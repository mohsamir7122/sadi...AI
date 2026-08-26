"""Small, explicit Saudi CLI; it never fetches data or places orders."""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from .markets.saudi.engine import SaudiResearchEngine
from .markets.saudi.identity import SaudiSecurityMaster, SaudiSecurityRecord


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("known-at must include a timezone offset")
    return parsed


def _load_master(path: Path | None) -> SaudiSecurityMaster:
    if path is None:
        return SaudiSecurityMaster()
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("identity file must contain an array")
    records = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("identity entries must be objects")
        for field in ("valid_from", "valid_to"):
            if item.get(field):
                item[field] = date.fromisoformat(item[field])
        for field in ("known_from", "known_to"):
            if item.get(field):
                item[field] = _parse_datetime(item[field])
        records.append(SaudiSecurityRecord(**item))
    return SaudiSecurityMaster(records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Saudi Exchange fail-closed research snapshot")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True, help="session date (YYYY-MM-DD)")
    parser.add_argument("--known-at", type=_parse_datetime, required=True, help="Point-in-Time knowledge cutoff")
    parser.add_argument("--identity-file", type=Path, help="authorized/effective-dated identity fixture")
    parser.add_argument("--benchmark", default="TASI")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = SaudiResearchEngine(security_master=_load_master(args.identity_file))
    print(json.dumps(engine.snapshot(as_of=args.as_of, known_at=args.known_at, benchmark_code=args.benchmark), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
