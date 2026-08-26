"""Command-line entry point for the governed Saudi post-open scan."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

from .atomic_output import run_atomic_output
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


def _load_jsonl(path: Path):
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload: Any = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"observation line {line_number} must be an object")
        rows.append(post_open_observation_from_mapping(payload))
    return tuple(rows)


def _load_weights(path: Path) -> dict[Horizon, dict[str, float]]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {item.value for item in ALL_HORIZONS}:
        raise ValueError("weights must contain exactly the five governed horizons")
    result: dict[Horizon, dict[str, float]] = {}
    for horizon in ALL_HORIZONS:
        values = payload[horizon.value]
        if not isinstance(values, dict):
            raise ValueError(f"{horizon.value} weights must be an object")
        result[horizon] = {str(key): float(value) for key, value in values.items()}
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rank Saudi research candidates after open plus thirty minutes"
    )
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--scan-at", type=_timestamp, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--maximum-market-age-minutes", type=int, default=15)
    parser.add_argument("--minimum-turnover-sar", type=float, default=0.0)
    parser.add_argument("--maximum-candidates-per-horizon", type=int, default=25)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scanner = SaudiPostOpenScanner(
        maximum_market_age=timedelta(minutes=args.maximum_market_age_minutes),
        minimum_turnover_sar=args.minimum_turnover_sar,
    )
    report = scanner.scan(
        _load_jsonl(args.observations),
        scan_at=args.scan_at,
        horizon_weights=_load_weights(args.weights),
        maximum_candidates_per_horizon=args.maximum_candidates_per_horizon,
    )

    def write(staging: Path) -> None:
        (staging / "post_open_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    run_atomic_output(args.output_root, write)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "RESEARCH_CANDIDATES_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
