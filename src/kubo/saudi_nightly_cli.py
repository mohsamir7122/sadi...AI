"""Command-line entry point for the governed Saudi nightly laboratory."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .atomic_output import run_atomic_output
from .saudi_capabilities.nightly_lab import (
    evaluate_sealed_holdout,
    historical_event_from_mapping,
    prepare_nightly_run,
)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone offset")
    return parsed


def _load_events(path: Path):
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload: Any = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"event line {line_number} must be an object")
        events.append(historical_event_from_mapping(payload))
    return tuple(events)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a Point-in-Time Saudi ten-year event laboratory"
    )
    parser.add_argument("--events", type=Path, required=True, help="authorized event JSONL")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-at", type=_timestamp, required=True)
    parser.add_argument("--lookback-years", type=int, default=10)
    parser.add_argument("--minimum-primary", type=int, default=50)
    parser.add_argument("--minimum-probe", type=int, default=300)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    events = _load_events(args.events)
    prepared = prepare_nightly_run(
        events,
        run_id=args.run_id,
        run_at=args.run_at,
        lookback_years=args.lookback_years,
        minimum_primary=args.minimum_primary,
        minimum_probe=args.minimum_probe,
    )
    if prepared.status == "STOP_TRAINING":
        report = {
            "status": prepared.status,
            "run_id": args.run_id,
            "run_at": args.run_at.isoformat(),
            "counts": dict(prepared.counts),
            "reasons": list(prepared.reasons),
            "model_updated": False,
            "final_holdout_scored": False,
            "recommendation": None,
        }

        def write_stop(staging: Path) -> None:
            _write_json(staging / "run_receipt.json", report)

        run_atomic_output(args.output_root, write_stop)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 2

    if prepared.split is None or prepared.model is None or prepared.sealed_packet is None:
        raise RuntimeError("nightly preparation returned incomplete artifacts")
    evaluation = evaluate_sealed_holdout(
        prepared.sealed_packet,
        prepared.split.outcome_vault,
        scored_at=args.run_at,
    )
    receipt = {
        "status": "COMPLETE",
        "run_id": args.run_id,
        "run_at": args.run_at.isoformat(),
        "counts": dict(prepared.counts),
        "split_counts": {
            "training": len(prepared.split.training),
            "validation": len(prepared.split.validation),
            "final_holdout": len(prepared.split.blind_holdout),
        },
        "stage_order": [
            "COHORT_COUNT_GATE",
            "TRAINING_FIT",
            "VALIDATION_CALIBRATION",
            "FINAL_HOLDOUT_PREDICTIONS_SEALED",
            "FINAL_HOLDOUT_OUTCOMES_SCORED",
        ],
        "model_fingerprint": prepared.model.fingerprint,
        "seal_sha256": prepared.sealed_packet.seal_sha256,
        "outcome_vault_sha256": prepared.split.outcome_vault.vault_sha256,
        "recommendation": None,
        "execution": None,
        "claim_boundary": "Historical research only; no live trading or accuracy claim",
    }
    horizon_weight_export = {
        item.horizon.value: {factor_id: weight for factor_id, weight in item.weights}
        for item in prepared.model.horizon_weights
    }

    def write_complete(staging: Path) -> None:
        _write_json(staging / "model.json", prepared.model.to_dict())
        _write_json(staging / "horizon_weights.json", horizon_weight_export)
        _write_json(staging / "sealed_predictions.json", prepared.sealed_packet.to_dict())
        _write_json(staging / "final_holdout_report.json", evaluation)
        _write_json(staging / "run_receipt.json", receipt)

    run_atomic_output(args.output_root, write_complete)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
