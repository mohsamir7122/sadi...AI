"""Effective-dated Saudi Exchange sessions.

Weekends are deterministic.  Official holidays must be supplied as a dated
mapping; Eid closures are never inferred from civil or Hijri calculations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import MAIN_MARKET, RIYADH_TZ, SAUDI_MARKET


@dataclass(frozen=True)
class SessionPhase:
    name: str
    start: datetime
    end: datetime
    executable: bool


@dataclass(frozen=True)
class SaudiSession:
    session_date: date
    segment: str
    is_trading_day: bool
    phases: tuple[SessionPhase, ...]
    closed_reason: str | None
    source_id: str

    @property
    def timezone(self) -> str:
        return RIYADH_TZ


class SaudiTradingCalendar:
    """Calendar with explicit official holiday overrides and no silent fallback."""

    def __init__(self, *, holidays: dict[date, str] | None = None, source_id: str = "saudi_exchange_official"):
        self.holidays = dict(holidays or {})
        self.source_id = source_id
        self._tz = ZoneInfo(RIYADH_TZ)

    def session_for(self, session_date: date, *, segment: str = MAIN_MARKET) -> SaudiSession:
        if session_date in self.holidays:
            return SaudiSession(session_date, segment, False, (), self.holidays[session_date], self.source_id)
        # Saudi Exchange's regular week is Sunday through Thursday; Friday
        # and Saturday are closed (Python weekday: Monday=0, Sunday=6).
        if session_date.weekday() in {4, 5}:
            return SaudiSession(session_date, segment, False, (), "WEEKEND", self.source_id)
        def at(value: time) -> datetime:
            return datetime.combine(session_date, value, tzinfo=self._tz)
        phases = (
            SessionPhase("OPENING_AUCTION", at(SAUDI_MARKET.opening_auction_start), at(SAUDI_MARKET.opening_auction_end), False),
            SessionPhase("CONTINUOUS_TRADING", at(SAUDI_MARKET.continuous_start), at(SAUDI_MARKET.continuous_end), True),
            SessionPhase("CLOSING_AUCTION", at(SAUDI_MARKET.continuous_end), at(SAUDI_MARKET.closing_auction_end), True),
            SessionPhase("TRADE_AT_LAST", at(SAUDI_MARKET.closing_auction_end), at(SAUDI_MARKET.trade_at_last_end), True),
        )
        return SaudiSession(session_date, segment, True, phases, None, self.source_id)

    def next_session(self, after: date, *, segment: str = MAIN_MARKET) -> SaudiSession:
        current = after + timedelta(days=1)
        for _ in range(370):
            candidate = self.session_for(current, segment=segment)
            if candidate.is_trading_day:
                return candidate
            current += timedelta(days=1)
        raise RuntimeError("no Saudi Exchange session found within one year")

    def require_aware_riyadh(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        normalized = value.astimezone(self._tz)
        if normalized.tzinfo is None:
            raise ValueError("timestamp cannot be normalized to Asia/Riyadh")
        return normalized
