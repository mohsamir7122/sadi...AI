"""Leakage-resistant nightly laboratory for Saudi Exchange event research.

The module is intentionally data-provider agnostic.  It accepts only evidence
that has already passed identity, rights, denominator, and corporate-action
checks.  The final holdout API excludes outcomes from fitting, seals predictions,
and only then allows a separate outcome vault to be scored.  This is a
retrospective out-of-sample code-path separation: labels are mature at run time,
not prospectively unavailable or protected by an independent custodian.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from ..markets.saudi.calendar import SaudiTradingCalendar
from ..markets.saudi.config import MAIN_MARKET, ORDINARY_EQUITY, RIYADH_TZ
from ..markets.saudi.identity import SaudiSecurityMaster
from ..saudi_admission import (
    AdmissionPurpose,
    VerifiedSaudiAdmission,
    require_verified_saudi_admission,
)
from .rights import MODEL_USE_RIGHTS, RightsUse, require_rights


SAUDI_CODE_RE = re.compile(r"^[0-9]{4}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_COVERAGE_TOLERANCE_DAYS = 62
MAX_MATURITY_BUFFER_DAYS = 550
MAX_COVERAGE_GAP_DAYS = 550
MAX_NIGHTLY_FACTOR_AGE_DAYS = 370
ALLOWED_SOURCE_ROLES = frozenset(
    {
        "OFFICIAL_VERIFICATION",
        "REGULATORY_EVIDENCE",
        "ISSUER_DISCLOSURE",
        "LICENSED_MARKET_DATA",
    }
)
# Compatibility export for callers that previously imported this name.  The
# nightly laboratory fits a model, so the set is intentionally model-use only.
ALLOWED_RIGHTS = MODEL_USE_RIGHTS


class Cohort(str, Enum):
    PRIMARY = "PRIMARY"
    PROBE = "PROBE"


class Horizon(str, Enum):
    INTRADAY = "INTRADAY"
    NEXT_SESSION = "NEXT_SESSION"  # secret-guard: allow; research horizon enum, not a credential
    WEEK = "WEEK"
    MONTH = "MONTH"
    YEAR = "YEAR"


ALL_HORIZONS = tuple(Horizon)
HORIZON_MINIMUM_MATURITY = {
    Horizon.INTRADAY: timedelta(0),
    Horizon.NEXT_SESSION: timedelta(days=1),
    Horizon.WEEK: timedelta(days=7),
    Horizon.MONTH: timedelta(days=28),
    Horizon.YEAR: timedelta(days=365),
}


class EventType(str, Enum):
    EARNINGS = "EARNINGS"
    GUIDANCE = "GUIDANCE"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    LEGAL_REGULATORY = "LEGAL_REGULATORY"
    SUSPENSION_STATUS = "SUSPENSION_STATUS"
    GOVERNANCE = "GOVERNANCE"
    MERGER_ACQUISITION = "MERGER_ACQUISITION"
    MACRO_SECTOR = "MACRO_SECTOR"
    PRICE_VOLUME_DISLOCATION = "PRICE_VOLUME_DISLOCATION"


def _require_aware(value: object, field: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{field} must be timezone-aware")


def _utc(value: datetime) -> datetime:
    """Compare aware instants in UTC, including ambiguous DST-fold values."""

    _require_aware(value, "timestamp")
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValueError("nightly timestamp is outside the supported UTC range") from exc


def _finite(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be finite")
    try:
        finite = math.isfinite(float(value))
    except (OverflowError, ValueError):
        finite = False
    if not finite:
        raise ValueError(f"{field} must be finite")


def _safe_product(left: object, right: object, field: str) -> float:
    _finite(left, field)
    _finite(right, field)
    result = float(left) * float(right)
    _finite(result, field)
    return result


def _safe_sum(values: Iterable[float], field: str) -> float:
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field} must remain finite") from exc
    _finite(result, field)
    return result


def _json_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _json_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a JSON number")
    _finite(value, field)
    return float(value)


def _json_timestamp(value: object, field: str) -> datetime:
    raw = _json_string(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp string") from exc
    _require_aware(parsed, field)
    return parsed


def _canonical_sha256(payload: object) -> str:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("canonical payload must contain finite JSON values") from exc
    return hashlib.sha256(encoded).hexdigest()


def _years_before(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, month=2, day=28)


@dataclass(frozen=True)
class FactorObservation:
    factor_id: str
    value: float
    known_at: datetime
    source_id: str
    rights_status: str

    def __post_init__(self) -> None:
        if not isinstance(self.factor_id, str) or not self.factor_id.startswith("F9-"):
            raise ValueError("factor_id must start with F9-")
        _finite(self.value, "factor value")
        object.__setattr__(self, "value", float(self.value))
        _require_aware(self.known_at, "factor known_at")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("factor source_id is required")
        require_rights(self.rights_status, use=RightsUse.MODEL_USE)

    def to_dict(self) -> dict[str, object]:
        return {
            "factor_id": self.factor_id,
            "value": self.value,
            "known_at": self.known_at.isoformat(),
            "source_id": self.source_id,
            "rights_status": self.rights_status,
        }


@dataclass(frozen=True)
class OutcomeObservation:
    horizon: Horizon
    excess_return: float
    known_at: datetime
    price_basis: str = "CORPORATE_ACTION_ADJUSTED_TOTAL_RETURN"

    def __post_init__(self) -> None:
        if not isinstance(self.horizon, Horizon):
            raise ValueError("outcome horizon must use the governed enum")
        _finite(self.excess_return, "outcome excess_return")
        object.__setattr__(self, "excess_return", float(self.excess_return))
        _require_aware(self.known_at, "outcome known_at")
        if self.price_basis != "CORPORATE_ACTION_ADJUSTED_TOTAL_RETURN":
            raise ValueError("outcome price basis must be corporate-action adjusted")

    def to_dict(self) -> dict[str, object]:
        return {
            "horizon": self.horizon.value,
            "excess_return": self.excess_return,
            "known_at": self.known_at.isoformat(),
            "price_basis": self.price_basis,
        }


@dataclass(frozen=True)
class HistoricalEvent:
    event_id: str
    official_code: str
    prediction_at: datetime
    event_at: datetime
    evidence_known_at: datetime
    cohort: Cohort
    event_type: EventType
    source_id: str
    source_role: str
    rights_status: str
    factors: tuple[FactorObservation, ...]
    outcomes: tuple[OutcomeObservation, ...]
    denominator_complete: bool
    corporate_actions_reconciled: bool
    identity_verified: bool

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id is required")
        if not isinstance(self.official_code, str) or not SAUDI_CODE_RE.fullmatch(
            self.official_code
        ):
            raise ValueError("official_code must be a four-digit Saudi code")
        for field, value in (
            ("prediction_at", self.prediction_at),
            ("event_at", self.event_at),
            ("evidence_known_at", self.evidence_known_at),
        ):
            _require_aware(value, field)
        if _utc(self.prediction_at) > _utc(self.event_at):
            raise ValueError("prediction_at cannot follow event_at")
        if _utc(self.evidence_known_at) < _utc(self.event_at):
            raise ValueError("event evidence cannot be known before the event")
        if not isinstance(self.cohort, Cohort) or not isinstance(
            self.event_type, EventType
        ):
            raise ValueError("event cohort and event_type must use governed enums")
        if not isinstance(self.source_role, str) or self.source_role not in ALLOWED_SOURCE_ROLES:
            raise ValueError("event source_role is not authoritative")
        require_rights(self.rights_status, use=RightsUse.MODEL_USE)
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("event source_id is required")
        if not isinstance(self.factors, tuple) or not self.factors or any(
            not isinstance(factor, FactorObservation) for factor in self.factors
        ):
            raise ValueError("at least one Point-in-Time factor is required")
        factor_ids = [factor.factor_id for factor in self.factors]
        if len(factor_ids) != len(set(factor_ids)):
            raise ValueError("factor IDs must be unique within an event")
        if any(
            _utc(factor.known_at) > _utc(self.prediction_at)
            for factor in self.factors
        ):
            raise ValueError("FEATURE_LEAKAGE_AFTER_PREDICTION_CUTOFF")
        if any(
            _utc(self.prediction_at) - _utc(factor.known_at)
            > timedelta(days=MAX_NIGHTLY_FACTOR_AGE_DAYS)
            for factor in self.factors
        ):
            raise ValueError("STALE_FACTOR_AT_PREDICTION_CUTOFF")
        if not isinstance(self.outcomes, tuple) or any(
            not isinstance(outcome, OutcomeObservation) for outcome in self.outcomes
        ):
            raise ValueError("outcomes must be governed outcome records")
        horizons = [outcome.horizon for outcome in self.outcomes]
        if len(horizons) != len(set(horizons)):
            raise ValueError("outcome horizons must be unique within an event")
        if set(horizons) != set(ALL_HORIZONS):
            raise ValueError("all five governed horizons are required")
        if any(
            _utc(outcome.known_at) <= _utc(self.prediction_at)
            for outcome in self.outcomes
        ):
            raise ValueError("OUTCOME_LEAKAGE_AT_PREDICTION_CUTOFF")
        if any(
            _utc(outcome.known_at) < _utc(self.event_at)
            for outcome in self.outcomes
        ):
            raise ValueError("outcome cannot be known before event_at")
        if any(
            _utc(outcome.known_at)
            < _utc(self.event_at) + HORIZON_MINIMUM_MATURITY[outcome.horizon]
            for outcome in self.outcomes
        ):
            raise ValueError("OUTCOME_HORIZON_MINIMUM_MATURITY_NOT_MET")
        for field, value in (
            ("denominator_complete", self.denominator_complete),
            ("corporate_actions_reconciled", self.corporate_actions_reconciled),
            ("identity_verified", self.identity_verified),
        ):
            if type(value) is not bool:
                raise ValueError(f"{field} must be a boolean")
        if not self.denominator_complete:
            raise ValueError("DENOMINATOR_INCOMPLETE")
        if not self.corporate_actions_reconciled:
            raise ValueError("CORPORATE_ACTIONS_UNRECONCILED")
        if not self.identity_verified:
            raise ValueError("IDENTITY_UNVERIFIED")

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "official_code": self.official_code,
            "prediction_at": self.prediction_at.isoformat(),
            "event_at": self.event_at.isoformat(),
            "evidence_known_at": self.evidence_known_at.isoformat(),
            "cohort": self.cohort.value,
            "event_type": self.event_type.value,
            "source_id": self.source_id,
            "source_role": self.source_role,
            "rights_status": self.rights_status,
            "factors": [factor.to_dict() for factor in self.factors],
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
        }


def _maturity_cutoffs(
    *,
    prediction_at: datetime,
    event_at: datetime,
    calendar: SaudiTradingCalendar,
) -> tuple[tuple[Horizon, datetime], ...]:
    try:
        next_session = calendar.next_session(
            event_at.astimezone(ZoneInfo(RIYADH_TZ)).date(),
            known_at=prediction_at,
        )
    except RuntimeError as exc:
        raise ValueError("NEXT_SESSION_CALENDAR_COVERAGE_MISSING") from exc
    if not next_session.phases:
        raise ValueError("NEXT_SESSION_PHASES_MISSING")
    next_session_available_at = max(
        phase.end for phase in next_session.phases
    ) + timedelta(seconds=next_session.boundary_uncertainty_seconds)
    values = {
        horizon: (
            next_session_available_at
            if horizon is Horizon.NEXT_SESSION
            else _utc(event_at) + HORIZON_MINIMUM_MATURITY[horizon]
        )
        for horizon in ALL_HORIZONS
    }
    return tuple((horizon, values[horizon]) for horizon in ALL_HORIZONS)


def _outcome_not_before(
    event: HistoricalEvent,
    calendar: SaudiTradingCalendar,
) -> tuple[tuple[Horizon, datetime], ...]:
    return _maturity_cutoffs(
        prediction_at=event.prediction_at,
        event_at=event.event_at,
        calendar=calendar,
    )


@dataclass(frozen=True)
class BlindHoldoutEvent:
    event_id: str
    official_code: str
    prediction_at: datetime
    event_at: datetime
    cohort: Cohort
    factors: tuple[FactorObservation, ...]
    outcome_not_before: tuple[tuple[Horizon, datetime], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("blind holdout event_id is required")
        if not isinstance(self.official_code, str) or not SAUDI_CODE_RE.fullmatch(
            self.official_code
        ):
            raise ValueError("blind holdout official_code is invalid")
        _require_aware(self.prediction_at, "blind holdout prediction_at")
        _require_aware(self.event_at, "blind holdout event_at")
        if _utc(self.prediction_at) > _utc(self.event_at):
            raise ValueError("blind holdout prediction_at cannot follow event_at")
        if not isinstance(self.cohort, Cohort):
            raise ValueError("blind holdout cohort must use the governed enum")
        if not isinstance(self.factors, tuple) or not self.factors or any(
            not isinstance(factor, FactorObservation) for factor in self.factors
        ):
            raise ValueError("blind holdout factors must be governed factor records")
        factor_ids = [factor.factor_id for factor in self.factors]
        if len(factor_ids) != len(set(factor_ids)):
            raise ValueError("blind holdout factor IDs must be unique")
        if any(
            _utc(factor.known_at) > _utc(self.prediction_at)
            for factor in self.factors
        ):
            raise ValueError("BLIND_HOLDOUT_FEATURE_LEAKAGE_AFTER_PREDICTION_CUTOFF")
        if any(
            _utc(self.prediction_at) - _utc(factor.known_at)
            > timedelta(days=MAX_NIGHTLY_FACTOR_AGE_DAYS)
            for factor in self.factors
        ):
            raise ValueError("BLIND_HOLDOUT_STALE_FACTOR_AT_PREDICTION_CUTOFF")
        if (
            not isinstance(self.outcome_not_before, tuple)
            or any(
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], Horizon)
                or not isinstance(item[1], datetime)
                for item in self.outcome_not_before
            )
            or tuple(item[0] for item in self.outcome_not_before) != ALL_HORIZONS
        ):
            raise ValueError("blind holdout maturity cutoffs must cover all horizons")
        for _, cutoff in self.outcome_not_before:
            _require_aware(cutoff, "blind holdout maturity cutoff")
            if _utc(cutoff) < _utc(self.event_at):
                raise ValueError("blind holdout maturity cutoff precedes event_at")

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "official_code": self.official_code,
            "prediction_at": self.prediction_at.isoformat(),
            "event_at": self.event_at.isoformat(),
            "cohort": self.cohort.value,
            "factors": [factor.to_dict() for factor in self.factors],
            "outcome_not_before": {
                horizon.value: cutoff.isoformat()
                for horizon, cutoff in self.outcome_not_before
            },
        }


@dataclass(frozen=True)
class OutcomeVaultEntry:
    event_id: str
    outcomes: tuple[OutcomeObservation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("outcome vault event_id is required")
        if any(not isinstance(outcome, OutcomeObservation) for outcome in self.outcomes):
            raise ValueError("outcome vault values must be OutcomeObservation records")
        if any(not isinstance(outcome.horizon, Horizon) for outcome in self.outcomes):
            raise ValueError("outcome vault horizons must use the governed enum")
        horizons = [outcome.horizon for outcome in self.outcomes]
        if len(horizons) != len(set(horizons)) or set(horizons) != set(ALL_HORIZONS):
            raise ValueError("outcome vault entry requires five unique governed horizons")
        by_horizon = {outcome.horizon: outcome for outcome in self.outcomes}
        known_at = [_utc(by_horizon[horizon].known_at) for horizon in ALL_HORIZONS]
        if known_at != sorted(known_at):
            raise ValueError("outcome availability must be nondecreasing by horizon")

    def to_dict(self) -> dict[str, object]:
        by_horizon = {outcome.horizon: outcome for outcome in self.outcomes}
        return {
            "event_id": self.event_id,
            "outcomes": [by_horizon[horizon].to_dict() for horizon in ALL_HORIZONS],
        }


@dataclass(frozen=True)
class HoldoutOutcomeVault:
    entries: tuple[OutcomeVaultEntry, ...]
    vault_sha256: str

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("outcome vault entries are required")
        if any(not isinstance(entry, OutcomeVaultEntry) for entry in self.entries):
            raise ValueError("outcome vault entries must be OutcomeVaultEntry records")
        event_ids = [entry.event_id for entry in self.entries]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("outcome vault event_id values must be unique")
        if not isinstance(self.vault_sha256, str) or not SHA256_RE.fullmatch(
            self.vault_sha256
        ):
            raise ValueError("outcome vault sha256 is invalid")

    @classmethod
    def build(cls, entries: Iterable[OutcomeVaultEntry]) -> "HoldoutOutcomeVault":
        ordered = tuple(sorted(entries, key=lambda item: item.event_id))
        if not ordered:
            raise ValueError("outcome vault entries are required")
        if len({entry.event_id for entry in ordered}) != len(ordered):
            raise ValueError("outcome vault event_id values must be unique")
        payload = [entry.to_dict() for entry in ordered]
        return cls(entries=ordered, vault_sha256=_canonical_sha256(payload))

    def verify(self) -> None:
        actual = _canonical_sha256(
            [entry.to_dict() for entry in sorted(self.entries, key=lambda item: item.event_id)]
        )
        if actual != self.vault_sha256:
            raise ValueError("HOLDOUT_OUTCOME_VAULT_HASH_MISMATCH")

    def to_dict(self) -> dict[str, object]:
        return {
            "entries": [
                entry.to_dict()
                for entry in sorted(self.entries, key=lambda item: item.event_id)
            ],
            "vault_sha256": self.vault_sha256,
        }


@dataclass(frozen=True)
class TemporalSplit:
    training: tuple[HistoricalEvent, ...]
    validation: tuple[HistoricalEvent, ...]
    blind_holdout: tuple[BlindHoldoutEvent, ...]
    outcome_vault: HoldoutOutcomeVault
    validation_start: datetime
    holdout_start: datetime
    purged_event_ids: tuple[str, ...]
    cohort_counts: Mapping[str, Mapping[str, int]]
    max_training_label_end: datetime
    max_validation_label_end: datetime
    max_training_information_end: datetime
    max_validation_information_end: datetime
    source_event_count: int
    retained_event_count: int
    retained_ratios: Mapping[str, float]
    purge_rate: float


class CausalTemporalSplitError(ValueError):
    """Raised when no globally causal split satisfies cohort minimums."""


@dataclass(frozen=True)
class HorizonWeights:
    horizon: Horizon
    weights: tuple[tuple[str, float], ...]
    validation_scale: float

    def __post_init__(self) -> None:
        if not isinstance(self.horizon, Horizon):
            raise ValueError("model horizon must use the governed enum")
        if not isinstance(self.weights, tuple) or not self.weights:
            raise ValueError("model horizon weights must be a non-empty tuple")
        factor_ids: list[str] = []
        for item in self.weights:
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
                or not item[0].startswith("F9-")
            ):
                raise ValueError("model weights require governed F9 factor IDs")
            _finite(item[1], "model weight")
            factor_ids.append(item[0])
        if factor_ids != sorted(factor_ids) or len(factor_ids) != len(set(factor_ids)):
            raise ValueError("model factor weights must be unique and canonically ordered")
        object.__setattr__(
            self,
            "weights",
            tuple((factor_id, float(weight)) for factor_id, weight in self.weights),
        )
        _finite(self.validation_scale, "model validation_scale")
        if not -3.0 <= self.validation_scale <= 3.0:
            raise ValueError("model validation_scale exceeds the governed range")
        object.__setattr__(self, "validation_scale", float(self.validation_scale))

    def as_mapping(self) -> dict[str, float]:
        return dict(self.weights)

    def to_dict(self) -> dict[str, object]:
        return {
            "horizon": self.horizon.value,
            "weights": {factor_id: weight for factor_id, weight in self.weights},
            "validation_scale": self.validation_scale,
        }


@dataclass(frozen=True)
class FittedModel:
    horizon_weights: tuple[HorizonWeights, ...]
    training_event_ids: tuple[str, ...]
    validation_event_ids: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        horizon_weights: tuple[HorizonWeights, ...],
        training_event_ids: tuple[str, ...],
        validation_event_ids: tuple[str, ...],
    ) -> "FittedModel":
        payload = {
            "horizon_weights": [item.to_dict() for item in horizon_weights],
            "training_event_ids": list(training_event_ids),
            "validation_event_ids": list(validation_event_ids),
        }
        return cls(
            horizon_weights=horizon_weights,
            training_event_ids=training_event_ids,
            validation_event_ids=validation_event_ids,
            fingerprint=_canonical_sha256(payload),
        )

    def with_horizon_weights(
        self, horizon_weights: tuple[HorizonWeights, ...]
    ) -> "FittedModel":
        return self.build(
            horizon_weights=horizon_weights,
            training_event_ids=self.training_event_ids,
            validation_event_ids=self.validation_event_ids,
        )

    def verify(self) -> None:
        if (
            not isinstance(self.horizon_weights, tuple)
            or any(not isinstance(item, HorizonWeights) for item in self.horizon_weights)
            or tuple(item.horizon for item in self.horizon_weights) != ALL_HORIZONS
        ):
            raise ValueError("model must contain exactly the governed horizons in order")
        factor_sets = {
            frozenset(factor_id for factor_id, _ in item.weights)
            for item in self.horizon_weights
        }
        if len(factor_sets) != 1:
            raise ValueError("model horizons must use the same exact factor set")
        for field, values in (
            ("training_event_ids", self.training_event_ids),
            ("validation_event_ids", self.validation_event_ids),
        ):
            if (
                not isinstance(values, tuple)
                or not values
                or any(not isinstance(value, str) or not value.strip() for value in values)
                or len(values) != len(set(values))
            ):
                raise ValueError(f"model {field} must contain unique non-empty IDs")
        if set(self.training_event_ids) & set(self.validation_event_ids):
            raise ValueError("model training and validation event IDs must be disjoint")
        if not isinstance(self.fingerprint, str) or not SHA256_RE.fullmatch(
            self.fingerprint
        ):
            raise ValueError("model fingerprint is invalid")
        payload = {
            "horizon_weights": [item.to_dict() for item in self.horizon_weights],
            "training_event_ids": list(self.training_event_ids),
            "validation_event_ids": list(self.validation_event_ids),
        }
        if self.fingerprint != _canonical_sha256(payload):
            raise ValueError("FITTED_MODEL_FINGERPRINT_MISMATCH")

    def weights_for(self, horizon: Horizon) -> dict[str, float]:
        for item in self.horizon_weights:
            if item.horizon is horizon:
                return item.as_mapping()
        raise KeyError(horizon.value)

    def to_dict(self) -> dict[str, object]:
        return {
            "horizon_weights": [item.to_dict() for item in self.horizon_weights],
            "training_event_ids": list(self.training_event_ids),
            "validation_event_ids": list(self.validation_event_ids),
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class HoldoutPrediction:
    event_id: str
    official_code: str
    cohort: Cohort
    horizon: Horizon
    score: float
    direction: str
    prediction_at: datetime
    event_at: datetime
    outcome_not_before: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("sealed prediction event_id is required")
        if not isinstance(self.official_code, str) or not SAUDI_CODE_RE.fullmatch(
            self.official_code
        ):
            raise ValueError("sealed prediction official_code is invalid")
        if not isinstance(self.cohort, Cohort) or not isinstance(self.horizon, Horizon):
            raise ValueError("sealed prediction cohort or horizon is invalid")
        _finite(self.score, "sealed prediction score")
        if self.direction not in {"UP", "DOWN", "FLAT"}:
            raise ValueError("sealed prediction direction is invalid")
        if self.direction != _direction(self.score):
            raise ValueError("sealed prediction direction does not match score")
        _require_aware(self.prediction_at, "sealed prediction prediction_at")
        _require_aware(self.event_at, "sealed prediction event_at")
        _require_aware(
            self.outcome_not_before,
            "sealed prediction outcome_not_before",
        )
        if _utc(self.prediction_at) > _utc(self.event_at):
            raise ValueError("sealed prediction prediction_at cannot follow event_at")
        if _utc(self.outcome_not_before) < _utc(self.event_at):
            raise ValueError("sealed prediction maturity cutoff precedes event_at")

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "official_code": self.official_code,
            "cohort": self.cohort.value,
            "horizon": self.horizon.value,
            "score": self.score,
            "direction": self.direction,
            "prediction_at": self.prediction_at.isoformat(),
            "event_at": self.event_at.isoformat(),
            "outcome_not_before": self.outcome_not_before.isoformat(),
        }


@dataclass(frozen=True)
class SealedPredictionPacket:
    run_id: str
    sealed_at: datetime
    model_fingerprint: str
    blind_event_sha256: str
    predictions: tuple[HoldoutPrediction, ...]
    seal_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("sealed packet run_id is required")
        _require_aware(self.sealed_at, "sealed_at")
        for field, value in (
            ("model_fingerprint", self.model_fingerprint),
            ("blind_event_sha256", self.blind_event_sha256),
            ("seal_sha256", self.seal_sha256),
        ):
            if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
                raise ValueError(f"sealed packet {field} is invalid")
        if not self.predictions:
            raise ValueError("sealed packet predictions are required")
        if any(not isinstance(item, HoldoutPrediction) for item in self.predictions):
            raise ValueError("sealed packet values must be HoldoutPrediction records")
        keys = [(item.event_id, item.horizon) for item in self.predictions]
        if len(keys) != len(set(keys)):
            raise ValueError("sealed packet prediction keys must be unique")
        grouped: dict[str, list[HoldoutPrediction]] = {}
        for item in self.predictions:
            if not isinstance(item.event_id, str) or not item.event_id.strip():
                raise ValueError("sealed prediction event_id is required")
            if not isinstance(item.official_code, str) or not SAUDI_CODE_RE.fullmatch(
                item.official_code
            ):
                raise ValueError("sealed prediction official_code is invalid")
            if not isinstance(item.cohort, Cohort) or not isinstance(item.horizon, Horizon):
                raise ValueError("sealed prediction cohort or horizon is invalid")
            _finite(item.score, "sealed prediction score")
            _require_aware(item.prediction_at, "sealed prediction prediction_at")
            _require_aware(item.event_at, "sealed prediction event_at")
            _require_aware(
                item.outcome_not_before,
                "sealed prediction outcome_not_before",
            )
            if _utc(item.prediction_at) > _utc(self.sealed_at):
                raise ValueError("sealed prediction cannot follow sealed_at")
            if _utc(item.outcome_not_before) > _utc(self.sealed_at):
                raise ValueError("sealed prediction maturity cutoff follows sealed_at")
            if item.direction != _direction(item.score):
                raise ValueError("sealed prediction direction does not match score")
            grouped.setdefault(item.event_id, []).append(item)
        for event_id, predictions in grouped.items():
            if {item.horizon for item in predictions} != set(ALL_HORIZONS):
                raise ValueError(
                    f"sealed prediction event {event_id} requires five governed horizons"
                )
            metadata = {
                (
                    item.official_code,
                    item.cohort,
                    _utc(item.prediction_at),
                    _utc(item.event_at),
                )
                for item in predictions
            }
            if len(metadata) != 1:
                raise ValueError(
                    f"sealed prediction event {event_id} metadata is inconsistent"
                )

    def unsigned_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "sealed_at": self.sealed_at.isoformat(),
            "model_fingerprint": self.model_fingerprint,
            "blind_event_sha256": self.blind_event_sha256,
            "predictions": [item.to_dict() for item in self.predictions],
        }

    def verify(self) -> None:
        if _canonical_sha256(self.unsigned_payload()) != self.seal_sha256:
            raise ValueError("SEALED_PREDICTION_PACKET_HASH_MISMATCH")

    def to_dict(self) -> dict[str, object]:
        return {**self.unsigned_payload(), "seal_sha256": self.seal_sha256}


@dataclass(frozen=True)
class NightlyPreparation:
    status: str
    reasons: tuple[str, ...]
    counts: Mapping[str, int]
    split: TemporalSplit | None = None
    model: FittedModel | None = None
    sealed_packet: SealedPredictionPacket | None = None
    coverage_audit: Mapping[str, object] | None = None


def _ordered(events: Iterable[HistoricalEvent]) -> tuple[HistoricalEvent, ...]:
    return tuple(
        sorted(events, key=lambda item: (_utc(item.prediction_at), item.event_id))
    )


def _label_end(event: HistoricalEvent) -> datetime:
    return max(_utc(outcome.known_at) for outcome in event.outcomes)


def _boundary_information_end(event: HistoricalEvent) -> datetime:
    """Latest instant required before an event may cross a causal boundary."""

    return max(_label_end(event), _utc(event.evidence_known_at))


def _validate_calendar_outcome_maturity(
    event: HistoricalEvent, calendar: SaudiTradingCalendar
) -> None:
    prediction_date = event.prediction_at.astimezone(ZoneInfo(RIYADH_TZ)).date()
    prediction_session = calendar.session_for(
        prediction_date,
        known_at=event.prediction_at,
    )
    if not prediction_session.coverage_known:
        raise ValueError("CALENDAR_NOT_POINT_IN_TIME_AT_EVENT_PREDICTION")
    cutoffs = dict(_outcome_not_before(event, calendar))
    for outcome in event.outcomes:
        if _utc(outcome.known_at) < _utc(cutoffs[outcome.horizon]):
            if outcome.horizon is Horizon.NEXT_SESSION:
                raise ValueError("NEXT_SESSION_OUTCOME_AVAILABLE_BEFORE_SESSION_END")
            raise ValueError("OUTCOME_HORIZON_MINIMUM_MATURITY_NOT_MET")


def _require_uniform_factor_set(
    events: Iterable[HistoricalEvent | BlindHoldoutEvent],
    *,
    expected: frozenset[str] | None = None,
) -> frozenset[str]:
    rows = tuple(events)
    factor_sets = {
        frozenset(factor.factor_id for factor in event.factors) for event in rows
    }
    if not factor_sets:
        raise ValueError("factor-set validation requires events")
    if len(factor_sets) != 1:
        raise ValueError("INCONSISTENT_FACTOR_SET_NO_MISSINGNESS_POLICY")
    actual = next(iter(factor_sets))
    if expected is not None and actual != expected:
        raise ValueError("FACTOR_SET_MISMATCH_NO_ZERO_IMPUTATION")
    return actual


def _partition_minimums(minimum: int) -> tuple[int, int, int]:
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 3:
        raise ValueError("each cohort minimum must be at least three")
    training = max(1, minimum * 3 // 5)
    validation = max(1, minimum // 5)
    holdout = max(1, minimum - training - validation)
    return training, validation, holdout


def _years_after(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, month=2, day=28)


def _annual_coverage_buckets(
    start: datetime,
    end: datetime,
) -> tuple[tuple[str, datetime, datetime, bool], ...]:
    """Return deterministic anniversary-anchored buckets through ``end``."""

    if end <= start:
        return ()
    buckets: list[tuple[str, datetime, datetime, bool]] = []
    bucket_start = start
    year_offset = 1
    while bucket_start < end:
        natural_end = _years_after(start, year_offset)
        bucket_end = min(natural_end, end)
        is_final = bucket_end == end
        label = f"{bucket_start.date().isoformat()}/{bucket_end.date().isoformat()}"
        buckets.append((label, bucket_start, bucket_end, is_final))
        bucket_start = bucket_end
        year_offset += 1
    return tuple(buckets)


def _build_coverage_audit(
    rows: Sequence[HistoricalEvent],
    *,
    run_at: datetime,
    earliest: datetime,
    lookback_years: int,
    coverage_tolerance_days: int,
    maturity_buffer_days: int,
    maximum_gap_days: int,
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Audit longitudinal event coverage without requiring immature YEAR labels."""

    tolerance = timedelta(days=coverage_tolerance_days)
    maturity_cutoff = max(earliest, run_at - timedelta(days=maturity_buffer_days))
    buckets = _annual_coverage_buckets(earliest, maturity_cutoff)
    cohort_audit: dict[str, object] = {}
    specific_reasons: list[str] = []
    generic_failures: set[str] = set()

    for cohort in Cohort:
        cohort_rows = tuple(event for event in rows if event.cohort is cohort)
        if not cohort_rows:
            cohort_audit[cohort.value] = {
                "event_count": 0,
                "first_prediction_at": None,
                "last_prediction_at": None,
                "latest_label_end": None,
                "annual_bucket_counts": {
                    label: 0 for label, _, _, _ in buckets
                },
                "missing_annual_buckets": [label for label, _, _, _ in buckets],
                "maximum_gap_days": None,
            }
            continue

        prediction_times = sorted({_utc(event.prediction_at) for event in cohort_rows})
        first_prediction = prediction_times[0]
        last_prediction = prediction_times[-1]
        latest_label_end = max(_label_end(event) for event in cohort_rows)
        bucket_counts: dict[str, int] = {}
        for label, bucket_start, bucket_end, is_final in buckets:
            bucket_counts[label] = sum(
                _utc(bucket_start) <= _utc(event.prediction_at) <= _utc(bucket_end)
                if is_final
                else _utc(bucket_start) <= _utc(event.prediction_at) < _utc(bucket_end)
                for event in cohort_rows
            )
        missing_buckets = [
            label for label, count in bucket_counts.items() if count == 0
        ]

        in_window = [
            value for value in prediction_times if earliest <= value <= maturity_cutoff
        ]
        gap_points = sorted({earliest, maturity_cutoff, *in_window})
        maximum_gap = max(
            (
                (right - left).total_seconds() / 86_400
                for left, right in zip(gap_points, gap_points[1:])
            ),
            default=0.0,
        )

        prefix = cohort.value
        if first_prediction > _utc(earliest + tolerance):
            generic_failures.add("HISTORY_START_COVERAGE_NOT_MET")
            specific_reasons.append(f"{prefix}_HISTORY_START_COVERAGE_NOT_MET")
        if last_prediction < _utc(maturity_cutoff - tolerance):
            generic_failures.add("MATURE_EVENT_END_COVERAGE_NOT_MET")
            specific_reasons.append(f"{prefix}_MATURE_EVENT_END_COVERAGE_NOT_MET")
        if missing_buckets:
            generic_failures.add("ANNUAL_BUCKET_COVERAGE_NOT_MET")
            specific_reasons.append(f"{prefix}_ANNUAL_BUCKET_COVERAGE_NOT_MET")
        if maximum_gap > maximum_gap_days:
            generic_failures.add("MAXIMUM_GAP_COVERAGE_NOT_MET")
            specific_reasons.append(f"{prefix}_MAXIMUM_GAP_COVERAGE_NOT_MET")
        if latest_label_end < _utc(run_at - tolerance):
            generic_failures.add("LATEST_OUTCOME_COVERAGE_NOT_MET")
            specific_reasons.append(f"{prefix}_LATEST_OUTCOME_COVERAGE_NOT_MET")

        cohort_audit[cohort.value] = {
            "event_count": len(cohort_rows),
            "first_prediction_at": first_prediction.isoformat(),
            "last_prediction_at": last_prediction.isoformat(),
            "latest_label_end": latest_label_end.isoformat(),
            "annual_bucket_counts": bucket_counts,
            "missing_annual_buckets": missing_buckets,
            "maximum_gap_days": round(maximum_gap, 6),
        }

    generic_order = (
        "HISTORY_START_COVERAGE_NOT_MET",
        "MATURE_EVENT_END_COVERAGE_NOT_MET",
        "ANNUAL_BUCKET_COVERAGE_NOT_MET",
        "MAXIMUM_GAP_COVERAGE_NOT_MET",
        "LATEST_OUTCOME_COVERAGE_NOT_MET",
    )
    reasons = tuple(
        reason for reason in generic_order if reason in generic_failures
    ) + tuple(specific_reasons)
    return (
        {
            "policy": {
                "lookback_years": lookback_years,
                "coverage_tolerance_days": coverage_tolerance_days,
                "maturity_buffer_days": maturity_buffer_days,
                "maximum_gap_days": maximum_gap_days,
                "window_start": earliest.isoformat(),
                "mature_prediction_cutoff": maturity_cutoff.isoformat(),
            },
            "cohorts": cohort_audit,
        },
        reasons,
    )


