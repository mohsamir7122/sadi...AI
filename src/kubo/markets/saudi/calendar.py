"""Effective-dated, fail-closed Saudi Exchange session calendar."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from ...foundation_io import safe_regular_file, strict_json_object
from .config import MAIN_MARKET, RIYADH_TZ


CALENDAR_COVERAGE_MISSING = "CALENDAR_COVERAGE_MISSING"
CALENDAR_REVISION_NOT_KNOWN = "CALENDAR_REVISION_NOT_KNOWN_AT_CUTOFF"
MAX_BOUNDARY_UNCERTAINTY_SECONDS = 300
MAX_CALENDAR_COVERAGE_DAYS = 4_100
MAX_HOLIDAY_CLOSURE_DAYS = 62
MAX_HOLIDAY_CLOSURES = 512
MIN_SUPPORTED_WEEKEND_REGIME_DATE = date(2013, 6, 29)
_REVISION_FIELDS = {
    "schema_version",
    "revision_id",
    "market",
    "segment",
    "timezone",
    "coverage_from",
    "coverage_through",
    "known_from",
    "known_to",
    "source_id",
    "source_url",
    "boundary_uncertainty_seconds",
    "evidence_class",
    "schedule",
    "holidays",
}
_HOLIDAY_FIELDS = {"closed_from", "closed_through", "resume_on", "reason"}
_SCHEDULE_FIELDS = {"effective_from", "effective_through", "phases"}
_PHASE_FIELDS = {"name", "start", "end", "executable"}
_PHASE_TEMPLATE = (
    ("OPENING_AUCTION", False),
    ("CONTINUOUS_TRADING", True),
    ("CLOSING_AUCTION", True),
    ("TRADE_AT_LAST", True),
)
_ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_WALL_TIME_RE = re.compile(r"^[0-9]{2}:[0-9]{2}:[0-9]{2}$")


def _aware(value: str, field: str) -> datetime:
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
        raise ValueError("calendar timestamp is outside the supported UTC range") from exc


def _calendar_time(value: object, field: str) -> time:
    if not isinstance(value, str) or not _WALL_TIME_RE.fullmatch(value):
        raise ValueError(f"{field} must use HH:MM:SS")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must use HH:MM:SS") from exc
    if (
        parsed.tzinfo is not None
        or parsed.second != 0
        or parsed.microsecond != 0
        or parsed.isoformat(timespec="seconds") != value
    ):
        raise ValueError(f"{field} must be a whole-minute local wall time")
    return parsed


def _calendar_date(value: object, field: str) -> date:
    if not isinstance(value, str) or not _ISO_DATE_RE.fullmatch(value):
        raise ValueError(f"{field} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date string") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must be a canonical ISO date string")
    return parsed


def _https_url(value: object, field: str) -> str:
    text = _required_text(value, field)
    if any(character.isspace() for character in text):
        raise ValueError(f"{field} must be a valid HTTPS URL")
    try:
        parsed = urlsplit(text)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid HTTPS URL") from exc
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"{field} must be a valid HTTPS URL")
    return text


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _next_saudi_weekday(value: date) -> date:
    try:
        candidate = value + timedelta(days=1)
        while candidate.weekday() in {4, 5}:
            candidate += timedelta(days=1)
    except OverflowError as exc:
        raise ValueError("calendar holiday has no representable resume date") from exc
    return candidate


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
    coverage_known: bool
    calendar_revision_id: str | None
    boundary_uncertainty_seconds: int
    resume_on: date | None

    @property
    def timezone(self) -> str:
        return RIYADH_TZ


@dataclass(frozen=True)
class SaudiSessionPhaseTemplate:
    name: str
    start: time
    end: time
    executable: bool


@dataclass(frozen=True)
class SaudiSessionSchedule:
    effective_from: date
    effective_through: date | None
    phases: tuple[SaudiSessionPhaseTemplate, ...]

    def applies_on(self, session_date: date) -> bool:
        return self.effective_from <= session_date and (
            self.effective_through is None or session_date <= self.effective_through
        )


@dataclass(frozen=True)
class SaudiHolidayClosure:
    closed_from: date
    closed_through: date
    resume_on: date
    reason: str

    def contains(self, session_date: date) -> bool:
        return self.closed_from <= session_date <= self.closed_through


@dataclass(frozen=True)
class SaudiCalendarRevision:
    revision_id: str
    coverage_from: date
    coverage_through: date
    known_from: datetime
    known_to: datetime | None
    source_id: str
    source_url: str
    boundary_uncertainty_seconds: int
    evidence_class: str
    schedule: SaudiSessionSchedule
    holiday_closures: tuple[SaudiHolidayClosure, ...]
    holidays: Mapping[date, str]
    content_sha256: str

    def known_at(self, instant: datetime) -> bool:
        if (
            not isinstance(instant, datetime)
            or instant.tzinfo is None
            or instant.utcoffset() is None
        ):
            raise ValueError("calendar knowledge cutoff must be timezone-aware")
        return _utc(self.known_from) <= _utc(instant) and (
            self.known_to is None or _utc(instant) < _utc(self.known_to)
        )

    def closure_on(self, session_date: date) -> SaudiHolidayClosure | None:
        for closure in self.holiday_closures:
            if closure.contains(session_date):
                return closure
        return None


def calendar_revision_from_mapping(
    payload: Mapping[str, Any], *, known_at: datetime
) -> SaudiCalendarRevision:
    if not isinstance(payload, Mapping) or set(payload) != _REVISION_FIELDS:
        raise ValueError("calendar revision fields mismatch")
    if payload["schema_version"] != "1.0":
        raise ValueError("unsupported Saudi calendar revision schema")
    if payload["market"] != "SAUDI_EXCHANGE" or payload["segment"] != MAIN_MARKET:
        raise ValueError("calendar revision must cover Saudi Main Market")
    if payload["timezone"] != RIYADH_TZ:
        raise ValueError("calendar revision timezone must be Asia/Riyadh")
    revision_id = _required_text(payload["revision_id"], "calendar revision_id")
    source_id = _required_text(payload["source_id"], "calendar source_id")
    source_url = _https_url(payload["source_url"], "calendar source_url")
    coverage_from = _calendar_date(payload["coverage_from"], "coverage_from")
    coverage_through = _calendar_date(payload["coverage_through"], "coverage_through")
    if coverage_from > coverage_through:
        raise ValueError("calendar coverage_from follows coverage_through")
    if coverage_from < MIN_SUPPORTED_WEEKEND_REGIME_DATE:
        raise ValueError(
            "calendar coverage predates the supported Friday/Saturday weekend regime"
        )
    if (coverage_through - coverage_from).days > MAX_CALENDAR_COVERAGE_DAYS:
        raise ValueError("calendar coverage exceeds the governed maximum span")
    known_from = _aware(payload["known_from"], "calendar known_from")
    known_to_value = payload["known_to"]
    known_to = None if known_to_value is None else _aware(known_to_value, "calendar known_to")
    if known_to is not None and _utc(known_to) <= _utc(known_from):
        raise ValueError("calendar known_to must follow known_from")
    if not isinstance(known_at, datetime) or known_at.tzinfo is None or known_at.utcoffset() is None:
        raise ValueError("known_at must be timezone-aware")
    if not (
        _utc(known_from) <= _utc(known_at)
        and (known_to is None or _utc(known_at) < _utc(known_to))
    ):
        raise ValueError("calendar revision was not known at the decision cutoff")
    uncertainty = payload["boundary_uncertainty_seconds"]
    if (
        isinstance(uncertainty, bool)
        or not isinstance(uncertainty, int)
        or not 0 <= uncertainty <= MAX_BOUNDARY_UNCERTAINTY_SECONDS
    ):
        raise ValueError(
            "boundary_uncertainty_seconds must be an integer between 0 and 300"
        )
    evidence_class = payload["evidence_class"]
    if not isinstance(evidence_class, str):
        raise ValueError("calendar evidence_class must be a string")
    if evidence_class not in {"SYNTHETIC_ONLY", "RECORDED_AUTHORIZED_FIXTURE"}:
        raise ValueError("calendar evidence_class is invalid")

    raw_schedule = payload["schedule"]
    if not isinstance(raw_schedule, Mapping) or set(raw_schedule) != _SCHEDULE_FIELDS:
        raise ValueError("calendar schedule fields mismatch")
    schedule_from = _calendar_date(
        raw_schedule["effective_from"], "schedule effective_from"
    )
    raw_schedule_through = raw_schedule["effective_through"]
    schedule_through = (
        None
        if raw_schedule_through is None
        else _calendar_date(raw_schedule_through, "schedule effective_through")
    )
    if schedule_through is not None and schedule_through < schedule_from:
        raise ValueError("schedule effective_through precedes effective_from")
    if coverage_from < schedule_from or (
        schedule_through is not None and coverage_through > schedule_through
    ):
        raise ValueError("calendar coverage exceeds the effective session schedule")
    raw_phases = raw_schedule["phases"]
    if not isinstance(raw_phases, list) or len(raw_phases) != len(_PHASE_TEMPLATE):
        raise ValueError("calendar schedule requires exactly four session phases")
    phases: list[SaudiSessionPhaseTemplate] = []
    previous_end: time | None = None
    for index, ((expected_name, expected_executable), item) in enumerate(
        zip(_PHASE_TEMPLATE, raw_phases, strict=True)
    ):
        if not isinstance(item, Mapping) or set(item) != _PHASE_FIELDS:
            raise ValueError("calendar session phase fields mismatch")
        if item["name"] != expected_name or item["executable"] is not expected_executable:
            raise ValueError("calendar session phase template mismatch")
        start = _calendar_time(item["start"], f"schedule phases[{index}].start")
        end = _calendar_time(item["end"], f"schedule phases[{index}].end")
        if start >= end or (previous_end is not None and start != previous_end):
            raise ValueError("calendar session phases must be ordered and contiguous")
        phases.append(
            SaudiSessionPhaseTemplate(
                name=expected_name,
                start=start,
                end=end,
                executable=expected_executable,
            )
        )
        previous_end = end
    schedule = SaudiSessionSchedule(
        effective_from=schedule_from,
        effective_through=schedule_through,
        phases=tuple(phases),
    )

    raw_holidays = payload["holidays"]
    if not isinstance(raw_holidays, list):
        raise ValueError("calendar holidays must be an array")
    if len(raw_holidays) > MAX_HOLIDAY_CLOSURES:
        raise ValueError("calendar holidays exceed the governed maximum count")
    holidays: dict[date, str] = {}
    closures: list[SaudiHolidayClosure] = []
    for item in raw_holidays:
        if not isinstance(item, Mapping) or set(item) != _HOLIDAY_FIELDS:
            raise ValueError("calendar holiday fields mismatch")
        closed_from = _calendar_date(item["closed_from"], "holiday closed_from")
        closed_through = _calendar_date(
            item["closed_through"], "holiday closed_through"
        )
        resume_on = _calendar_date(item["resume_on"], "holiday resume_on")
        reason = _required_text(item["reason"], "calendar holiday reason")
        if closed_from > closed_through:
            raise ValueError("calendar holiday interval or resume_on is invalid")
        if (closed_through - closed_from).days + 1 > MAX_HOLIDAY_CLOSURE_DAYS:
            raise ValueError("calendar holiday closure exceeds the governed maximum span")
        if resume_on != _next_saudi_weekday(closed_through):
            raise ValueError("calendar holiday interval or resume_on is invalid")
        if (
            closed_from < coverage_from
            or closed_through > coverage_through
            or resume_on > coverage_through
        ):
            raise ValueError("calendar holiday falls outside revision coverage")
        current = closed_from
        while True:
            if current in holidays:
                raise ValueError("calendar holiday intervals overlap")
            holidays[current] = reason
            if current == closed_through:
                break
            current += timedelta(days=1)
        closures.append(
            SaudiHolidayClosure(
                closed_from=closed_from,
                closed_through=closed_through,
                resume_on=resume_on,
                reason=reason,
            )
        )
    if any(closure.resume_on in holidays for closure in closures):
        raise ValueError("calendar holiday resume_on is also marked closed")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return SaudiCalendarRevision(
        revision_id=revision_id,
        coverage_from=coverage_from,
        coverage_through=coverage_through,
        known_from=known_from,
        known_to=known_to,
        source_id=source_id,
        source_url=source_url,
        boundary_uncertainty_seconds=uncertainty,
        evidence_class=evidence_class,
        schedule=schedule,
        holiday_closures=tuple(
            sorted(closures, key=lambda item: (item.closed_from, item.closed_through))
        ),
        holidays=MappingProxyType(dict(holidays)),
        content_sha256=hashlib.sha256(canonical).hexdigest(),
    )


def calendar_revision_from_bytes(
    content: bytes, *, known_at: datetime
) -> SaudiCalendarRevision:
    return calendar_revision_from_mapping(
        strict_json_object(content, "Saudi calendar revision"),
        known_at=known_at,
    )


def load_saudi_calendar_revision(
    path: Path, *, known_at: datetime
) -> SaudiCalendarRevision:
    return calendar_revision_from_bytes(
        safe_regular_file(path, field="Saudi calendar revision"),
        known_at=known_at,
    )


class SaudiTradingCalendar:
    """Calendar that treats missing official coverage as unknown, never open."""

    def __init__(self, *, revision: SaudiCalendarRevision | None = None):
        self.revision = revision
        self._tz = ZoneInfo(RIYADH_TZ)

    def session_for(
        self,
        session_date: date,
        *,
        known_at: datetime,
        segment: str = MAIN_MARKET,
    ) -> SaudiSession:
        if segment != MAIN_MARKET:
            raise ValueError("only Saudi Main Market sessions are enabled")
        if type(session_date) is not date:
            raise ValueError("session_date must be a date")
        if (
            not isinstance(known_at, datetime)
            or known_at.tzinfo is None
            or known_at.utcoffset() is None
        ):
            raise ValueError("calendar known_at must be timezone-aware")
        revision = self.revision
        if revision is not None and not revision.known_at(known_at):
            return SaudiSession(
                session_date=session_date,
                segment=segment,
                is_trading_day=False,
                phases=(),
                closed_reason=CALENDAR_REVISION_NOT_KNOWN,
                source_id="UNAVAILABLE_AT_CUTOFF",
                coverage_known=False,
                calendar_revision_id=None,
                boundary_uncertainty_seconds=MAX_BOUNDARY_UNCERTAINTY_SECONDS,
                resume_on=None,
            )
        source_id = revision.source_id if revision else "UNCONFIGURED"
        revision_id = revision.revision_id if revision else None
        uncertainty = revision.boundary_uncertainty_seconds if revision else 30
        if revision is None or not (
            revision.coverage_from <= session_date <= revision.coverage_through
        ) or not revision.schedule.applies_on(session_date):
            return SaudiSession(
                session_date=session_date,
                segment=segment,
                is_trading_day=False,
                phases=(),
                closed_reason=CALENDAR_COVERAGE_MISSING,
                source_id=source_id,
                coverage_known=False,
                calendar_revision_id=revision_id,
                boundary_uncertainty_seconds=uncertainty,
                resume_on=None,
            )
        if session_date.weekday() in {4, 5}:
            return SaudiSession(
                session_date=session_date,
                segment=segment,
                is_trading_day=False,
                phases=(),
                closed_reason="WEEKEND",
                source_id=source_id,
                coverage_known=True,
                calendar_revision_id=revision_id,
                boundary_uncertainty_seconds=uncertainty,
                resume_on=None,
            )
        closure = revision.closure_on(session_date)
        if closure is not None:
            return SaudiSession(
                session_date=session_date,
                segment=segment,
                is_trading_day=False,
                phases=(),
                closed_reason=closure.reason,
                source_id=source_id,
                coverage_known=True,
                calendar_revision_id=revision_id,
                boundary_uncertainty_seconds=uncertainty,
                resume_on=closure.resume_on,
            )

        def at(value: time) -> datetime:
            return datetime.combine(session_date, value, tzinfo=self._tz)

        phases = tuple(
            SessionPhase(
                name=template.name,
                start=at(template.start),
                end=at(template.end),
                executable=template.executable,
            )
            for template in revision.schedule.phases
        )
        return SaudiSession(
            session_date=session_date,
            segment=segment,
            is_trading_day=True,
            phases=phases,
            closed_reason=None,
            source_id=source_id,
            coverage_known=True,
            calendar_revision_id=revision_id,
            boundary_uncertainty_seconds=uncertainty,
            resume_on=None,
        )

    def next_session(
        self,
        after: date,
        *,
        known_at: datetime,
        segment: str = MAIN_MARKET,
    ) -> SaudiSession:
        try:
            current = after + timedelta(days=1)
        except OverflowError as exc:
            raise RuntimeError("no representable Saudi Exchange session follows date") from exc
        for _ in range(370):
            candidate = self.session_for(
                current,
                known_at=known_at,
                segment=segment,
            )
            if candidate.closed_reason in {
                CALENDAR_COVERAGE_MISSING,
                CALENDAR_REVISION_NOT_KNOWN,
            }:
                raise RuntimeError(candidate.closed_reason)
            if candidate.is_trading_day:
                return candidate
            try:
                current += timedelta(days=1)
            except OverflowError as exc:
                raise RuntimeError(
                    "no representable Saudi Exchange session follows date"
                ) from exc
        raise RuntimeError("no Saudi Exchange session found within one year")

    def require_aware_riyadh(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        try:
            return value.astimezone(self._tz)
        except (OverflowError, ValueError) as exc:
            raise ValueError(
                "timestamp is outside the supported Riyadh range"
            ) from exc


__all__ = [
    "CALENDAR_COVERAGE_MISSING",
    "CALENDAR_REVISION_NOT_KNOWN",
    "MAX_BOUNDARY_UNCERTAINTY_SECONDS",
    "MAX_CALENDAR_COVERAGE_DAYS",
    "MAX_HOLIDAY_CLOSURE_DAYS",
    "MAX_HOLIDAY_CLOSURES",
    "MIN_SUPPORTED_WEEKEND_REGIME_DATE",
    "SaudiCalendarRevision",
    "SaudiHolidayClosure",
    "SaudiSession",
    "SaudiSessionPhaseTemplate",
    "SaudiSessionSchedule",
    "SaudiTradingCalendar",
    "SessionPhase",
    "calendar_revision_from_mapping",
    "calendar_revision_from_bytes",
    "load_saudi_calendar_revision",
]
