"""Public-key verification for governed Saudi runtime admissions.

This package contains verifier trust only. It intentionally ships no private
issuer key and the sole built-in key is explicitly synthetic, so a verified
receipt cannot be mistaken for production market evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping
from weakref import WeakSet

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .foundation_io import safe_regular_file, strict_json_object


SAUDI_ADMISSION_AUDIENCE = "sadi-ai-runtime-admission"
SAUDI_ADMISSION_ALGORITHM = "Ed25519"
SYNTHETIC_ADMISSION_TRUST_CLASS = "SYNTHETIC_ONLY"
SYNTHETIC_ADMISSION_KEY_ID = "synthetic-ed25519-admission-v1"
MAX_POST_OPEN_MARKET_AGE_MINUTES = 15
MAX_POST_OPEN_CANDIDATES_PER_HORIZON = 25
_MIB = 1024 * 1024


class AdmissionPurpose(str, Enum):
    NIGHTLY_MODEL_USE = "NIGHTLY_MODEL_USE"
    POST_OPEN_MODEL_USE = "POST_OPEN_MODEL_USE"
    HOLDOUT_SCORE = "HOLDOUT_SCORE"


_NIGHTLY_ARTIFACT_ROLES = (
    "input",
    "identity",
    "calendar",
    "denominator_report",
    "corporate_actions_report",
)
_POST_OPEN_ARTIFACT_ROLES = ("input", "identity", "calendar", "weights")
_HOLDOUT_ARTIFACT_ROLES = (
    "sealed_predictions",
    "outcome_vault",
    "run_report",
)
ARTIFACT_ROLES_BY_PURPOSE: Mapping[AdmissionPurpose, tuple[str, ...]] = (
    MappingProxyType(
        {
            AdmissionPurpose.NIGHTLY_MODEL_USE: _NIGHTLY_ARTIFACT_ROLES,
            AdmissionPurpose.POST_OPEN_MODEL_USE: _POST_OPEN_ARTIFACT_ROLES,
            AdmissionPurpose.HOLDOUT_SCORE: _HOLDOUT_ARTIFACT_ROLES,
        }
    )
)
ARTIFACT_ROLES = tuple(
    dict.fromkeys(
        role
        for roles in ARTIFACT_ROLES_BY_PURPOSE.values()
        for role in roles
    )
)
MAX_ARTIFACT_BYTES_BY_ROLE: Mapping[str, int] = MappingProxyType(
    {
        "input": 128 * _MIB,
        "identity": 32 * _MIB,
        "calendar": 8 * _MIB,
        "denominator_report": 8 * _MIB,
        "corporate_actions_report": 8 * _MIB,
        "weights": 8 * _MIB,
        "sealed_predictions": 128 * _MIB,
        "outcome_vault": 128 * _MIB,
        "run_report": 8 * _MIB,
    }
)

_EXECUTION_FIELDS_BY_PURPOSE: Mapping[AdmissionPurpose, frozenset[str]] = (
    MappingProxyType(
        {
            AdmissionPurpose.NIGHTLY_MODEL_USE: frozenset(
                {
                    "run_id",
                    "run_at",
                    "lookback_years",
                    "minimum_primary",
                    "minimum_probe",
                    "coverage_tolerance_days",
                    "maturity_buffer_days",
                    "maximum_coverage_gap_days",
                }
            ),
            AdmissionPurpose.POST_OPEN_MODEL_USE: frozenset(
                {
                    "scan_at",
                    "maximum_market_age_minutes",
                    "minimum_turnover_sar",
                    "maximum_candidates_per_horizon",
                }
            ),
            AdmissionPurpose.HOLDOUT_SCORE: frozenset({"scored_at", "run_id"}),
        }
    )
)

_TOP_FIELDS = frozenset(
    {
        "schema_version",
        "audience",
        "trust_class",
        "purpose",
        "receipt_id",
        "issued_at",
        "expires_at",
        "execution_contract",
        "artifacts",
        "assertions",
        "authentication",
    }
)
_DESCRIPTOR_FIELDS = frozenset({"sha256", "size_bytes"})
_MODEL_USE_ASSERTION_FIELDS = frozenset(
    {
        "identity_point_in_time_verified",
        "model_use_rights_verified",
        "source_authority_verified",
        "licensed_entitlements_verified_or_not_applicable",
        "denominator_complete",
        "corporate_actions_reconciled",
    }
)
_HOLDOUT_ASSERTION_FIELDS = frozenset(
    {"packet_sealed", "vault_sealed", "run_binding_verified"}
)
ASSERTION_FIELDS_BY_PURPOSE: Mapping[AdmissionPurpose, frozenset[str]] = (
    MappingProxyType(
        {
            AdmissionPurpose.NIGHTLY_MODEL_USE: _MODEL_USE_ASSERTION_FIELDS,
            AdmissionPurpose.POST_OPEN_MODEL_USE: _MODEL_USE_ASSERTION_FIELDS,
            AdmissionPurpose.HOLDOUT_SCORE: _HOLDOUT_ASSERTION_FIELDS,
        }
    )
)
_AUTH_FIELDS = frozenset({"algorithm", "key_id", "signature"})
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,254}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")

class _VerifiedConstructionMarker:
    __slots__ = ("__weakref__",)


_CONSUMED_CONSTRUCTION_MARKERS: WeakSet[_VerifiedConstructionMarker] = WeakSet()


class SaudiAdmissionError(ValueError):
    """Raised when a Saudi admission is not exactly and publicly verified."""


@dataclass(frozen=True)
class AdmissionTrustKey:
    key_id: str
    algorithm: str
    trust_class: str
    purposes: frozenset[AdmissionPurpose]
    public_key_bytes: bytes = field(repr=False)


# Public verifier material only. The corresponding deterministic test-only
# private seed lives under tests/saudi/helpers.py and is never a production key.
_SYNTHETIC_PUBLIC_KEY = bytes.fromhex(
    "3fa706aba38733a44a4de96a6c09a8eaeccba52ffe020137834fd69ac587b60e"
)
BUILTIN_ADMISSION_TRUST_STORE: Mapping[str, AdmissionTrustKey] = MappingProxyType(
    {
        SYNTHETIC_ADMISSION_KEY_ID: AdmissionTrustKey(
            key_id=SYNTHETIC_ADMISSION_KEY_ID,
            algorithm=SAUDI_ADMISSION_ALGORITHM,
            trust_class=SYNTHETIC_ADMISSION_TRUST_CLASS,
            purposes=frozenset(AdmissionPurpose),
            public_key_bytes=_SYNTHETIC_PUBLIC_KEY,
        )
    }
)


def artifact_roles_for_purpose(purpose: AdmissionPurpose) -> tuple[str, ...]:
    if not isinstance(purpose, AdmissionPurpose):
        raise SaudiAdmissionError("admission purpose must use AdmissionPurpose")
    return ARTIFACT_ROLES_BY_PURPOSE[purpose]


def execution_fields_for_purpose(purpose: AdmissionPurpose) -> frozenset[str]:
    if not isinstance(purpose, AdmissionPurpose):
        raise SaudiAdmissionError("admission purpose must use AdmissionPurpose")
    return _EXECUTION_FIELDS_BY_PURPOSE[purpose]


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SaudiAdmissionError(
            "admission receipt is not canonicalizable JSON"
        ) from exc


def canonical_admission_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return the exact Ed25519 signing bytes for an admission receipt."""

    if not isinstance(payload, Mapping):
        raise SaudiAdmissionError("admission receipt must be an object")
    authentication = payload.get("authentication")
    if not isinstance(authentication, Mapping):
        raise SaudiAdmissionError("admission authentication must be an object")
    return _canonical(
        {
            "receipt": {
                key: value
                for key, value in payload.items()
                if key != "authentication"
            },
            "algorithm": authentication.get("algorithm"),
            "key_id": authentication.get("key_id"),
        }
    )


