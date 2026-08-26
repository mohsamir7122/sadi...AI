"""Saudi-first, fail-closed research entrypoint."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .benchmarks import SaudiBenchmarkRegistry
from .calendar import SaudiTradingCalendar
from .config import MAIN_MARKET, SAUDI_MARKET
from .identity import SaudiSecurityMaster
from .sources import SAUDI_SOURCES


class SaudiResearchEngine:
    """Compose the canonical KU-BO runtime with Saudi market contracts."""

    def __init__(self, *, security_master: SaudiSecurityMaster, calendar: SaudiTradingCalendar | None = None, benchmarks: SaudiBenchmarkRegistry | None = None):
        self.security_master = security_master
        self.calendar = calendar or SaudiTradingCalendar()
        self.benchmarks = benchmarks or SaudiBenchmarkRegistry()

    def snapshot(self, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET, benchmark_code: str = "TASI") -> dict[str, Any]:
        session = self.calendar.session_for(as_of, segment=segment)
        members = self.security_master.members_on(as_of=as_of, known_at=known_at, segment=segment)
        benchmark = self.benchmarks.get(benchmark_code, as_of=as_of)
        blocked: list[str] = []
        if not session.is_trading_day:
            blocked.append("NON_TRADING_SESSION")
        if not members:
            blocked.append("EMPTY_OR_UNVERIFIED_UNIVERSE")
        return {
            "market": SAUDI_MARKET.market_id,
            "currency": SAUDI_MARKET.currency,
            "timezone": SAUDI_MARKET.timezone,
            "segment": segment,
            "as_of": as_of.isoformat(),
            "known_at": known_at.isoformat(),
            "session": {"is_trading_day": session.is_trading_day, "closed_reason": session.closed_reason},
            "benchmark": {"code": benchmark.code, "scope": benchmark.scope},
            "universe_size": len(members),
            "source_states": {source.source_id: source.state for source in SAUDI_SOURCES},
            "status": "ABSTAIN" if blocked else "READY_FOR_EVIDENCE",
            "blocked_reasons": blocked,
        }
