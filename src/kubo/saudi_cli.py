"""Small, explicit Saudi CLI; it never fetches data or places orders."""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Any

from .markets.saudi.calendar import SaudiTradingCalendar, load_saudi_calendar_revision
from .markets.saudi.engine import SaudiResearchEngine
from .markets.saudi.identity import SaudiSecurityMaster, load_saudi_security_master


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("known-at must include a timezone offset")
    return parsed


def _parse_date(value: str) -> date:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise argparse.ArgumentTypeError("date must use canonical YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "date must use canonical YYYY-MM-DD"
        ) from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("date must use canonical YYYY-MM-DD")
    return parsed


def _load_master(path: Path | None) -> SaudiSecurityMaster:
    if path is None:
        return SaudiSecurityMaster()
    return load_saudi_security_master(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Saudi Exchange fail-closed research snapshot")
    parser.add_argument("--as-of", type=_parse_date, required=True, help="session date (YYYY-MM-DD)")
    parser.add_argument("--known-at", type=_parse_datetime, required=True, help="Point-in-Time knowledge cutoff")
    parser.add_argument("--identity-file", type=Path, help="authorized/effective-dated identity fixture")
    parser.add_argument("--calendar-file", type=Path, help="effective-dated calendar revision")
    parser.add_argument("--benchmark", default="TASI")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    calendar = SaudiTradingCalendar(
        revision=(
            load_saudi_calendar_revision(args.calendar_file, known_at=args.known_at)
            if args.calendar_file
            else None
        )
    )
    engine = SaudiResearchEngine(
        security_master=_load_master(args.identity_file),
        calendar=calendar,
    )
    print(json.dumps(engine.snapshot(as_of=args.as_of, known_at=args.known_at, benchmark_code=args.benchmark), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
