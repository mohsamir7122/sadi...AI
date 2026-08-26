"""Shared contracts for market adapters.

The contracts intentionally make market, segment, identity, time, authority,
and rights explicit.  A provider implementation may be incomplete, but it
cannot silently masquerade as an official live source.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, Sequence


class MarketContractError(ValueError):
    """Raised when a market contract is ambiguous or internally inconsistent."""


@dataclass(frozen=True)
class MarketConfig:
    market_id: str
    display_name: str
    currency: str
    timezone: str
    primary_benchmark: str
    default_segment: str
    active: bool = True

    def __post_init__(self) -> None:
        if not self.market_id or not self.display_name:
            raise MarketContractError("market_id and display_name are required")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise MarketContractError("currency must be a three-letter uppercase code")
        if not self.timezone or not self.primary_benchmark or not self.default_segment:
            raise MarketContractError("timezone, benchmark, and segment are required")


@dataclass(frozen=True)
class SecurityIdentity:
    security_id: str
    official_code: str
    isin: str | None
    symbol_en: str
    symbol_ar: str | None
    issuer_id: str
    segment: str
    instrument_type: str
    valid_from: date
    valid_to: date | None
    known_from: datetime
    known_to: datetime | None
    tradable: bool

    def is_valid(self, *, as_of: date, known_at: datetime) -> bool:
        if as_of < self.valid_from or (self.valid_to and as_of > self.valid_to):
            return False
        if known_at < self.known_from or (self.known_to and known_at > self.known_to):
            return False
        return True


@dataclass(frozen=True)
class MarketSource:
    source_id: str
    provider: str
    canonical_url: str
    authority_tier: int
    independence_group: str
    access_mode: str
    latency_class: str
    rights_requirement: str
    state: str = "DEFINED_ONLY"

    def __post_init__(self) -> None:
        if self.authority_tier not in range(1, 8):
            raise MarketContractError("authority_tier must be between 1 and 7")
        if not self.canonical_url.startswith("https://"):
            raise MarketContractError("source URLs must be HTTPS")
        if self.state not in {"DEFINED_ONLY", "ADMITTED", "RETIRED"}:
            raise MarketContractError("unknown source state")
        if self.latency_class not in {"REAL_TIME", "DELAYED", "END_OF_DAY", "UNKNOWN"}:
            raise MarketContractError("unknown latency class")


class UniverseProvider(Protocol):
    def members_on(self, *, as_of: date, known_at: datetime, segment: str) -> Sequence[SecurityIdentity]: ...


class MarketCalendarProvider(Protocol):
    def session_for(self, session_date: date): ...


class BenchmarkProvider(Protocol):
    def get(self, code: str, *, as_of: date): ...
