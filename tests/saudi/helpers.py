from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from kubo.saudi_admission import (
    SAUDI_ADMISSION_ALGORITHM,
    SAUDI_ADMISSION_AUDIENCE,
    SYNTHETIC_ADMISSION_KEY_ID,
    SYNTHETIC_ADMISSION_TRUST_CLASS,
    AdmissionPurpose,
    artifact_roles_for_purpose,
    canonical_admission_bytes,
)


# Deterministic synthetic issuer material for tests only. This seed is derived
# from an explicit test label and is not a production credential.
SYNTHETIC_ADMISSION_PRIVATE_SEED = hashlib.sha256(
    b"sadi-ai tests only synthetic Ed25519 admission seed v1"
).digest()


def synthetic_calendar_payload(
    *,
    closed_from: date | None = None,
    closed_through: date | None = None,
    resume_on: date | None = None,
) -> dict[str, object]:
    holidays: list[dict[str, str]] = []
    if closed_from is not None:
        holidays.append(
            {
                "closed_from": closed_from.isoformat(),
                "closed_through": (closed_through or closed_from).isoformat(),
                "resume_on": (resume_on or date.fromordinal(closed_from.toordinal() + 1)).isoformat(),
                "reason": "SYNTHETIC_CLOSURE",
            }
        )
    return {
        "schema_version": "1.0",
        "revision_id": "synthetic-saudi-main-2026",
        "market": "SAUDI_EXCHANGE",
        "segment": "MAIN",
        "timezone": "Asia/Riyadh",
        "coverage_from": "2026-01-01",
        "coverage_through": "2026-12-31",
        "known_from": "2026-01-01T00:00:00+03:00",
        "known_to": None,
        "source_id": "synthetic-calendar-fixture",
        "source_url": "https://example.com/synthetic-saudi-calendar",
        "boundary_uncertainty_seconds": 30,
        "evidence_class": "SYNTHETIC_ONLY",
        "schedule": {
            "effective_from": "2026-01-01",
            "effective_through": "2026-12-31",
            "phases": [
                {
                    "name": "OPENING_AUCTION",
                    "start": "09:30:00",
                    "end": "10:00:00",
                    "executable": False,
                },
                {
                    "name": "CONTINUOUS_TRADING",
                    "start": "10:00:00",
                    "end": "15:00:00",
                    "executable": True,
                },
                {
                    "name": "CLOSING_AUCTION",
                    "start": "15:00:00",
                    "end": "15:10:00",
                    "executable": True,
                },
                {
                    "name": "TRADE_AT_LAST",
                    "start": "15:10:00",
                    "end": "15:20:00",
                    "executable": True,
                },
            ],
        },
        "holidays": holidays,
    }


def _isin_checksum_valid(value: str) -> bool:
    expanded = "".join(
        str(ord(character) - ord("A") + 10)
        if character.isalpha()
        else character
        for character in value
    )
    total = 0
    for index, character in enumerate(reversed(expanded)):
        digit = int(character) * (2 if index % 2 else 1)
        total += digit // 10 + digit % 10
    return total % 10 == 0


def identity_payload(
    code: str,
    *,
    instrument_type: str = "ORDINARY_EQUITY",
    segment: str = "MAIN",
    tradable: bool = True,
) -> dict[str, object]:
    isin_body = f"SA{code}56789"
    isin = next(
        candidate
        for check_digit in range(10)
        if (
            candidate := isin_body + str(check_digit)
        )
        and _isin_checksum_valid(candidate)
    )
    return {
        "security_id": f"sec-{code}",
        "official_code": code,
        "isin": isin,
        "symbol_en": f"SEC{code}",
        "symbol_ar": None,
        "issuer_id": f"issuer-{code}",
        "segment": segment,
        "instrument_type": instrument_type,
        "valid_from": "2016-01-01",
        "valid_to": None,
        "known_from": datetime(2016, 1, 1, tzinfo=timezone.utc).isoformat(),
        "known_to": None,
        "tradable": tradable,
    }


def write_admission_receipt(
    path: Path,
    *,
    purpose: AdmissionPurpose,
    artifact_paths: dict[str, Path | None],
    decision_at: datetime,
    execution_contract: Mapping[str, object] | None = None,
    issued_at: datetime | None = None,
) -> dict[str, object]:
    required_roles = artifact_roles_for_purpose(purpose)
    present_paths = {
        role: artifact
        for role, artifact in artifact_paths.items()
        if artifact is not None
    }
    if set(present_paths) != set(required_roles):
        raise ValueError("test artifact roles mismatch")
    descriptors: dict[str, object] = {}
    for role in required_roles:
        artifact = present_paths[role]
        content = artifact.read_bytes()
        descriptors[role] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
    if execution_contract is None:
        if purpose is AdmissionPurpose.NIGHTLY_MODEL_USE:
            execution_contract = {
                "run_id": "synthetic-nightly-run",
                "run_at": decision_at.isoformat(),
                "lookback_years": 10,
                "minimum_primary": 50,
                "minimum_probe": 300,
                "coverage_tolerance_days": 31,
                "maturity_buffer_days": 370,
                "maximum_coverage_gap_days": 396,
            }
        elif purpose is AdmissionPurpose.POST_OPEN_MODEL_USE:
            execution_contract = {
                "scan_at": decision_at.isoformat(),
                "maximum_market_age_minutes": 15,
                "minimum_turnover_sar": 0.0,
                "maximum_candidates_per_horizon": 25,
            }
        else:
            execution_contract = {
                "scored_at": decision_at.isoformat(),
                "run_id": "synthetic-holdout-run",
            }
    nightly = purpose is AdmissionPurpose.NIGHTLY_MODEL_USE
    model_use = purpose in {
        AdmissionPurpose.NIGHTLY_MODEL_USE,
        AdmissionPurpose.POST_OPEN_MODEL_USE,
    }
    assertions = (
        {
            "packet_sealed": True,
            "vault_sealed": True,
            "run_binding_verified": True,
        }
        if purpose is AdmissionPurpose.HOLDOUT_SCORE
        else {
            "identity_point_in_time_verified": True,
            "model_use_rights_verified": True,
            "source_authority_verified": True,
            "licensed_entitlements_verified_or_not_applicable": True,
            "denominator_complete": True if model_use else None,
            "corporate_actions_reconciled": True if nightly else None,
        }
    )
    authentication: dict[str, object] = {
        "algorithm": SAUDI_ADMISSION_ALGORITHM,
        "key_id": SYNTHETIC_ADMISSION_KEY_ID,
        "signature": "0" * 128,
    }
    effective_issued_at = issued_at or (
        decision_at
        if purpose is AdmissionPurpose.HOLDOUT_SCORE
        else decision_at - timedelta(hours=1)
    )
    payload: dict[str, object] = {
        "schema_version": "2.0",
        "audience": SAUDI_ADMISSION_AUDIENCE,
        "trust_class": SYNTHETIC_ADMISSION_TRUST_CLASS,
        "purpose": purpose.value,
        "receipt_id": f"synthetic-{purpose.value.lower()}",
        "issued_at": effective_issued_at.isoformat(),
        "expires_at": (decision_at + timedelta(hours=1)).isoformat(),
        "execution_contract": dict(execution_contract),
        "artifacts": descriptors,
        "assertions": assertions,
        "authentication": authentication,
    }
    private_key = Ed25519PrivateKey.from_private_bytes(
        SYNTHETIC_ADMISSION_PRIVATE_SEED
    )
    authentication["signature"] = private_key.sign(
        canonical_admission_bytes(payload)
    ).hex()
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload
