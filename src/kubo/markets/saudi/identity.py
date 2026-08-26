"""Effective-dated Saudi security master with official-code joins."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from ..base import SecurityIdentity
from .config import MAIN_MARKET, NOMU


SAUDI_CODE_RE = re.compile(r"^[0-9]{4}$")
ISIN_RE = re.compile(r"^SA[A-Z0-9]{10}$")


@dataclass(frozen=True)
class SaudiSecurityRecord(SecurityIdentity):
    """One date-valid, knowledge-valid listing identity."""

    def __post_init__(self) -> None:
        if not SAUDI_CODE_RE.fullmatch(self.official_code):
            raise ValueError("official_code must be a four-digit Saudi Exchange code")
        if self.isin is not None and not ISIN_RE.fullmatch(self.isin):
            raise ValueError("isin must be a 12-character Saudi ISIN when provided")
        if self.segment not in {MAIN_MARKET, NOMU}:
            raise ValueError("segment must be MAIN or NOMU")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to precedes valid_from")
        if self.known_to is not None and self.known_to < self.known_from:
            raise ValueError("known_to precedes known_from")
        if not self.symbol_en.strip() or not self.issuer_id.strip() or not self.security_id.strip():
            raise ValueError("security_id, issuer_id, and symbol_en are required")


class SaudiSecurityMaster:
    def __init__(self, records: list[SaudiSecurityRecord] | tuple[SaudiSecurityRecord, ...] = ()):
        self._records: list[SaudiSecurityRecord] = []
        for record in records:
            self.add(record)

    def add(self, record: SaudiSecurityRecord) -> None:
        for existing in self._records:
            if existing.security_id == record.security_id and existing.valid_from == record.valid_from:
                raise ValueError("duplicate security identity interval")
            if existing.official_code == record.official_code and existing.segment == record.segment:
                if not (record.valid_to and record.valid_to < existing.valid_from) and not (existing.valid_to and existing.valid_to < record.valid_from):
                    raise ValueError("overlapping official-code identity intervals")
        self._records.append(record)

    def members_on(self, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET) -> tuple[SaudiSecurityRecord, ...]:
        return tuple(record for record in self._records if record.segment == segment and record.tradable and record.is_valid(as_of=as_of, known_at=known_at))

    def resolve(self, official_code: str, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET, isin: str | None = None) -> SaudiSecurityRecord:
        matches = [record for record in self.members_on(as_of=as_of, known_at=known_at, segment=segment) if record.official_code == official_code]
        if isin is not None:
            matches = [record for record in matches if record.isin == isin]
        if len(matches) != 1:
            raise LookupError("official code did not resolve to exactly one date-valid Saudi security")
        return matches[0]

    def as_rows(self, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET) -> list[dict[str, object]]:
        return [
            {
                "security_id": record.security_id,
                "issuer_id": record.issuer_id,
                "official_code": record.official_code,
                "isin": record.isin,
                "symbol_en": record.symbol_en,
                "symbol_ar": record.symbol_ar,
                "segment": record.segment,
                "instrument_type": record.instrument_type,
                "valid_from": record.valid_from.isoformat(),
                "valid_to": record.valid_to.isoformat() if record.valid_to else None,
                "known_from": record.known_from.isoformat(),
                "known_to": record.known_to.isoformat() if record.known_to else None,
                "tradable": record.tradable,
            }
            for record in self.members_on(as_of=as_of, known_at=known_at, segment=segment)
        ]