def _timestamp(value: object, field_name: str) -> datetime:
    if type(value) is not str:
        raise SaudiAdmissionError(f"{field_name} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SaudiAdmissionError(
            f"{field_name} must be an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SaudiAdmissionError(f"{field_name} must be timezone-aware")
    return parsed


def _exact(
    value: object,
    fields: frozenset[str] | set[str],
    field_name: str,
) -> Mapping[str, Any]:
    if (
        not isinstance(value, Mapping)
        or any(type(key) is not str for key in value)
        or set(value) != set(fields)
    ):
        raise SaudiAdmissionError(f"{field_name} fields mismatch")
    return value


def _identifier(value: object, field_name: str) -> str:
    if type(value) is not str or value != value.strip() or not _ID_RE.fullmatch(value):
        raise SaudiAdmissionError(f"{field_name} is invalid")
    return value


def _positive_integer(
    value: object,
    field_name: str,
    *,
    allow_zero: bool = False,
) -> int:
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise SaudiAdmissionError(f"{field_name} must be a {qualifier} integer")
    return value


def _non_negative_number(value: object, field_name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SaudiAdmissionError(f"{field_name} must be a non-negative number")
    try:
        finite = math.isfinite(float(value))
    except (OverflowError, ValueError):
        finite = False
    if not finite or value < 0:
        raise SaudiAdmissionError(f"{field_name} must be a non-negative number")
    return value


def _validate_execution_contract(
    value: object,
    *,
    purpose: AdmissionPurpose,
    field_name: str,
) -> dict[str, object]:
    contract = _exact(value, execution_fields_for_purpose(purpose), field_name)
    validated: dict[str, object] = dict(contract)
    if purpose is AdmissionPurpose.NIGHTLY_MODEL_USE:
        _identifier(contract["run_id"], f"{field_name}.run_id")
        _timestamp(contract["run_at"], f"{field_name}.run_at")
        _positive_integer(
            contract["lookback_years"], f"{field_name}.lookback_years"
        )
        _positive_integer(
            contract["minimum_primary"], f"{field_name}.minimum_primary"
        )
        _positive_integer(
            contract["minimum_probe"], f"{field_name}.minimum_probe"
        )
        _positive_integer(
            contract["coverage_tolerance_days"],
            f"{field_name}.coverage_tolerance_days",
            allow_zero=True,
        )
        _positive_integer(
            contract["maturity_buffer_days"],
            f"{field_name}.maturity_buffer_days",
        )
        _positive_integer(
            contract["maximum_coverage_gap_days"],
            f"{field_name}.maximum_coverage_gap_days",
        )
    elif purpose is AdmissionPurpose.POST_OPEN_MODEL_USE:
        _timestamp(contract["scan_at"], f"{field_name}.scan_at")
        _positive_integer(
            contract["maximum_market_age_minutes"],
            f"{field_name}.maximum_market_age_minutes",
        )
        _non_negative_number(
            contract["minimum_turnover_sar"],
            f"{field_name}.minimum_turnover_sar",
        )
        _positive_integer(
            contract["maximum_candidates_per_horizon"],
            f"{field_name}.maximum_candidates_per_horizon",
        )
        if (
            contract["maximum_market_age_minutes"]
            > MAX_POST_OPEN_MARKET_AGE_MINUTES
        ):
            raise SaudiAdmissionError(
                f"{field_name}.maximum_market_age_minutes exceeds governed maximum"
            )
        if (
            contract["maximum_candidates_per_horizon"]
            > MAX_POST_OPEN_CANDIDATES_PER_HORIZON
        ):
            raise SaudiAdmissionError(
                f"{field_name}.maximum_candidates_per_horizon exceeds governed maximum"
            )
    else:
        _timestamp(contract["scored_at"], f"{field_name}.scored_at")
        _identifier(contract["run_id"], f"{field_name}.run_id")
    return validated


def _contract_decision_at(
    contract: Mapping[str, object], purpose: AdmissionPurpose
) -> datetime:
    field_name = {
        AdmissionPurpose.NIGHTLY_MODEL_USE: "run_at",
        AdmissionPurpose.POST_OPEN_MODEL_USE: "scan_at",
        AdmissionPurpose.HOLDOUT_SCORE: "scored_at",
    }[purpose]
    return _timestamp(contract[field_name], f"execution_contract.{field_name}")


def _utc(value: datetime) -> datetime:
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise SaudiAdmissionError(
            "admission timestamp is outside the supported UTC range"
        ) from exc


def _snapshot_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _read_file_snapshot(
    path: Path,
    *,
    field_name: str,
    max_bytes: int | None = None,
) -> tuple[bytes, tuple[int, int]]:
    if not isinstance(path, Path):
        raise SaudiAdmissionError(f"{field_name} path must be a pathlib.Path")
    try:
        before = os.stat(path, follow_symlinks=False)
        if max_bytes is None:
            content = safe_regular_file(path, field=field_name)
        else:
            content = safe_regular_file(path, field=field_name, max_bytes=max_bytes)
        after = os.stat(path, follow_symlinks=False)
    except (OSError, ValueError) as exc:
        raise SaudiAdmissionError(f"{field_name} cannot be read safely") from exc
    if _snapshot_identity(before) != _snapshot_identity(after):
        raise SaudiAdmissionError(f"{field_name} changed while being read")
    return content, (after.st_dev, after.st_ino)


@dataclass(frozen=True, eq=False)
class VerifiedSaudiAdmission:
    receipt_id: str
    purpose: AdmissionPurpose
    trust_class: str
    issued_at: datetime
    expires_at: datetime
    authenticated_key_id: str
    content_sha256: str
    execution_contract: Mapping[str, object]
    artifact_sha256: Mapping[str, str]
    assertions: Mapping[str, bool | None]
    artifact_bytes: Mapping[str, bytes] = field(repr=False)
    _construction_marker: object = field(repr=False, compare=False)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("VerifiedSaudiAdmission cannot be subclassed")

    def __post_init__(self) -> None:
        marker = self._construction_marker
        if (
            not isinstance(marker, _VerifiedConstructionMarker)
            or marker in _CONSUMED_CONSTRUCTION_MARKERS
        ):
            raise TypeError(
                "VerifiedSaudiAdmission must come from one receipt verification and cannot be replaced"
            )
        _CONSUMED_CONSTRUCTION_MARKERS.add(marker)

    def __copy__(self) -> "VerifiedSaudiAdmission":
        raise TypeError("VerifiedSaudiAdmission cannot be copied")

    def __deepcopy__(self, memo: object) -> "VerifiedSaudiAdmission":
        raise TypeError("VerifiedSaudiAdmission cannot be copied")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("VerifiedSaudiAdmission cannot be serialized")

    def to_dict(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "purpose": self.purpose.value,
            "trust_class": self.trust_class,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "authenticated_key_id": self.authenticated_key_id,
            "content_sha256": self.content_sha256,
            "execution_contract": dict(self.execution_contract),
            "artifact_sha256": dict(self.artifact_sha256),
            "assertions": dict(self.assertions),
            "market_evidence_trust_class": self.trust_class,
            "receipt_is_market_evidence": False,
        }


def _verify_saudi_admission_receipt_impl(
    receipt_path: Path,
    *,
    purpose: AdmissionPurpose,
    artifact_paths: Mapping[str, Path],
    decision_at: datetime,
    expected_execution_contract: Mapping[str, object],
) -> VerifiedSaudiAdmission:
    """Verify one purpose-bound receipt against the built-in public trust store."""

    if not isinstance(purpose, AdmissionPurpose):
        raise SaudiAdmissionError("admission purpose must use AdmissionPurpose")
    if not isinstance(decision_at, datetime):
        raise SaudiAdmissionError("decision_at must be a datetime")
    if decision_at.tzinfo is None or decision_at.utcoffset() is None:
        raise SaudiAdmissionError("decision_at must be timezone-aware")
    expected_roles = frozenset(artifact_roles_for_purpose(purpose))
    _exact(artifact_paths, expected_roles, "artifact paths")

    receipt_bytes, receipt_inode = _read_file_snapshot(
        receipt_path,
        field_name="Saudi admission receipt",
        max_bytes=2 * 1024 * 1024,
    )
    try:
        payload = strict_json_object(receipt_bytes, "Saudi admission receipt")
    except ValueError as exc:
        raise SaudiAdmissionError(str(exc)) from exc
    top = _exact(payload, _TOP_FIELDS, "admission receipt")
    if type(top["schema_version"]) is not str or top["schema_version"] != "2.0":
        raise SaudiAdmissionError("admission receipt schema mismatch")
    if (
        type(top["audience"]) is not str
        or top["audience"] != SAUDI_ADMISSION_AUDIENCE
    ):
        raise SaudiAdmissionError("admission receipt audience mismatch")
    try:
        actual_purpose = AdmissionPurpose(top["purpose"])
    except (TypeError, ValueError) as exc:
        raise SaudiAdmissionError("admission receipt purpose is invalid") from exc
    if actual_purpose is not purpose:
        raise SaudiAdmissionError("admission receipt purpose mismatch")
    receipt_id = _identifier(top["receipt_id"], "admission receipt_id")
    if type(top["trust_class"]) is not str:
        raise SaudiAdmissionError("admission receipt trust_class is invalid")

    authentication = _exact(top["authentication"], _AUTH_FIELDS, "authentication")
    if (
        type(authentication["algorithm"]) is not str
        or authentication["algorithm"] != SAUDI_ADMISSION_ALGORITHM
    ):
        raise SaudiAdmissionError("unsupported admission authentication algorithm")
    key_id = _identifier(
        authentication["key_id"], "admission authentication key_id"
    )
    trust_key = BUILTIN_ADMISSION_TRUST_STORE.get(key_id)
    if trust_key is None:
        raise SaudiAdmissionError("admission authentication key_id is not trusted")
    if trust_key.algorithm != authentication["algorithm"]:
        raise SaudiAdmissionError("admission trust-store algorithm mismatch")
    if purpose not in trust_key.purposes:
        raise SaudiAdmissionError("admission key is not authorized for purpose")
    if top["trust_class"] != trust_key.trust_class:
        raise SaudiAdmissionError("admission trust_class mismatch")
    signature_hex = authentication["signature"]
    if type(signature_hex) is not str or not _SIGNATURE_RE.fullmatch(signature_hex):
        raise SaudiAdmissionError("admission authentication signature is invalid")
    try:
        Ed25519PublicKey.from_public_bytes(trust_key.public_key_bytes).verify(
            bytes.fromhex(signature_hex),
            canonical_admission_bytes(top),
        )
    except (InvalidSignature, ValueError) as exc:
        raise SaudiAdmissionError("admission authentication failed") from exc

    issued_at = _timestamp(top["issued_at"], "issued_at")
    expires_at = _timestamp(top["expires_at"], "expires_at")
    issued_utc = _utc(issued_at)
    decision_utc = _utc(decision_at)
    expires_utc = _utc(expires_at)
    if not issued_utc <= decision_utc < expires_utc:
        raise SaudiAdmissionError("admission receipt is not valid at decision_at")
    if (
        expires_utc <= issued_utc
        or expires_utc - issued_utc > timedelta(hours=24)
    ):
        raise SaudiAdmissionError("admission receipt validity window is invalid")

    actual_contract = _validate_execution_contract(
        top["execution_contract"],
        purpose=purpose,
        field_name="execution_contract",
    )
    expected_contract = _validate_execution_contract(
        expected_execution_contract,
        purpose=purpose,
        field_name="expected_execution_contract",
    )
    if _canonical(actual_contract) != _canonical(expected_contract):
        raise SaudiAdmissionError("admission execution_contract mismatch")
    if _utc(_contract_decision_at(actual_contract, purpose)) != decision_utc:
        raise SaudiAdmissionError(
            "admission decision_at does not match execution_contract"
        )

    assertions = _exact(
        top["assertions"], ASSERTION_FIELDS_BY_PURPOSE[purpose], "assertions"
    )
    if purpose is AdmissionPurpose.HOLDOUT_SCORE:
        for assertion_name in _HOLDOUT_ASSERTION_FIELDS:
            if assertions[assertion_name] is not True:
                raise SaudiAdmissionError(
                    f"admission assertion failed: {assertion_name}"
                )
    else:
        for assertion_name in (
            "identity_point_in_time_verified",
            "model_use_rights_verified",
            "source_authority_verified",
            "licensed_entitlements_verified_or_not_applicable",
        ):
            if assertions[assertion_name] is not True:
                raise SaudiAdmissionError(
                    f"admission assertion failed: {assertion_name}"
                )
    if purpose is AdmissionPurpose.NIGHTLY_MODEL_USE:
        if assertions["denominator_complete"] is not True:
            raise SaudiAdmissionError(
                "admission assertion failed: denominator_complete"
            )
        if assertions["corporate_actions_reconciled"] is not True:
            raise SaudiAdmissionError(
                "admission assertion failed: corporate_actions_reconciled"
            )
    elif purpose is AdmissionPurpose.POST_OPEN_MODEL_USE:
        if assertions["denominator_complete"] is not True:
            raise SaudiAdmissionError(
                "admission assertion failed: denominator_complete"
            )
        if assertions["corporate_actions_reconciled"] is not None:
            raise SaudiAdmissionError(
                "post-open corporate_actions_reconciled assertion must be null"
            )

    artifacts = _exact(top["artifacts"], expected_roles, "artifacts")
    seen_inodes = {receipt_inode}
    hashes: dict[str, str] = {}
    bound_bytes: dict[str, bytes] = {}
    for role in artifact_roles_for_purpose(purpose):
        path = artifact_paths[role]
        item = _exact(artifacts[role], _DESCRIPTOR_FIELDS, f"artifacts.{role}")
        digest = item["sha256"]
        size = item["size_bytes"]
        if type(digest) is not str or not _SHA_RE.fullmatch(digest):
            raise SaudiAdmissionError(f"artifacts.{role}.sha256 is invalid")
        if type(size) is not int or size < 0:
            raise SaudiAdmissionError(f"artifacts.{role}.size_bytes is invalid")
        content, inode = _read_file_snapshot(
            path,
            field_name=f"Saudi admission artifact {role}",
            max_bytes=MAX_ARTIFACT_BYTES_BY_ROLE[role],
        )
        if inode in seen_inodes:
            raise SaudiAdmissionError(
                "admission receipt and artifacts must be inode-distinct files"
            )
        seen_inodes.add(inode)
        if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
            raise SaudiAdmissionError(f"admission artifact mismatch: {role}")
        hashes[role] = digest
        bound_bytes[role] = content

    unsigned = {key: value for key, value in top.items() if key != "authentication"}
    return VerifiedSaudiAdmission(
        receipt_id=receipt_id,
        purpose=purpose,
        trust_class=trust_key.trust_class,
        issued_at=issued_at,
        expires_at=expires_at,
        authenticated_key_id=key_id,
        content_sha256=hashlib.sha256(_canonical(unsigned)).hexdigest(),
        execution_contract=MappingProxyType(dict(actual_contract)),
        artifact_sha256=MappingProxyType(hashes),
        assertions=MappingProxyType(dict(assertions)),
        artifact_bytes=MappingProxyType(bound_bytes),
        _construction_marker=_VerifiedConstructionMarker(),
    )


def _build_verified_admission_boundary(verifier: object) -> tuple[object, object]:
    """Keep accepted object identities private to verifier and consumers.

    A leading underscore is not an authentication boundary in Python. Runtime
    consumers therefore require both the exact sealed class and an identity
    recorded only after the public-key verifier completes successfully.
    """

    verified_instances: WeakSet[VerifiedSaudiAdmission] = WeakSet()

    @wraps(verifier)
    def verified_verifier(*args: object, **kwargs: object) -> VerifiedSaudiAdmission:
        admission = verifier(*args, **kwargs)  # type: ignore[operator]
        if type(admission) is not VerifiedSaudiAdmission:
            raise SaudiAdmissionError("admission verifier returned an invalid type")
        verified_instances.add(admission)
        return admission

    def require_verified(
        value: object, *, purpose: AdmissionPurpose
    ) -> VerifiedSaudiAdmission:
        if (
            type(value) is not VerifiedSaudiAdmission
            or value not in verified_instances
            or value.purpose is not purpose
        ):
            raise SaudiAdmissionError(
                "Saudi admission must be the exact result of receipt verification "
                "for this purpose"
            )
        return value

    return verified_verifier, require_verified


(
    verify_saudi_admission_receipt,
    require_verified_saudi_admission,
) = _build_verified_admission_boundary(_verify_saudi_admission_receipt_impl)
del _build_verified_admission_boundary
del _verify_saudi_admission_receipt_impl


__all__ = [
    "ARTIFACT_ROLES",
    "ARTIFACT_ROLES_BY_PURPOSE",
    "ASSERTION_FIELDS_BY_PURPOSE",
    "AdmissionPurpose",
    "AdmissionTrustKey",
    "BUILTIN_ADMISSION_TRUST_STORE",
    "MAX_ARTIFACT_BYTES_BY_ROLE",
    "MAX_POST_OPEN_CANDIDATES_PER_HORIZON",
    "MAX_POST_OPEN_MARKET_AGE_MINUTES",
    "SAUDI_ADMISSION_ALGORITHM",
    "SAUDI_ADMISSION_AUDIENCE",
    "SYNTHETIC_ADMISSION_KEY_ID",
    "SYNTHETIC_ADMISSION_TRUST_CLASS",
    "SaudiAdmissionError",
    "VerifiedSaudiAdmission",
    "artifact_roles_for_purpose",
    "canonical_admission_bytes",
    "execution_fields_for_purpose",
    "require_verified_saudi_admission",
    "verify_saudi_admission_receipt",
]