def build_temporal_split(
    events: Iterable[HistoricalEvent],
    *,
    calendar: SaudiTradingCalendar,
    cohort_minimums: Mapping[Cohort, int] | None = None,
) -> TemporalSplit:
    """Build one global, purged split targeting retained 60/20/20 ratios.

    Training labels and event evidence must both be available strictly before
    validation begins; validation labels and evidence must both be available
    strictly before holdout begins. Rows whose information interval crosses a
    boundary are purged rather than reassigned.
    """

    if not isinstance(calendar, SaudiTradingCalendar):
        raise ValueError("a governed SaudiTradingCalendar is required")
    rows = _ordered(events)
    for event in rows:
        _validate_calendar_outcome_maturity(event, calendar)
    ids = [event.event_id for event in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("event_id values must be unique")
    minimums = dict(cohort_minimums or {cohort: 3 for cohort in Cohort})
    if set(minimums) != set(Cohort):
        raise ValueError("cohort minimums are required for PRIMARY and PROBE")
    required = {
        cohort: _partition_minimums(minimums[cohort]) for cohort in Cohort
    }
    if len(rows) < sum(minimums.values()):
        raise CausalTemporalSplitError("CAUSAL_TEMPORAL_SPLIT_MINIMUMS_NOT_MET")

    boundaries: list[tuple[int, datetime]] = []
    for index in range(1, len(rows)):
        if _utc(rows[index - 1].prediction_at) != _utc(rows[index].prediction_at):
            boundaries.append((index, _utc(rows[index].prediction_at)))
    if len(boundaries) < 2:
        raise CausalTemporalSplitError("CAUSAL_TEMPORAL_SPLIT_MINIMUMS_NOT_MET")

    base_prefix = {cohort: [0] * (len(rows) + 1) for cohort in Cohort}
    for index, event in enumerate(rows, start=1):
        for cohort in Cohort:
            base_prefix[cohort][index] = base_prefix[cohort][index - 1]
        base_prefix[event.cohort][index] += 1

    training_counts: dict[int, dict[Cohort, int]] = {}
    for boundary_index, boundary_time in boundaries:
        training_counts[boundary_index] = {
            cohort: sum(
                event.cohort is cohort
                and _boundary_information_end(event) < boundary_time
                for event in rows[:boundary_index]
            )
            for cohort in Cohort
        }

    best: tuple[tuple[object, ...], int, int, datetime, datetime] | None = None
    row_count = len(rows)
    for holdout_index, holdout_start in boundaries[1:]:
        eligible_prefix = {cohort: [0] * (row_count + 1) for cohort in Cohort}
        for index, event in enumerate(rows, start=1):
            for cohort in Cohort:
                eligible_prefix[cohort][index] = eligible_prefix[cohort][index - 1]
            if _boundary_information_end(event) < holdout_start:
                eligible_prefix[event.cohort][index] += 1

        for validation_index, validation_start in boundaries:
            if validation_index >= holdout_index:
                break
            train_by_cohort = training_counts[validation_index]
            validation_by_cohort = {
                cohort: (
                    eligible_prefix[cohort][holdout_index]
                    - eligible_prefix[cohort][validation_index]
                )
                for cohort in Cohort
            }
            holdout_by_cohort = {
                cohort: (
                    base_prefix[cohort][row_count]
                    - base_prefix[cohort][holdout_index]
                )
                for cohort in Cohort
            }
            if any(
                train_by_cohort[cohort] < required[cohort][0]
                or validation_by_cohort[cohort] < required[cohort][1]
                or holdout_by_cohort[cohort] < required[cohort][2]
                for cohort in Cohort
            ):
                continue
            train_total = sum(train_by_cohort.values())
            validation_total = sum(validation_by_cohort.values())
            holdout_total = sum(holdout_by_cohort.values())
            purged_total = (
                validation_index
                - train_total
                + holdout_index
                - validation_index
                - validation_total
            )
            ratio_distance = (
                abs(train_total * 5 - row_count * 3)
                + abs(validation_total * 5 - row_count)
                + abs(holdout_total * 5 - row_count)
            )
            retained_total = train_total + validation_total + holdout_total
            retained_ratio_distance = (
                abs(train_total * 5 - retained_total * 3)
                + abs(validation_total * 5 - retained_total)
                + abs(holdout_total * 5 - retained_total)
            )
            score: tuple[object, ...] = (
                retained_ratio_distance,
                purged_total,
                ratio_distance,
                validation_start,
                holdout_start,
            )
            candidate = (
                score,
                validation_index,
                holdout_index,
                validation_start,
                holdout_start,
            )
            if best is None or candidate[0] < best[0]:
                best = candidate

    if best is None:
        raise CausalTemporalSplitError("CAUSAL_TEMPORAL_SPLIT_MINIMUMS_NOT_MET")

    _, validation_index, holdout_index, validation_start, holdout_start = best
    training = tuple(
        event
        for event in rows[:validation_index]
        if _boundary_information_end(event) < validation_start
    )
    validation = tuple(
        event
        for event in rows[validation_index:holdout_index]
        if _boundary_information_end(event) < holdout_start
    )
    holdout = tuple(rows[holdout_index:])
    purged = tuple(
        event.event_id
        for event in (
            *(
                event
                for event in rows[:validation_index]
                if _boundary_information_end(event) >= validation_start
            ),
            *(
                event
                for event in rows[validation_index:holdout_index]
                if _boundary_information_end(event) >= holdout_start
            ),
        )
    )
    if max(_boundary_information_end(event) for event in training) >= min(
        _utc(event.prediction_at) for event in validation
    ):
        raise AssertionError("training information crosses validation boundary")
    if max(_boundary_information_end(event) for event in validation) >= min(
        _utc(event.prediction_at) for event in holdout
    ):
        raise AssertionError("validation information crosses holdout boundary")

    cohort_counts = {
        cohort.value: {
            "training": sum(event.cohort is cohort for event in training),
            "validation": sum(event.cohort is cohort for event in validation),
            "final_holdout": sum(event.cohort is cohort for event in holdout),
        }
        for cohort in Cohort
    }
    retained_event_count = len(training) + len(validation) + len(holdout)
    retained_ratios = {
        "training": round(len(training) / retained_event_count, 12),
        "validation": round(len(validation) / retained_event_count, 12),
        "final_holdout": round(len(holdout) / retained_event_count, 12),
    }
    blind = tuple(
        BlindHoldoutEvent(
            event_id=event.event_id,
            official_code=event.official_code,
            prediction_at=event.prediction_at,
            event_at=event.event_at,
            cohort=event.cohort,
            factors=event.factors,
            outcome_not_before=_outcome_not_before(event, calendar),
        )
        for event in holdout
    )
    vault = HoldoutOutcomeVault.build(
        OutcomeVaultEntry(event_id=event.event_id, outcomes=event.outcomes)
        for event in holdout
    )
    return TemporalSplit(
        training=training,
        validation=validation,
        blind_holdout=blind,
        outcome_vault=vault,
        validation_start=validation_start,
        holdout_start=holdout_start,
        purged_event_ids=purged,
        cohort_counts=cohort_counts,
        max_training_label_end=max(_label_end(event) for event in training),
        max_validation_label_end=max(_label_end(event) for event in validation),
        max_training_information_end=max(
            _boundary_information_end(event) for event in training
        ),
        max_validation_information_end=max(
            _boundary_information_end(event) for event in validation
        ),
        source_event_count=len(rows),
        retained_event_count=retained_event_count,
        retained_ratios=retained_ratios,
        purge_rate=round(len(purged) / len(rows), 12),
    )


def _outcome(event: HistoricalEvent, horizon: Horizon) -> float:
    return next(item.excess_return for item in event.outcomes if item.horizon is horizon)


def _score_factors(factors: Iterable[FactorObservation], weights: Mapping[str, float]) -> float:
    return _safe_sum(
        (
            _safe_product(
                weights[factor.factor_id],
                factor.value,
                "model score arithmetic",
            )
            for factor in factors
        ),
        "model score arithmetic",
    )


def fit_and_calibrate(
    training: Sequence[HistoricalEvent], validation: Sequence[HistoricalEvent]
) -> FittedModel:
    if not training or not validation:
        raise ValueError("training and validation rows are required")
    _require_uniform_factor_set((*training, *validation))
    factor_ids = sorted({factor.factor_id for event in training for factor in event.factors})
    if not factor_ids:
        raise ValueError("training rows contain no admitted factors")
    rows: list[HorizonWeights] = []
    for horizon in ALL_HORIZONS:
        raw: dict[str, float] = {}
        for factor_id in factor_ids:
            pairs = [
                (next((f.value for f in event.factors if f.factor_id == factor_id), 0.0), _outcome(event, horizon))
                for event in training
            ]
            raw[factor_id] = _safe_sum(
                (
                    _safe_product(feature, outcome, "training arithmetic")
                    for feature, outcome in pairs
                ),
                "training arithmetic",
            )
        denominator = _safe_sum(
            (abs(value) for value in raw.values()),
            "training normalization arithmetic",
        )
        base = {
            factor_id: (value / denominator if denominator else 0.0)
            for factor_id, value in raw.items()
        }
        validation_pairs = [
            (_score_factors(event.factors, base), _outcome(event, horizon))
            for event in validation
        ]
        scale_denominator = _safe_sum(
            (
                _safe_product(score, score, "validation scale arithmetic")
                for score, _ in validation_pairs
            ),
            "validation scale arithmetic",
        )
        scale = (
            _safe_sum(
                (
                    _safe_product(score, outcome, "validation scale arithmetic")
                    for score, outcome in validation_pairs
                ),
                "validation scale arithmetic",
            )
            / scale_denominator
            if scale_denominator
            else 0.0
        )
        _finite(scale, "validation scale")
        scale = max(-3.0, min(3.0, scale))
        calibrated = tuple(
            (factor_id, round(base[factor_id] * scale, 12))
            for factor_id in factor_ids
        )
        rows.append(
            HorizonWeights(
                horizon=horizon,
                weights=calibrated,
                validation_scale=round(scale, 12),
            )
        )
    training_ids = tuple(event.event_id for event in _ordered(training))
    validation_ids = tuple(event.event_id for event in _ordered(validation))
    return FittedModel.build(
        horizon_weights=tuple(rows),
        training_event_ids=training_ids,
        validation_event_ids=validation_ids,
    )


def _direction(value: float) -> str:
    if value > 1e-12:
        return "UP"
    if value < -1e-12:
        return "DOWN"
    return "FLAT"


def seal_holdout_predictions(
    *,
    run_id: str,
    sealed_at: datetime,
    model: FittedModel,
    blind_events: Sequence[BlindHoldoutEvent],
    calendar: SaudiTradingCalendar,
) -> SealedPredictionPacket:
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id is required")
    _require_aware(sealed_at, "sealed_at")
    if not isinstance(model, FittedModel):
        raise ValueError("model must be a FittedModel")
    model.verify()
    if not isinstance(calendar, SaudiTradingCalendar):
        raise ValueError("a governed SaudiTradingCalendar is required")
    rows = tuple(blind_events)
    if any(not isinstance(event, BlindHoldoutEvent) for event in rows):
        raise ValueError("blind_events must contain BlindHoldoutEvent records")
    blind_event_ids = [event.event_id for event in rows]
    if len(blind_event_ids) != len(set(blind_event_ids)):
        raise ValueError("blind holdout event IDs must be unique")
    fitted_event_ids = set(model.training_event_ids) | set(
        model.validation_event_ids
    )
    if fitted_event_ids & set(blind_event_ids):
        raise ValueError("HOLDOUT_EVENT_ID_OVERLAPS_MODEL_FIT")
    for event in rows:
        expected_cutoffs = _maturity_cutoffs(
            prediction_at=event.prediction_at,
            event_at=event.event_at,
            calendar=calendar,
        )
        if tuple(
            (horizon, _utc(cutoff))
            for horizon, cutoff in event.outcome_not_before
        ) != tuple(
            (horizon, _utc(cutoff))
            for horizon, cutoff in expected_cutoffs
        ):
            raise ValueError("BLIND_HOLDOUT_MATURITY_CUTOFF_MISMATCH")
    model_factor_sets = {
        frozenset(factor_id for factor_id, _ in item.weights)
        for item in model.horizon_weights
    }
    if len(model_factor_sets) != 1:
        raise ValueError("model horizons must use the same exact factor set")
    _require_uniform_factor_set(
        rows,
        expected=next(iter(model_factor_sets)),
    )
    blind_payload = [event.to_dict() for event in rows]
    predictions: list[HoldoutPrediction] = []
    for event in sorted(rows, key=lambda item: item.event_id):
        cutoff_by_horizon = dict(event.outcome_not_before)
        for horizon in ALL_HORIZONS:
            score = round(
                _score_factors(event.factors, model.weights_for(horizon)), 12
            )
            _finite(score, "sealed prediction score")
            predictions.append(
                HoldoutPrediction(
                    event_id=event.event_id,
                    official_code=event.official_code,
                    cohort=event.cohort,
                    horizon=horizon,
                    score=score,
                    direction=_direction(score),
                    prediction_at=event.prediction_at,
                    event_at=event.event_at,
                    outcome_not_before=cutoff_by_horizon[horizon],
                )
            )
    unsigned = {
        "run_id": run_id,
        "sealed_at": sealed_at.isoformat(),
        "model_fingerprint": model.fingerprint,
        "blind_event_sha256": _canonical_sha256(blind_payload),
        "predictions": [item.to_dict() for item in predictions],
    }
    return SealedPredictionPacket(
        run_id=run_id,
        sealed_at=sealed_at,
        model_fingerprint=model.fingerprint,
        blind_event_sha256=str(unsigned["blind_event_sha256"]),
        predictions=tuple(predictions),
        seal_sha256=_canonical_sha256(unsigned),
    )


def evaluate_sealed_holdout(
    packet: SealedPredictionPacket,
    vault: HoldoutOutcomeVault,
    *,
    scored_at: datetime,
) -> dict[str, object]:
    _require_aware(scored_at, "scored_at")
    packet.verify()
    vault.verify()
    if _utc(scored_at) < _utc(packet.sealed_at):
        raise ValueError("scored_at cannot precede sealed_at")
    outcomes = {
        (entry.event_id, outcome.horizon): outcome
        for entry in vault.entries
        for outcome in entry.outcomes
    }
    expected = {(item.event_id, item.horizon) for item in packet.predictions}
    if expected != set(outcomes):
        raise ValueError("HOLDOUT_PREDICTION_OUTCOME_DENOMINATOR_MISMATCH")
    if any(
        _utc(outcomes[(item.event_id, item.horizon)].known_at)
        <= _utc(item.prediction_at)
        for item in packet.predictions
    ):
        raise ValueError("HOLDOUT_OUTCOME_LEAKAGE_AT_PREDICTION_CUTOFF")
    if any(
        _utc(outcomes[(item.event_id, item.horizon)].known_at)
        < _utc(item.outcome_not_before)
        for item in packet.predictions
    ):
        raise ValueError("HOLDOUT_HORIZON_MINIMUM_MATURITY_NOT_MET")
    if any(
        _utc(outcome.known_at) > _utc(packet.sealed_at)
        for outcome in outcomes.values()
    ):
        raise ValueError("HOLDOUT_OUTCOME_NOT_AVAILABLE_AT_SEAL")
    if any(_utc(outcome.known_at) > _utc(scored_at) for outcome in outcomes.values()):
        raise ValueError("HOLDOUT_OUTCOME_NOT_YET_AVAILABLE")
    metrics: dict[str, dict[str, object]] = {}
    for horizon in ALL_HORIZONS:
        selected = [item for item in packet.predictions if item.horizon is horizon]
        absolute_errors = [
            abs(
                _safe_sum(
                    (
                        item.score,
                        -outcomes[(item.event_id, horizon)].excess_return,
                    ),
                    "holdout metric arithmetic",
                )
            )
            for item in selected
        ]
        hits = [
            item.direction == _direction(outcomes[(item.event_id, horizon)].excess_return)
            for item in selected
        ]
        metrics[horizon.value] = {
            "event_count": len(selected),
            "mean_absolute_error": round(
                _safe_sum(absolute_errors, "holdout metric arithmetic")
                / len(absolute_errors),
                12,
            ),
            "directional_hit_rate": round(sum(hits) / len(hits), 12),
        }
    return {
        "status": "UNAUTHENTICATED_HOLDOUT_METRICS_COMPUTED",
        "run_id": packet.run_id,
        "sealed_at": packet.sealed_at.isoformat(),
        "scored_at": scored_at.isoformat(),
        "seal_sha256": packet.seal_sha256,
        "outcome_vault_sha256": vault.vault_sha256,
        "metrics": metrics,
        "probability": None,
        "recommendation": None,
        "authenticated": False,
        "report_is_market_evidence": False,
        "claim_boundary": (
            "Retrospective out-of-sample research only; labels were mature at seal "
            "time, with no independent custodian, forecast-accuracy, or trading claim"
        ),
    }


def prepare_nightly_run(
    events: Iterable[HistoricalEvent],
    *,
    run_id: str,
    run_at: datetime,
    calendar: SaudiTradingCalendar,
    lookback_years: int = 10,
    minimum_primary: int = 50,
    minimum_probe: int = 300,
    coverage_tolerance_days: int = 31,
    maturity_buffer_days: int = 370,
    maximum_coverage_gap_days: int = 396,
) -> NightlyPreparation:
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id is required")
    _require_aware(run_at, "run_at")
    if not isinstance(calendar, SaudiTradingCalendar):
        raise ValueError("a governed SaudiTradingCalendar is required")
    integer_policy = (
        lookback_years,
        minimum_primary,
        minimum_probe,
        coverage_tolerance_days,
        maturity_buffer_days,
        maximum_coverage_gap_days,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in integer_policy):
        raise ValueError("nightly policy values must be integers")
    if lookback_years <= 0 or minimum_primary < 3 or minimum_probe < 3:
        raise ValueError("lookback and cohort minimums must be positive")
    if coverage_tolerance_days < 0 or maturity_buffer_days < 0:
        raise ValueError("coverage and maturity policy days cannot be negative")
    if coverage_tolerance_days > MAX_COVERAGE_TOLERANCE_DAYS:
        raise ValueError("coverage_tolerance_days exceeds the governed maximum")
    if maturity_buffer_days > MAX_MATURITY_BUFFER_DAYS:
        raise ValueError("maturity_buffer_days exceeds the governed maximum")
    maximum_gap_days = maximum_coverage_gap_days
    if maximum_gap_days <= 0:
        raise ValueError("maximum_coverage_gap_days must be positive")
    if maximum_gap_days > MAX_COVERAGE_GAP_DAYS:
        raise ValueError("maximum_coverage_gap_days exceeds the governed maximum")
    rows = _ordered(events)
    if rows:
        _require_uniform_factor_set(rows)
    earliest = _years_before(run_at, lookback_years)
    for event in rows:
        if not _utc(earliest) <= _utc(event.prediction_at) <= _utc(run_at):
            raise ValueError("PREDICTION_OUTSIDE_GOVERNED_LOOKBACK_WINDOW")
        if not _utc(earliest) <= _utc(event.event_at) <= _utc(run_at):
            raise ValueError("EVENT_OUTSIDE_GOVERNED_LOOKBACK_WINDOW")
        if _utc(event.evidence_known_at) > _utc(run_at):
            raise ValueError("EVENT_EVIDENCE_NOT_KNOWN_AT_RUN_CUTOFF")
        if any(
            _utc(outcome.known_at) > _utc(run_at)
            for outcome in event.outcomes
        ):
            raise ValueError("OUTCOME_NOT_KNOWN_AT_RUN_CUTOFF")
        _validate_calendar_outcome_maturity(event, calendar)
    counts = {
        Cohort.PRIMARY.value: sum(event.cohort is Cohort.PRIMARY for event in rows),
        Cohort.PROBE.value: sum(event.cohort is Cohort.PROBE for event in rows),
        "TOTAL": len(rows),
    }
    reasons: list[str] = []
    if counts[Cohort.PRIMARY.value] < minimum_primary:
        reasons.append("PRIMARY_EVENT_MINIMUM_NOT_MET")
    if counts[Cohort.PROBE.value] < minimum_probe:
        reasons.append("PROBE_EVENT_MINIMUM_NOT_MET")
    coverage_audit, coverage_reasons = _build_coverage_audit(
        rows,
        run_at=run_at,
        earliest=earliest,
        lookback_years=lookback_years,
        coverage_tolerance_days=coverage_tolerance_days,
        maturity_buffer_days=maturity_buffer_days,
        maximum_gap_days=maximum_gap_days,
    )
    reasons.extend(coverage_reasons)
    if reasons:
        return NightlyPreparation(
            status="STOP_TRAINING",
            reasons=tuple(reasons),
            counts=counts,
            coverage_audit=coverage_audit,
        )
    try:
        split = build_temporal_split(
            rows,
            calendar=calendar,
            cohort_minimums={
                Cohort.PRIMARY: minimum_primary,
                Cohort.PROBE: minimum_probe,
            },
        )
    except CausalTemporalSplitError:
        return NightlyPreparation(
            status="STOP_TRAINING",
            reasons=("CAUSAL_TEMPORAL_SPLIT_MINIMUMS_NOT_MET",),
            counts=counts,
            coverage_audit=coverage_audit,
        )
    model = fit_and_calibrate(split.training, split.validation)
    packet = seal_holdout_predictions(
        run_id=run_id,
        sealed_at=run_at,
        model=model,
        blind_events=split.blind_holdout,
        calendar=calendar,
    )
    return NightlyPreparation(
        # This library API receives Python objects and cannot prove that they
        # came from the artifact bytes authenticated by the receipt.  The CLI
        # is the only boundary allowed to promote this structural result.
        status="UNAUTHENTICATED_SEALED_AWAITING_FINAL_SCORE",
        reasons=(),
        counts=counts,
        split=split,
        model=model,
        sealed_packet=packet,
        coverage_audit=coverage_audit,
    )


def historical_event_from_mapping(
    payload: Mapping[str, Any],
    *,
    security_master: SaudiSecurityMaster,
    admission: VerifiedSaudiAdmission,
) -> HistoricalEvent:
    """Parse an explicit JSON-compatible event record without silent defaults."""

    required = {
        "event_id",
        "official_code",
        "prediction_at",
        "event_at",
        "evidence_known_at",
        "cohort",
        "event_type",
        "source_id",
        "source_role",
        "rights_status",
        "factors",
        "outcomes",
    }
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extra = sorted(set(payload) - required)
        raise ValueError(f"event fields mismatch; missing={missing}; extra={extra}")
    require_verified_saudi_admission(
        admission, purpose=AdmissionPurpose.NIGHTLY_MODEL_USE
    )

    factors_payload = payload["factors"]
    outcomes_payload = payload["outcomes"]
    if not isinstance(factors_payload, list) or not isinstance(outcomes_payload, list):
        raise ValueError("factors and outcomes must be arrays")
    factor_fields = {"factor_id", "value", "known_at", "source_id", "rights_status"}
    outcome_fields = {"horizon", "excess_return", "known_at", "price_basis"}
    if any(not isinstance(item, dict) or set(item) != factor_fields for item in factors_payload):
        raise ValueError("factor entries must use the strict governed fields")
    if any(not isinstance(item, dict) or set(item) != outcome_fields for item in outcomes_payload):
        raise ValueError("outcome entries must use the strict governed fields")
    factors = tuple(
        FactorObservation(
            factor_id=_json_string(item["factor_id"], "factor_id"),
            value=_json_number(item["value"], "factor value"),
            known_at=_json_timestamp(item["known_at"], "factor known_at"),
            source_id=_json_string(item["source_id"], "factor source_id"),
            rights_status=_json_string(
                item["rights_status"], "factor rights_status"
            ),
        )
        for item in factors_payload
    )
    outcomes = tuple(
        OutcomeObservation(
            horizon=Horizon(_json_string(item["horizon"], "outcome horizon")),
            excess_return=_json_number(
                item["excess_return"], "outcome excess_return"
            ),
            known_at=_json_timestamp(item["known_at"], "outcome known_at"),
            price_basis=_json_string(item["price_basis"], "outcome price_basis"),
        )
        for item in outcomes_payload
    )
    prediction_at = _json_timestamp(payload["prediction_at"], "prediction_at")
    official_code = _json_string(payload["official_code"], "official_code")
    try:
        identity = security_master.resolve_member(
            official_code,
            as_of=prediction_at.astimezone(ZoneInfo(RIYADH_TZ)).date(),
            known_at=prediction_at,
            segment=MAIN_MARKET,
        )
    except LookupError as exc:
        raise ValueError("IDENTITY_NOT_POINT_IN_TIME_MAIN_MARKET_MEMBER") from exc
    if identity.instrument_type != ORDINARY_EQUITY:
        raise ValueError("IDENTITY_NOT_MAIN_MARKET_ORDINARY_EQUITY")
    return HistoricalEvent(
        event_id=_json_string(payload["event_id"], "event_id"),
        official_code=official_code,
        prediction_at=prediction_at,
        event_at=_json_timestamp(payload["event_at"], "event_at"),
        evidence_known_at=_json_timestamp(
            payload["evidence_known_at"], "evidence_known_at"
        ),
        cohort=Cohort(_json_string(payload["cohort"], "cohort")),
        event_type=EventType(_json_string(payload["event_type"], "event_type")),
        source_id=_json_string(payload["source_id"], "source_id"),
        source_role=_json_string(payload["source_role"], "source_role"),
        rights_status=_json_string(payload["rights_status"], "rights_status"),
        factors=factors,
        outcomes=outcomes,
        denominator_complete=True,
        corporate_actions_reconciled=True,
        identity_verified=True,
    )


def sealed_prediction_packet_from_mapping(
    payload: Mapping[str, Any],
) -> SealedPredictionPacket:
    required = {
        "run_id",
        "sealed_at",
        "model_fingerprint",
        "blind_event_sha256",
        "predictions",
        "seal_sha256",
    }
    if set(payload) != required:
        raise ValueError("sealed packet fields mismatch")
    sealed_at = _json_timestamp(payload["sealed_at"], "sealed_at")
    raw_predictions = payload["predictions"]
    prediction_fields = {
        "event_id",
        "official_code",
        "cohort",
        "horizon",
        "score",
        "direction",
        "prediction_at",
        "event_at",
        "outcome_not_before",
    }
    if not isinstance(raw_predictions, list) or any(
        not isinstance(item, dict) or set(item) != prediction_fields
        for item in raw_predictions
    ):
        raise ValueError("sealed predictions must use the strict governed fields")
    predictions: list[HoldoutPrediction] = []
    for item in raw_predictions:
        prediction_at = _json_timestamp(item["prediction_at"], "prediction_at")
        event_at = _json_timestamp(item["event_at"], "event_at")
        outcome_not_before = _json_timestamp(
            item["outcome_not_before"], "outcome_not_before"
        )
        score = _json_number(item["score"], "prediction score")
        direction = _json_string(item["direction"], "prediction direction")
        if direction not in {"UP", "DOWN", "FLAT"}:
            raise ValueError("prediction direction is invalid")
        predictions.append(
            HoldoutPrediction(
                event_id=_json_string(item["event_id"], "prediction event_id"),
                official_code=_json_string(
                    item["official_code"], "prediction official_code"
                ),
                cohort=Cohort(_json_string(item["cohort"], "prediction cohort")),
                horizon=Horizon(
                    _json_string(item["horizon"], "prediction horizon")
                ),
                score=score,
                direction=direction,
                prediction_at=prediction_at,
                event_at=event_at,
                outcome_not_before=outcome_not_before,
            )
    )
    packet = SealedPredictionPacket(
        run_id=_json_string(payload["run_id"], "run_id"),
        sealed_at=sealed_at,
        model_fingerprint=_json_string(
            payload["model_fingerprint"], "model_fingerprint"
        ),
        blind_event_sha256=_json_string(
            payload["blind_event_sha256"], "blind_event_sha256"
        ),
        predictions=tuple(predictions),
        seal_sha256=_json_string(payload["seal_sha256"], "seal_sha256"),
    )
    packet.verify()
    return packet


def holdout_outcome_vault_from_mapping(
    payload: Mapping[str, Any],
) -> HoldoutOutcomeVault:
    if set(payload) != {"entries", "vault_sha256"}:
        raise ValueError("outcome vault fields mismatch")
    raw_entries = payload["entries"]
    if not isinstance(raw_entries, list):
        raise ValueError("outcome vault entries must be an array")
    entries: list[OutcomeVaultEntry] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {"event_id", "outcomes"}:
            raise ValueError("outcome vault entry fields mismatch")
        raw_outcomes = raw_entry["outcomes"]
        if not isinstance(raw_outcomes, list):
            raise ValueError("outcome vault outcomes must be an array")
        outcomes: list[OutcomeObservation] = []
        for item in raw_outcomes:
            if not isinstance(item, dict) or set(item) != {
                "horizon",
                "excess_return",
                "known_at",
                "price_basis",
            }:
                raise ValueError("outcome vault observation fields mismatch")
            known_at = _json_timestamp(item["known_at"], "outcome known_at")
            outcomes.append(
                OutcomeObservation(
                    horizon=Horizon(
                        _json_string(item["horizon"], "outcome horizon")
                    ),
                    excess_return=_json_number(
                        item["excess_return"], "outcome excess_return"
                    ),
                    known_at=known_at,
                    price_basis=_json_string(
                        item["price_basis"], "outcome price_basis"
                    ),
                )
            )
        entries.append(
            OutcomeVaultEntry(
                event_id=_json_string(raw_entry["event_id"], "outcome vault event_id"),
                outcomes=tuple(outcomes),
            )
        )
    vault = HoldoutOutcomeVault(
        entries=tuple(entries),
        vault_sha256=_json_string(payload["vault_sha256"], "vault_sha256"),
    )
    vault.verify()
    if len({entry.event_id for entry in vault.entries}) != len(vault.entries):
        raise ValueError("outcome vault event_id values must be unique")
    return vault
