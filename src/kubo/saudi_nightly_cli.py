"""Command-line entry point for the governed Saudi nightly laboratory."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .atomic_output import run_atomic_output
from .foundation_io import strict_json_object
from .markets.saudi.calendar import SaudiTradingCalendar, calendar_revision_from_bytes
from .markets.saudi.config import RIYADH_TZ
from .markets.saudi.identity import saudi_security_master_from_bytes
from .saudi_admission import (
    SYNTHETIC_ADMISSION_TRUST_CLASS,
    AdmissionPurpose,
    VerifiedSaudiAdmission,
    verify_saudi_admission_receipt,
)
from .saudi_evidence_reports import (
    corporate_actions_report_from_bytes,
    cross_validate_evidence_reports,
    denominator_report_from_bytes,
)
from .saudi_capabilities.nightly_lab import (
    historical_event_from_mapping,
    prepare_nightly_run,
)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone offset")
    return parsed


def _load_events(
    content: bytes,
    *,
    identity_content: bytes,
    admission: VerifiedSaudiAdmission,
):
    security_master = saudi_security_master_from_bytes(identity_content)
    events = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = strict_json_object(line, f"event line {line_number}")
        except ValueError as exc:
            raise ValueError(f"invalid JSON on line {line_number}") from exc
        events.append(
            historical_event_from_mapping(
                payload,
                security_master=security_master,
                admission=admission,
            )
        )
    return tuple(events)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _years_before(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, month=2, day=28)


def _require_absent_output_roots(*roots: Path) -> None:
    """Preflight every publication root before the first root is committed."""

    for root in roots:
        if os.path.lexists(root):
            raise ValueError(f"output root must be absent before run: {root}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Point-in-Time Saudi ten-year event laboratory"
    )
    parser.add_argument("--events", type=Path, required=True, help="authorized event JSONL")
    parser.add_argument("--identity-file", type=Path, required=True)
    parser.add_argument("--calendar-file", type=Path, required=True)
    parser.add_argument("--denominator-report", type=Path, required=True)
    parser.add_argument("--corporate-actions-report", type=Path, required=True)
    parser.add_argument("--admission-receipt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--outcome-vault-output-root",
        type=Path,
        required=True,
        help="separate restricted output root for retrospective withheld-fit outcomes",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-at", type=_timestamp, required=True)
    parser.add_argument("--lookback-years", type=int, default=10)
    parser.add_argument("--minimum-primary", type=int, default=50)
    parser.add_argument("--minimum-probe", type=int, default=300)
    parser.add_argument("--coverage-tolerance-days", type=int, default=31)
    parser.add_argument("--maturity-buffer-days", type=int, default=370)
    parser.add_argument("--maximum-coverage-gap-days", type=int, default=396)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = args.output_root.resolve()
    vault_root = args.outcome_vault_output_root.resolve()
    if (
        output_root == vault_root
        or output_root in vault_root.parents
        or vault_root in output_root.parents
    ):
        raise ValueError("outcome vault and model outputs must use disjoint roots")
    _require_absent_output_roots(args.output_root, args.outcome_vault_output_root)
    if args.lookback_years != 10:
        raise ValueError("governed nightly CLI requires exactly ten lookback years")
    if args.minimum_primary < 50 or args.minimum_probe < 300:
        raise ValueError("governed nightly CLI minimums cannot be reduced below 50/300")
    if not 0 <= args.coverage_tolerance_days <= 31:
        raise ValueError("governed coverage tolerance must be between 0 and 31 days")
    if not 1 <= args.maturity_buffer_days <= 370:
        raise ValueError("governed maturity buffer must be between 1 and 370 days")
    if not 1 <= args.maximum_coverage_gap_days <= 396:
        raise ValueError("governed maximum coverage gap must be between 1 and 396 days")
    execution_contract = {
        "run_id": args.run_id,
        "run_at": args.run_at.isoformat(),
        "lookback_years": args.lookback_years,
        "minimum_primary": args.minimum_primary,
        "minimum_probe": args.minimum_probe,
        "coverage_tolerance_days": args.coverage_tolerance_days,
        "maturity_buffer_days": args.maturity_buffer_days,
        "maximum_coverage_gap_days": args.maximum_coverage_gap_days,
    }
    admission = verify_saudi_admission_receipt(
        args.admission_receipt,
        purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
        artifact_paths={
            "input": args.events,
            "identity": args.identity_file,
            "calendar": args.calendar_file,
            "denominator_report": args.denominator_report,
            "corporate_actions_report": args.corporate_actions_report,
        },
        decision_at=args.run_at,
        expected_execution_contract=execution_contract,
    )
    event_bytes = admission.artifact_bytes["input"]
    identity_bytes = admission.artifact_bytes["identity"]
    calendar_bytes = admission.artifact_bytes["calendar"]
    denominator_bytes = admission.artifact_bytes["denominator_report"]
    corporate_actions_bytes = admission.artifact_bytes["corporate_actions_report"]
    calendar_revision = calendar_revision_from_bytes(
        calendar_bytes,
        known_at=args.run_at,
    )
    synthetic_only = (
        admission.trust_class == SYNTHETIC_ADMISSION_TRUST_CLASS
        or calendar_revision.evidence_class == "SYNTHETIC_ONLY"
    )
    local_run_at = args.run_at.astimezone(ZoneInfo(RIYADH_TZ))
    governed_start = _years_before(local_run_at, args.lookback_years)
    if (
        calendar_revision.coverage_from > governed_start.date()
        or calendar_revision.coverage_through < local_run_at.date()
    ):
        raise ValueError("calendar revision does not cover the governed nightly window")
    events = _load_events(
        event_bytes,
        identity_content=identity_bytes,
        admission=admission,
    )
    point_in_time_calendar = SaudiTradingCalendar(revision=calendar_revision)
    for event in events:
        prediction_date = event.prediction_at.astimezone(
            ZoneInfo(RIYADH_TZ)
        ).date()
        session = point_in_time_calendar.session_for(
            prediction_date,
            known_at=event.prediction_at,
        )
        if not session.coverage_known:
            raise ValueError("CALENDAR_NOT_POINT_IN_TIME_AT_EVENT_PREDICTION")
    denominator = denominator_report_from_bytes(denominator_bytes)
    corporate_actions = corporate_actions_report_from_bytes(corporate_actions_bytes)
    expected_input_sha256 = hashlib.sha256(event_bytes).hexdigest()
    evidence_arguments = {
        "expected_run_id": args.run_id,
        "expected_input_sha256": expected_input_sha256,
        "expected_coverage_from": governed_start.date(),
        "expected_coverage_through": local_run_at.date(),
        "expected_event_count": len(events),
    }
    cross_validate_evidence_reports(
        denominator,
        corporate_actions,
        **evidence_arguments,
    )
    identity_sha256 = hashlib.sha256(identity_bytes).hexdigest()
    if denominator.security_set_sha256 != identity_sha256:
        raise ValueError("evidence reports do not bind the admitted identity file")
    prepared = prepare_nightly_run(
        events,
        run_id=args.run_id,
        run_at=args.run_at,
        calendar=point_in_time_calendar,
        lookback_years=args.lookback_years,
        minimum_primary=args.minimum_primary,
        minimum_probe=args.minimum_probe,
        coverage_tolerance_days=args.coverage_tolerance_days,
        maturity_buffer_days=args.maturity_buffer_days,
        maximum_coverage_gap_days=args.maximum_coverage_gap_days,
    )
    if prepared.status == "STOP_TRAINING":
        report = {
            "status": prepared.status,
            "run_id": args.run_id,
            "run_at": args.run_at.isoformat(),
            "counts": dict(prepared.counts),
            "reasons": list(prepared.reasons),
            "coverage_audit": prepared.coverage_audit,
            "governed_policy": execution_contract,
            "model_updated": False,
            "final_holdout_scored": False,
            "recommendation": None,
            "admission": admission.to_dict(),
            "evidence_class": (
                "SYNTHETIC_ONLY" if synthetic_only else calendar_revision.evidence_class
            ),
            "calendar_revision_id": calendar_revision.revision_id,
            "calendar_content_sha256": calendar_revision.content_sha256,
            "input_admission_authenticated": True,
            "report_authenticated": False,
            "report_is_market_evidence": False,
        }

        def write_stop(staging: Path) -> None:
            _write_json(staging / "run_report.json", report)

        run_atomic_output(args.output_root, write_stop)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))
        return 2

    if prepared.split is None or prepared.model is None or prepared.sealed_packet is None:
        raise RuntimeError("nightly preparation returned incomplete artifacts")
    if prepared.status != "UNAUTHENTICATED_SEALED_AWAITING_FINAL_SCORE":
        raise RuntimeError("nightly preparation returned an unexpected trust status")
    receipt = {
        "status": (
            "SYNTHETIC_SEALED_AWAITING_FINAL_SCORE"
            if synthetic_only
            else "SEALED_AWAITING_FINAL_SCORE"
        ),
        "run_id": args.run_id,
        "run_at": args.run_at.isoformat(),
        "counts": dict(prepared.counts),
        "coverage_audit": prepared.coverage_audit,
        "governed_policy": execution_contract,
        "split_counts": {
            "training": len(prepared.split.training),
            "validation": len(prepared.split.validation),
            "final_holdout": len(prepared.split.blind_holdout),
        },
        "temporal_audit": {
            "validation_start": prepared.split.validation_start.isoformat(),
            "holdout_start": prepared.split.holdout_start.isoformat(),
            "max_training_label_end": prepared.split.max_training_label_end.isoformat(),
            "max_validation_label_end": prepared.split.max_validation_label_end.isoformat(),
            "max_training_information_end": prepared.split.max_training_information_end.isoformat(),
            "max_validation_information_end": prepared.split.max_validation_information_end.isoformat(),
            "purged_event_count": len(prepared.split.purged_event_ids),
            "purged_event_ids": list(prepared.split.purged_event_ids),
            "cohort_counts": prepared.split.cohort_counts,
            "source_event_count": prepared.split.source_event_count,
            "retained_event_count": prepared.split.retained_event_count,
            "retained_ratios": dict(prepared.split.retained_ratios),
            "purge_rate": prepared.split.purge_rate,
        },
        "stage_order": [
            "COHORT_COUNT_GATE",
            "HISTORY_COVERAGE_GATE",
            "GLOBAL_CAUSAL_SPLIT_AND_INFORMATION_PURGE",
            "TRAINING_FIT",
            "VALIDATION_CALIBRATION",
            "FINAL_HOLDOUT_PREDICTIONS_SEALED",
        ],
        "model_fingerprint": prepared.model.fingerprint,
        "seal_sha256": prepared.sealed_packet.seal_sha256,
        "outcome_vault_sha256": prepared.split.outcome_vault.vault_sha256,
        "final_holdout_scored": False,
        "input_admission_authenticated": True,
        "report_authenticated": False,
        "report_is_market_evidence": False,
        "admission": admission.to_dict(),
        "evidence_class": (
            "SYNTHETIC_ONLY" if synthetic_only else calendar_revision.evidence_class
        ),
        "calendar_revision_id": calendar_revision.revision_id,
        "calendar_content_sha256": calendar_revision.content_sha256,
        "recommendation": None,
        "execution": None,
        "claim_boundary": "Historical research only; no live trading or accuracy claim",
        "holdout_boundary": (
            "Retrospective out-of-sample code-path separation only; every label is "
            "mature at run_at and no independent custodian or timestamp is supplied"
        ),
    }
    horizon_weight_export = {
        item.horizon.value: {factor_id: weight for factor_id, weight in item.weights}
        for item in prepared.model.horizon_weights
    }

    def write_complete(staging: Path) -> None:
        _write_json(staging / "model.json", prepared.model.to_dict())
        _write_json(staging / "horizon_weights.json", horizon_weight_export)
        _write_json(staging / "sealed_predictions.json", prepared.sealed_packet.to_dict())
        _write_json(staging / "run_report.json", receipt)

    def write_vault(staging: Path) -> None:
        _write_json(staging / "outcome_vault.json", prepared.split.outcome_vault.to_dict())
        _write_json(
            staging / "vault_manifest.json",
            {
                "run_id": args.run_id,
                "vault_sha256": prepared.split.outcome_vault.vault_sha256,
                "sealed_prediction_sha256": hashlib.sha256(
                    (
                        json.dumps(
                            prepared.sealed_packet.to_dict(),
                            ensure_ascii=False,
                            allow_nan=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n"
                    ).encode("utf-8")
                ).hexdigest(),
                "restricted_artifact": True,
                "release_requires_holdout_score_admission": True,
                "claim_boundary": "Holdout labels; store separately from model development outputs",
                "holdout_boundary": (
                    "Labels were already mature at run_at; this root separation is not "
                    "prospective blinding or an independent-custodian guarantee"
                ),
            },
        )

    # Publish the prediction commitment first. A second-root failure can leave
    # a recoverable packet-only run, but never an orphaned label vault.
    run_atomic_output(args.output_root, write_complete)
    run_atomic_output(args.outcome_vault_output_root, write_vault)
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
