"""Leakage-resistant nightly laboratory for Saudi Exchange event research.

The module is intentionally data-provider agnostic.  It accepts only evidence
that has already passed identity, rights, denominator, and corporate-action
checks.  The final holdout API accepts blinded rows, seals predictions, and
only then allows a separate outcome vault to be scored.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence


SAUDI_CODE_RE = re.compile(r"^[0-9]{4}$")
ALLOWED_SOURCE_ROLES = frozenset(
    {
        "OFFICIAL_VERIFICATION",
        "REGULATORY_EVIDENCE",
        "ISSUER_DISCLOSURE",
        "LICENSED_MARKET_DATA",
    }
)
ALLOWED_RIGHTS = frozenset(
    {"PUBLIC_RESEARCH_ALLOWED", "LICENSED_RESEARCH_ALLOWED"}
)


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


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


def _finite(value: float, field: str) -> None:
    if isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be finite")


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
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
        if not self.factor_id.startswith("F9-"):
            raise ValueError("factor_id must start with F9-")
        _finite(self.value, "factor value")
        _require_aware(self.known_at, "factor known_at")
        if not self.source_id.strip():
            raise ValueError("factor source_id is required")
        if self.rights_status not in ALLOWED_RIGHTS:
            raise ValueError("factor rights are not admitted for research")

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
        _finite(self.excess_return, "outcome excess_return")
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
        if not self.event_id.strip():
            raise ValueError("event_id is required")
        if not SAUDI_CODE_RE.fullmatch(self.official_code):
            raise ValueError("official_code must be a four-digit Saudi code")
        for field, value in (
            ("prediction_at", self.prediction_at),
            ("event_at", self.event_at),
            ("evidence_known_at", self.evidence_known_at),
        ):
            _require_aware(value, field)
        if self.prediction_at > self.event_at:
            raise ValueError("prediction_at cannot follow event_at")
        if self.evidence_known_at < self.event_at:
            raise ValueError("event evidence cannot be known before the event")
        if self.source_role not in ALLOWED_SOURCE_ROLES:
            raise ValueError("event source_role is not authoritative")
        if self.rights_status not in ALLOWED_RIGHTS:
            raise ValueError("event rights are not admitted for research")
        if not self.source_id.strip():
            raise ValueError("event source_id is required")
        if not self.factors:
            raise ValueError("at least one Point-in-Time factor is required")
        factor_ids = [factor.factor_id for factor in self.factors]
        if len(factor_ids) != len(set(factor_ids)):
            raise ValueError("factor IDs must be unique within an event")
        if any(factor.known_at > self.prediction_at for factor in self.factors):
            raise ValueError("FEATURE_LEAKAGE_AFTER_PREDICTION_CUTOFF")
        horizons = [outcome.horizon for outcome in self.outcomes]
        if len(horizons) != len(set(horizons)):
            raise ValueError("outcome horizons must be unique within an event")
        if set(horizons) != set(ALL_HORIZONS):
            raise ValueError("all five governed horizons are required")
        if any(outcome.known_at <= self.prediction_at for outcome in self.outcomes):
            raise ValueError("OUTCOME_LEAKAGE_AT_PREDICTION_CUTOFF")
        if any(outcome.known_at < self.event_at for outcome in self.outcomes):
            raise ValueError("outcome cannot be known before event_at")
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
            "denominator_complete": self.denominator_complete,
            "corporate_actions_reconciled": self.corporate_actions_reconciled,
            "identity_verified": self.identity_verified,
        }


@dataclass(frozen=True)
class BlindHoldoutEvent:
    event_id: str
    official_code: str
    prediction_at: datetime
    cohort: Cohort
    factors: tuple[FactorObservation, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "official_code": self.official_code,
            "prediction_at": self.prediction_at.isoformat(),
            "cohort": self.cohort.value,
            "factors": [factor.to_dict() for factor in self.factors],
        }


@dataclass(frozen=True)
class OutcomeVaultEntry:
    event_id: str
    outcomes: tuple[OutcomeObservation, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
        }


@dataclass(frozen=True)
class HoldoutOutcomeVault:
    entries: tuple[OutcomeVaultEntry, ...]
    vault_sha256: str

    @classmethod
    def build(cls, entries: Iterable[OutcomeVaultEntry]) -> "HoldoutOutcomeVault":
        ordered = tuple(sorted(entries, key=lambda item: item.event_id))
        payload = [entry.to_dict() for entry in ordered]
        return cls(entries=ordered, vault_sha256=_canonical_sha256(payload))

    def verify(self) -> None:
        actual = _canonical_sha256([entry.to_dict() for entry in self.entries])
        if actual != self.vault_sha256:
            raise ValueError("HOLDOUT_OUTCOME_VAULT_HASH_MISMATCH")


@dataclass(frozen=True)
class TemporalSplit:
    training: tuple[HistoricalEvent, ...]
    validation: tuple[HistoricalEvent, ...]
    blind_holdout: tuple[BlindHoldoutEvent, ...]
    outcome_vault: HoldoutOutcomeVault


@dataclass(frozen=True)
class HorizonWeights:
    horizon: Horizon
    weights: tuple[tuple[str, float], ...]
    validation_scale: float

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

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "official_code": self.official_code,
            "cohort": self.cohort.value,
            "horizon": self.horizon.value,
            "score": self.score,
            "direction": self.direction,
            "prediction_at": self.prediction_at.isoformat(),
        }


@dataclass(frozen=True)
class SealedPredictionPacket:
    run_id: str
    sealed_at: datetime
    model_fingerprint: str
    blind_event_sha256: str
    predictions: tuple[HoldoutPrediction, ...]
    seal_sha256: str

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


def _ordered(events: Iterable[HistoricalEvent]) -> tuple[HistoricalEvent, ...]:
    return tuple(sorted(events, key=lambda item: (item.prediction_at, item.event_id)))


def _split_one_cohort(
    events: Sequence[HistoricalEvent],
) -> tuple[Sequence[HistoricalEvent], Sequence[HistoricalEvent], Sequence[HistoricalEvent]]:
    count = len(events)
    train_end = int(count * 0.60)
    validation_end = int(count * 0.80)
    if train_end < 1 or validation_end <= train_end or validation_end >= count:
        raise ValueError("each cohort needs enough rows for 60/20/20 temporal splits")
    return events[:train_end], events[train_end:validation_end], events[validation_end:]


def build_temporal_split(events: Iterable[HistoricalEvent]) -> TemporalSplit:
    rows = _ordered(events)
    ids = [event.event_id for event in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("event_id values must be unique")
    training: list[HistoricalEvent] = []
    validation: list[HistoricalEvent] = []
    holdout: list[HistoricalEvent] = []
    for cohort in Cohort:
        cohort_rows = [event for event in rows if event.cohort is cohort]
        train_rows, validation_rows, holdout_rows = _split_one_cohort(cohort_rows)
        training.extend(train_rows)
        validation.extend(validation_rows)
        holdout.extend(holdout_rows)
    blind = tuple(
        BlindHoldoutEvent(
            event_id=event.event_id,
            official_code=event.official_code,
            prediction_at=event.prediction_at,
            cohort=event.cohort,
            factors=event.factors,
        )
        for event in _ordered(holdout)
    )
    vault = HoldoutOutcomeVault.build(
        OutcomeVaultEntry(event_id=event.event_id, outcomes=event.outcomes)
        for event in holdout
    )
    return TemporalSplit(
        training=_ordered(training),
        validation=_ordered(validation),
        blind_holdout=blind,
        outcome_vault=vault,
    )


def _outcome(event: HistoricalEvent, horizon: Horizon) -> float:
    return next(item.excess_return for item in event.outcomes if item.horizon is horizon)


def _score_factors(factors: Iterable[FactorObservation], weights: Mapping[str, float]) -> float:
    return sum(weights.get(factor.factor_id, 0.0) * factor.value for factor in factors)


def fit_and_calibrate(
    training: Sequence[HistoricalEvent], validation: Sequence[HistoricalEvent]
) -> FittedModel:
    if not training or not validation:
        raise ValueError("training and validation rows are required")
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
            raw[factor_id] = sum(feature * outcome for feature, outcome in pairs)
        denominator = sum(abs(value) for value in raw.values())
        base = {
            factor_id: (value / denominator if denominator else 0.0)
            for factor_id, value in raw.items()
        }
        validation_pairs = [
            (_score_factors(event.factors, base), _outcome(event, horizon))
            for event in validation
        ]
        scale_denominator = sum(score * score for score, _ in validation_pairs)
        scale = (
            sum(score * outcome for score, outcome in validation_pairs) / scale_denominator
            if scale_denominator
            else 0.0
        )
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
    payload = {
        "horizon_weights": [item.to_dict() for item in rows],
        "training_event_ids": training_ids,
        "validation_event_ids": validation_ids,
    }
    return FittedModel(
        horizon_weights=tuple(rows),
        training_event_ids=training_ids,
        validation_event_ids=validation_ids,
        fingerprint=_canonical_sha256(payload),
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
) -> SealedPredictionPacket:
    if not run_id.strip():
        raise ValueError("run_id is required")
    _require_aware(sealed_at, "sealed_at")
    blind_payload = [event.to_dict() for event in blind_events]
    predictions = tuple(
        HoldoutPrediction(
            event_id=event.event_id,
            official_code=event.official_code,
            cohort=event.cohort,
            horizon=horizon,
            score=round(_score_factors(event.factors, model.weights_for(horizon)), 12),
            direction=_direction(_score_factors(event.factors, model.weights_for(horizon))),
            prediction_at=event.prediction_at,
        )
        for event in sorted(blind_events, key=lambda item: item.event_id)
        for horizon in ALL_HORIZONS
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
        predictions=predictions,
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
    if scored_at < packet.sealed_at:
        raise ValueError("scored_at cannot precede sealed_at")
    outcomes = {
        (entry.event_id, outcome.horizon): outcome
        for entry in vault.entries
        for outcome in entry.outcomes
    }
    expected = {(item.event_id, item.horizon) for item in packet.predictions}
    if expected != set(outcomes):
        raise ValueError("HOLDOUT_PREDICTION_OUTCOME_DENOMINATOR_MISMATCH")
    if any(outcome.known_at > scored_at for outcome in outcomes.values()):
        raise ValueError("HOLDOUT_OUTCOME_NOT_YET_AVAILABLE")
    metrics: dict[str, dict[str, object]] = {}
    for horizon in ALL_HORIZONS:
        selected = [item for item in packet.predictions if item.horizon is horizon]
        absolute_errors = [
            abs(item.score - outcomes[(item.event_id, horizon)].excess_return)
            for item in selected
        ]
        hits = [
            item.direction == _direction(outcomes[(item.event_id, horizon)].excess_return)
            for item in selected
        ]
        metrics[horizon.value] = {
            "event_count": len(selected),
            "mean_absolute_error": round(sum(absolute_errors) / len(absolute_errors), 12),
            "directional_hit_rate": round(sum(hits) / len(hits), 12),
        }
    return {
        "status": "FINAL_HOLDOUT_SCORED",
        "run_id": packet.run_id,
        "sealed_at": packet.sealed_at.isoformat(),
        "scored_at": scored_at.isoformat(),
        "seal_sha256": packet.seal_sha256,
        "outcome_vault_sha256": vault.vault_sha256,
        "metrics": metrics,
        "probability": None,
        "recommendation": None,
        "claim_boundary": "Historical out-of-sample research only; no forecast-accuracy or trading claim",
    }


def prepare_nightly_run(
    events: Iterable[HistoricalEvent],
    *,
    run_id: str,
    run_at: datetime,
    lookback_years: int = 10,
    minimum_primary: int = 50,
    minimum_probe: int = 300,
) -> NightlyPreparation:
    _require_aware(run_at, "run_at")
    if lookback_years <= 0 or minimum_primary <= 0 or minimum_probe <= 0:
        raise ValueError("lookback and cohort minimums must be positive")
    rows = _ordered(events)
    earliest = _years_before(run_at, lookback_years)
    for event in rows:
        if not earliest <= event.event_at <= run_at:
            raise ValueError("EVENT_OUTSIDE_GOVERNED_LOOKBACK_WINDOW")
        if event.evidence_known_at > run_at:
            raise ValueError("EVENT_EVIDENCE_NOT_KNOWN_AT_RUN_CUTOFF")
        if any(outcome.known_at > run_at for outcome in event.outcomes):
            raise ValueError("OUTCOME_NOT_KNOWN_AT_RUN_CUTOFF")
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
    if reasons:
        return NightlyPreparation(
            status="STOP_TRAINING",
            reasons=tuple(reasons),
            counts=counts,
        )
    split = build_temporal_split(rows)
    model = fit_and_calibrate(split.training, split.validation)
    packet = seal_holdout_predictions(
        run_id=run_id,
        sealed_at=run_at,
        model=model,
        blind_events=split.blind_holdout,
    )
    return NightlyPreparation(
        status="SEALED_AWAITING_FINAL_SCORE",
        reasons=(),
        counts=counts,
        split=split,
        model=model,
        sealed_packet=packet,
    )


def historical_event_from_mapping(payload: Mapping[str, Any]) -> HistoricalEvent:
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
        "denominator_complete",
        "corporate_actions_reconciled",
        "identity_verified",
    }
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extra = sorted(set(payload) - required)
        raise ValueError(f"event fields mismatch; missing={missing}; extra={extra}")

    def timestamp(value: object, field: str) -> datetime:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be an ISO timestamp string")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _require_aware(parsed, field)
        return parsed

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
            factor_id=str(item["factor_id"]),
            value=float(item["value"]),
            known_at=timestamp(item["known_at"], "factor known_at"),
            source_id=str(item["source_id"]),
            rights_status=str(item["rights_status"]),
        )
        for item in factors_payload
    )
    outcomes = tuple(
        OutcomeObservation(
            horizon=Horizon(str(item["horizon"])),
            excess_return=float(item["excess_return"]),
            known_at=timestamp(item["known_at"], "outcome known_at"),
            price_basis=str(item["price_basis"]),
        )
        for item in outcomes_payload
    )
    return HistoricalEvent(
        event_id=str(payload["event_id"]),
        official_code=str(payload["official_code"]),
        prediction_at=timestamp(payload["prediction_at"], "prediction_at"),
        event_at=timestamp(payload["event_at"], "event_at"),
        evidence_known_at=timestamp(payload["evidence_known_at"], "evidence_known_at"),
        cohort=Cohort(str(payload["cohort"])),
        event_type=EventType(str(payload["event_type"])),
        source_id=str(payload["source_id"]),
        source_role=str(payload["source_role"]),
        rights_status=str(payload["rights_status"]),
        factors=factors,
        outcomes=outcomes,
        denominator_complete=payload["denominator_complete"] is True,
        corporate_actions_reconciled=payload["corporate_actions_reconciled"] is True,
        identity_verified=payload["identity_verified"] is True,
    )
