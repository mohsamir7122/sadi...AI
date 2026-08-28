"""Command-line entry point for the governed Saudi post-open scan."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
from typing import Any

from .atomic_output import run_atomic_output
from .foundation_io import strict_json_object
from .markets.saudi.calendar import SaudiTradingCalendar, calendar_revision_from_bytes
from .markets.saudi.identity import saudi_security_master_from_bytes
from .saudi_admission import (
    MAX_POST_OPEN_CANDIDATES_PER_HORIZON,
    MAX_POST_OPEN_MARKET_AGE_MINUTES,
    SYNTHETIC_ADMISSION_TRUST_CLASS,
    AdmissionPurpose,
    VerifiedSaudiAdmission,
    verify_saudi_admission_receipt,
)
from .saudi_capabilities.nightly_lab import ALL_HORIZONS, Horizon
from .saudi_capabilities.post_open import (
    SaudiPostOpenScanner,
    post_open_observation_from_mapping,
)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("scan-at must include a timezone offset")
    return parsed


def _load_jsonl(content: bytes, *, admission: VerifiedSaudiAdmission):
    rows = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = strict_json_object(line, f"observation line {line_number}")
        except ValueError as exc:
            raise ValueError(f"invalid JSON on line {line_number}") from exc
        rows.append(
            post_open_observation_from_mapping(payload, admission=admission)
        )
    return tuple(rows)


def _load_weights(content: bytes) -> dict[Horizon, dict[str, float]]:
    payload: Any = strict_json_object(content, "Saudi horizon weights")
    if not isinstance(payload, dict) or set(payload) != {item.value for item in ALL_HORIZONS}:
        raise ValueError("weights must contain exactly the five governed horizons")
    result: dict[Horizon, dict[str, float]] = {}
    for horizon in ALL_HORIZONS:
        values = payload[horizon.value]
        if not isinstance(values, dict) or not values:
            raise ValueError(f"{horizon.value} weights must be an object")
        parsed: dict[str, float] = {}
        for factor_id, value in values.items():
            if (
                not isinstance(factor_id, str)
                or not factor_id.startswith("F9-")
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ValueError(
                    f"{horizon.value} weights require F9 string keys and finite JSON numbers"
                )
            parsed[factor_id] = float(value)
        result[horizon] = parsed
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rank Saudi research candidates after open plus thirty minutes"
    )
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--identity-file", type=Path, required=True)
    parser.add_argument("--calendar-file", type=Path, required=True)
    parser.add_argument("--admission-receipt", type=Path, required=True)
    parser.add_argument("--scan-at", type=_timestamp, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--maximum-market-age-minutes", type=int, default=15)
    parser.add_argument("--minimum-turnover-sar", type=float, default=0.0)
    parser.add_argument("--maximum-candidates-per-horizon", type=int, default=25)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.maximum_market_age_minutes <= MAX_POST_OPEN_MARKET_AGE_MINUTES:
        raise ValueError("maximum market age must be between 1 and 15 minutes")
    if not 1 <= args.maximum_candidates_per_horizon <= MAX_POST_OPEN_CANDIDATES_PER_HORIZON:
        raise ValueError("maximum candidates per horizon must be between 1 and 25")
    execution_contract = {
        "scan_at": args.scan_at.isoformat(),
        "maximum_market_age_minutes": args.maximum_market_age_minutes,
        "minimum_turnover_sar": args.minimum_turnover_sar,
        "maximum_candidates_per_horizon": args.maximum_candidates_per_horizon,
    }
    admission = verify_saudi_admission_receipt(
        args.admission_receipt,
        purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
        artifact_paths={
            "input": args.observations,
            "identity": args.identity_file,
            "calendar": args.calendar_file,
            "weights": args.weights,
        },
        decision_at=args.scan_at,
        expected_execution_contract=execution_contract,
    )
    observation_bytes = admission.artifact_bytes["input"]
    identity_bytes = admission.artifact_bytes["identity"]
    calendar_bytes = admission.artifact_bytes["calendar"]
    weights_bytes = admission.artifact_bytes["weights"]
    if any(
        value is None
        for value in (observation_bytes, identity_bytes, calendar_bytes, weights_bytes)
    ):
        raise RuntimeError("verified post-open admission omitted required artifacts")
    assert observation_bytes is not None
    assert identity_bytes is not None
    assert calendar_bytes is not None
    assert weights_bytes is not None
    calendar_revision = calendar_revision_from_bytes(
        calendar_bytes,
        known_at=args.scan_at,
    )
    scanner = SaudiPostOpenScanner(
        calendar=SaudiTradingCalendar(
            revision=calendar_revision
        ),
        security_master=saudi_security_master_from_bytes(identity_bytes),
        maximum_market_age=timedelta(minutes=args.maximum_market_age_minutes),
        minimum_turnover_sar=args.minimum_turnover_sar,
    )
    report = scanner.scan(
        _load_jsonl(observation_bytes, admission=admission),
        admission=admission,
        scan_at=args.scan_at,
        horizon_weights=_load_weights(weights_bytes),
        maximum_candidates_per_horizon=args.maximum_candidates_per_horizon,
    )
    if report["status"] == "UNAUTHENTICATED_RESEARCH_CANDIDATES":
        synthetic_only = (
            admission.trust_class == SYNTHETIC_ADMISSION_TRUST_CLASS
            or calendar_revision.evidence_class == "SYNTHETIC_ONLY"
        )
        report["status"] = (
            "SYNTHETIC_RESEARCH_CANDIDATES"
            if synthetic_only
            else "RESEARCH_CANDIDATES_READY"
        )
        report["evidence_class"] = (
            "SYNTHETIC_ONLY" if synthetic_only else calendar_revision.evidence_class
        )
        report["claim_boundary"] = (
            "Synthetic behavioral output only; not market evidence or a production "
            "research claim"
            if synthetic_only
            else "Admission-bound research candidates only; no personalized "
            "recommendation, probability, order, or execution"
        )
    report["input_admission_authenticated"] = True
    report["admission_trust_class"] = admission.trust_class
    report["admission"] = admission.to_dict()
    report["report_authenticated"] = False
    report["report_is_market_evidence"] = False

    def write(staging: Path) -> None:
        (staging / "post_open_report.json").write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    run_atomic_output(args.output_root, write)
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if report["status"] in {
        "RESEARCH_CANDIDATES_READY",
        "SYNTHETIC_RESEARCH_CANDIDATES",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
