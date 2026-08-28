"""Effective-dated Saudi security master with official-code joins."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from ..base import SecurityIdentity
from ...foundation_io import safe_regular_file
from .config import MAIN_MARKET, NOMU, ORDINARY_EQUITY


SAUDI_CODE_RE = re.compile(r"^[0-9]{4}$")
ISIN_RE = re.compile(r"^SA[A-Z0-9]{9}[0-9]$")
ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_IDENTITY_FIELDS = {
    "security_id",
    "official_code",
    "isin",
    "symbol_en",
    "symbol_ar",
    "issuer_id",
    "segment",
    "instrument_type",
    "valid_from",
    "valid_to",
    "known_from",
    "known_to",
    "tradable",
}


def _aware(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO timestamp string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _utc(value: datetime) -> datetime:
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValueError("identity timestamp is outside the supported UTC range") from exc


def _valid_isin(value: str) -> bool:
    if not ISIN_RE.fullmatch(value):
        return False
    expanded = "".join(
        str(ord(character) - ord("A") + 10)
        if "A" <= character <= "Z"
        else character
        for character in value
    )
    checksum = 0
    for index, character in enumerate(reversed(expanded)):
        digit = int(character)
        if index % 2 == 1:
            digit *= 2
        checksum += digit // 10 + digit % 10
    return checksum % 10 == 0


def _identity_date(value: object, field: str) -> date:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        raise ValueError(f"{field} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date string") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must be a canonical ISO date string")
    return parsed


def _text(value: object, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _valid_intervals_overlap(
    left: "SaudiSecurityRecord", right: "SaudiSecurityRecord"
) -> bool:
    return not (
        left.valid_to is not None and left.valid_to < right.valid_from
    ) and not (
        right.valid_to is not None and right.valid_to < left.valid_from
    )


def _knowledge_intervals_overlap(
    left: "SaudiSecurityRecord", right: "SaudiSecurityRecord"
) -> bool:
    return (
        left.known_to is None or _utc(right.known_from) < _utc(left.known_to)
    ) and (
        right.known_to is None or _utc(left.known_from) < _utc(right.known_to)
    )


@dataclass(frozen=True)
class SaudiSecurityRecord(SecurityIdentity):
    """One date-valid, knowledge-valid listing identity."""

    def __post_init__(self) -> None:
        for field, value in (
            ("security_id", self.security_id),
            ("official_code", self.official_code),
            ("symbol_en", self.symbol_en),
            ("issuer_id", self.issuer_id),
            ("segment", self.segment),
            ("instrument_type", self.instrument_type),
        ):
            _text(value, field)
        if self.isin is not None and not isinstance(self.isin, str):
            raise ValueError("isin must be a string or null")
        if self.symbol_ar is not None and not isinstance(self.symbol_ar, str):
            raise ValueError("symbol_ar must be a string or null")
        if type(self.valid_from) is not date or (
            self.valid_to is not None and type(self.valid_to) is not date
        ):
            raise ValueError("identity validity boundaries must be dates")
        if (
            not isinstance(self.known_from, datetime)
            or self.known_from.tzinfo is None
            or self.known_from.utcoffset() is None
        ):
            raise ValueError("known_from must be timezone-aware")
        if self.known_to is not None and (
            not isinstance(self.known_to, datetime)
            or self.known_to.tzinfo is None
            or self.known_to.utcoffset() is None
        ):
            raise ValueError("known_to must be timezone-aware")
        if not isinstance(self.tradable, bool):
            raise ValueError("tradable must be a boolean")
        if not SAUDI_CODE_RE.fullmatch(self.official_code):
            raise ValueError("official_code must be a four-digit Saudi Exchange code")
        if self.isin is not None and not _valid_isin(self.isin):
            raise ValueError(
                "isin must be a checksum-valid 12-character Saudi ISIN when provided"
            )
        if self.segment not in {MAIN_MARKET, NOMU}:
            raise ValueError("segment must be MAIN or NOMU")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to precedes valid_from")
        if self.known_to is not None and _utc(self.known_to) <= _utc(self.known_from):
            raise ValueError("known_to must follow known_from")

    def is_valid(self, *, as_of: date, known_at: datetime) -> bool:
        """Use inclusive valid dates and a half-open knowledge interval."""

        if type(as_of) is not date:
            raise ValueError("identity as_of must be a date")
        if (
            not isinstance(known_at, datetime)
            or known_at.tzinfo is None
            or known_at.utcoffset() is None
        ):
            raise ValueError("identity known_at must be timezone-aware")
        if as_of < self.valid_from or (
            self.valid_to is not None and as_of > self.valid_to
        ):
            return False
        return _utc(self.known_from) <= _utc(known_at) and (
            self.known_to is None or _utc(known_at) < _utc(self.known_to)
        )


class SaudiSecurityMaster:
    def __init__(self, records: list[SaudiSecurityRecord] | tuple[SaudiSecurityRecord, ...] = ()):
        self._records: list[SaudiSecurityRecord] = []
        for record in records:
            self.add(record)

    def add(self, record: SaudiSecurityRecord) -> None:
        if not isinstance(record, SaudiSecurityRecord):
            raise TypeError("SaudiSecurityMaster accepts SaudiSecurityRecord values")
        for existing in self._records:
            if not (
                _valid_intervals_overlap(existing, record)
                and _knowledge_intervals_overlap(existing, record)
            ):
                continue
            if existing.security_id == record.security_id:
                raise ValueError("overlapping security_id bitemporal intervals")
            if (
                existing.official_code == record.official_code
                and existing.segment == record.segment
            ):
                raise ValueError("overlapping official-code bitemporal intervals")
            if (
                existing.isin is not None
                and record.isin is not None
                and existing.isin == record.isin
            ):
                raise ValueError("overlapping ISIN bitemporal intervals")
        self._records.append(record)

    def membership_on(self, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET) -> tuple[SaudiSecurityRecord, ...]:
        """Return the Point-in-Time denominator, including suspended members."""

        return tuple(
            record
            for record in self._records
            if record.segment == segment and record.is_valid(as_of=as_of, known_at=known_at)
        )

    def selectable_on(self, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET) -> tuple[SaudiSecurityRecord, ...]:
        if segment != MAIN_MARKET:
            return ()
        return tuple(
            record
            for record in self.membership_on(as_of=as_of, known_at=known_at, segment=segment)
            if record.instrument_type == ORDINARY_EQUITY and record.tradable
        )

    # Compatibility alias: historically members_on meant the selectable set.
    # Denominator consumers must opt into membership_on explicitly.
    def members_on(self, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET) -> tuple[SaudiSecurityRecord, ...]:
        return self.selectable_on(as_of=as_of, known_at=known_at, segment=segment)

    def _resolve_from(self, records: tuple[SaudiSecurityRecord, ...], official_code: str, *, isin: str | None = None) -> SaudiSecurityRecord:
        matches = [record for record in records if record.official_code == official_code]
        if isin is not None:
            matches = [record for record in matches if record.isin == isin]
        if len(matches) != 1:
            raise LookupError("official code did not resolve to exactly one date-valid Saudi security")
        return matches[0]

    def resolve_member(self, official_code: str, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET, isin: str | None = None) -> SaudiSecurityRecord:
        return self._resolve_from(
            self.membership_on(as_of=as_of, known_at=known_at, segment=segment),
            official_code,
            isin=isin,
        )

    def resolve_selectable(self, official_code: str, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET, isin: str | None = None) -> SaudiSecurityRecord:
        return self._resolve_from(
            self.selectable_on(as_of=as_of, known_at=known_at, segment=segment),
            official_code,
            isin=isin,
        )

    def resolve(self, official_code: str, *, as_of: date, known_at: datetime, segment: str = MAIN_MARKET, isin: str | None = None) -> SaudiSecurityRecord:
        return self.resolve_selectable(
            official_code, as_of=as_of, known_at=known_at, segment=segment, isin=isin
        )

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
            for record in self.membership_on(
                as_of=as_of, known_at=known_at, segment=segment
            )
        ]


def saudi_security_record_from_mapping(payload: Mapping[str, Any]) -> SaudiSecurityRecord:
    if not isinstance(payload, Mapping) or set(payload) != _IDENTITY_FIELDS:
        raise ValueError("identity entry fields mismatch")
    valid_from = _identity_date(payload["valid_from"], "valid_from")
    valid_to = (
        None
        if payload["valid_to"] is None
        else _identity_date(payload["valid_to"], "valid_to")
    )
    known_from = _aware(payload["known_from"], "known_from")
    known_to = None if payload["known_to"] is None else _aware(payload["known_to"], "known_to")
    if not isinstance(payload["tradable"], bool):
        raise ValueError("tradable must be a boolean")
    isin = payload["isin"]
    if isin is not None:
        isin = _text(isin, "isin")
    symbol_ar = payload["symbol_ar"]
    if symbol_ar is not None:
        symbol_ar = _text(symbol_ar, "symbol_ar")
    return SaudiSecurityRecord(
        security_id=_text(payload["security_id"], "security_id"),
        official_code=_text(payload["official_code"], "official_code"),
        isin=isin,
        symbol_en=_text(payload["symbol_en"], "symbol_en"),
        symbol_ar=symbol_ar,
        issuer_id=_text(payload["issuer_id"], "issuer_id"),
        segment=_text(payload["segment"], "segment"),
        instrument_type=_text(payload["instrument_type"], "instrument_type"),
        valid_from=valid_from,
        valid_to=valid_to,
        known_from=known_from,
        known_to=known_to,
        tradable=payload["tradable"],
    )


def saudi_security_master_from_bytes(content: bytes) -> SaudiSecurityMaster:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"identity file contains duplicate key: {key}")
            value[key] = item
        return value

    try:
        payload: Any = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"identity file contains non-finite JSON: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("identity file must be strict UTF-8 JSON") from exc
    if not isinstance(payload, list):
        raise ValueError("identity file must contain an array")
    return SaudiSecurityMaster(
        tuple(saudi_security_record_from_mapping(item) for item in payload)
    )


def load_saudi_security_master(path: Path) -> SaudiSecurityMaster:
    return saudi_security_master_from_bytes(
        safe_regular_file(path, field="Saudi identity file")
    )


__all__ = [
    "SaudiSecurityMaster",
    "SaudiSecurityRecord",
    "load_saudi_security_master",
    "saudi_security_master_from_bytes",
    "saudi_security_record_from_mapping",
]
