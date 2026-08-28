"""Governed Saudi Exchange research scan thirty minutes after the open."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from ..markets.saudi.calendar import SaudiTradingCalendar
from ..markets.saudi.config import RIYADH_TZ, SAR
from ..markets.saudi.identity import SaudiSecurityMaster
from ..saudi_admission import (
    MAX_POST_OPEN_CANDIDATES_PER_HORIZON,
    MAX_POST_OPEN_MARKET_AGE_MINUTES,
    AdmissionPurpose,
    VerifiedSaudiAdmission,
    require_verified_saudi_admission,
)
from .nightly_lab import (
    ALL_HORIZONS,
    ALLOWED_SOURCE_ROLES,
    FactorObservation,
    Horizon,
)
from .rights import RightsUse, require_rights


def _is_finite_json_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _utc(value: datetime) -> datetime:
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValueError("post-open timestamp is outside the supported UTC range") from exc


@dataclass(frozen=True)
class PostOpenObservation:
    official_code: str
    observed_at: datetime
    source_id: str
    source_role: str
    rights_status: str
    latency_class: str
    last_price_sar: float
    average_daily_turnover_sar: float
    factors: tuple[FactorObservation, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.official_code, str)
            or len(self.official_code) != 4
            or not self.official_code.isdigit()
        ):
            raise ValueError("official_code must be a four-digit Saudi code")
        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at must be timezone-aware")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id is required")
        if not isinstance(self.source_role, str) or self.source_role not in ALLOWED_SOURCE_ROLES:
            raise ValueError("source role is not admitted")
        if not isinstance(self.rights_status, str):
            raise ValueError("source rights are not admitted")
        require_rights(self.rights_status, use=RightsUse.MODEL_USE)
        if not isinstance(self.latency_class, str) or self.latency_class not in {
            "REAL_TIME",
            "DELAYED",
            "END_OF_DAY",
        }:
            raise ValueError("latency_class must be explicit")
        if (
            not _is_finite_json_number(self.last_price_sar)
            or self.last_price_sar <= 0
        ):
            raise ValueError("last_price_sar must be finite and positive")
        object.__setattr__(self, "last_price_sar", float(self.last_price_sar))
        if (
            not _is_finite_json_number(self.average_daily_turnover_sar)
            or self.average_daily_turnover_sar <= 0
        ):
            raise ValueError("average_daily_turnover_sar must be finite and positive")
        object.__setattr__(
            self,
            "average_daily_turnover_sar",
            float(self.average_daily_turnover_sar),
        )
        if (
            not isinstance(self.factors, tuple)
            or not self.factors
            or any(
                not isinstance(factor, FactorObservation)
                for factor in self.factors
            )
        ):
            raise ValueError(
                "factors must be a non-empty tuple of governed FactorObservation records"
            )
        factor_ids = [factor.factor_id for factor in self.factors]
        if len(factor_ids) != len(set(factor_ids)):
            raise ValueError("factor IDs must be unique")
        if any(
            _utc(factor.known_at) > _utc(self.observed_at)
            for factor in self.factors
        ):
            raise ValueError("factor cannot be known after its market observation")

    def to_dict(self) -> dict[str, object]:
        return {
            "official_code": self.official_code,
            "observed_at": self.observed_at.isoformat(),
            "source_id": self.source_id,
            "source_role": self.source_role,
            "rights_status": self.rights_status,
            "latency_class": self.latency_class,
            "last_price_sar": self.last_price_sar,
            "average_daily_turnover_sar": self.average_daily_turnover_sar,
            "factors": [factor.to_dict() for factor in self.factors],
        }


def _score(
    factors: Iterable[FactorObservation], weights: Mapping[str, float]
) -> float:
    products: list[float] = []
    for factor in factors:
        product = weights[factor.factor_id] * factor.value
        if not _is_finite_json_number(product):
            raise ValueError("NON_FINITE_RESEARCH_SCORE")
        products.append(product)
    try:
        score = math.fsum(products)
    except (OverflowError, ValueError) as exc:
        raise ValueError("NON_FINITE_RESEARCH_SCORE") from exc
    if not _is_finite_json_number(score):
        raise ValueError("NON_FINITE_RESEARCH_SCORE")
    return score


class SaudiPostOpenScanner:
    """Structurally rank admitted research candidates; never emit orders or advice."""

    def __init__(
        self,
        *,
        calendar: SaudiTradingCalendar | None = None,
        security_master: SaudiSecurityMaster | None = None,
        maximum_market_age: timedelta = timedelta(minutes=15),
        minimum_turnover_sar: float = 0.0,
    ) -> None:
        if not isinstance(maximum_market_age, timedelta) or maximum_market_age <= timedelta(0):
            raise ValueError("maximum_market_age must be positive")
        if maximum_market_age > timedelta(
            minutes=MAX_POST_OPEN_MARKET_AGE_MINUTES
        ):
            raise ValueError("maximum_market_age exceeds the governed maximum")
        if not _is_finite_json_number(minimum_turnover_sar) or minimum_turnover_sar < 0:
            raise ValueError("minimum_turnover_sar cannot be negative")
        self.calendar = calendar or SaudiTradingCalendar()
        self.security_master = security_master
        self.maximum_market_age = maximum_market_age
        self.minimum_turnover_sar = minimum_turnover_sar
        self._riyadh = ZoneInfo(RIYADH_TZ)

    def scan(
        self,
        observations: Iterable[PostOpenObservation],
        *,
        admission: VerifiedSaudiAdmission,
        scan_at: datetime,
        horizon_weights: Mapping[Horizon, Mapping[str, float]],
        maximum_candidates_per_horizon: int = 25,
    ) -> dict[str, object]:
        require_verified_saudi_admission(
            admission, purpose=AdmissionPurpose.POST_OPEN_MODEL_USE
        )
        if (
            not isinstance(scan_at, datetime)
            or scan_at.tzinfo is None
            or scan_at.utcoffset() is None
        ):
            raise ValueError("scan_at must be timezone-aware")
        if (
            isinstance(maximum_candidates_per_horizon, bool)
            or not isinstance(maximum_candidates_per_horizon, int)
            or maximum_candidates_per_horizon <= 0
        ):
            raise ValueError("maximum_candidates_per_horizon must be positive")
        if maximum_candidates_per_horizon > MAX_POST_OPEN_CANDIDATES_PER_HORIZON:
            raise ValueError(
                "maximum_candidates_per_horizon exceeds the governed maximum"
            )
        if not isinstance(horizon_weights, Mapping) or set(horizon_weights) != set(ALL_HORIZONS):
            raise ValueError("weights are required for all five governed horizons")
        for weights in horizon_weights.values():
            if not isinstance(weights, Mapping) or not weights or any(
                not isinstance(factor_id, str)
                or not factor_id.startswith("F9-")
                or not _is_finite_json_number(value)
                for factor_id, value in weights.items()
            ):
                raise ValueError("each horizon requires finite factor weights")
        weight_factor_sets = {
            frozenset(weights) for weights in horizon_weights.values()
        }
        if len(weight_factor_sets) != 1:
            raise ValueError("all horizons must use the same exact factor set")
        required_factor_ids = next(iter(weight_factor_sets))
        local = scan_at.astimezone(self._riyadh)
        session = self.calendar.session_for(local.date(), known_at=scan_at)
        if not session.is_trading_day:
            return self._abstain(local, session.closed_reason or "MARKET_CLOSED")
        continuous = next(phase for phase in session.phases if phase.name == "CONTINUOUS_TRADING")
        governed_start = continuous.start + timedelta(
            minutes=30,
            seconds=session.boundary_uncertainty_seconds,
        )
        governed_end = session.phases[-1].end - timedelta(
            seconds=session.boundary_uncertainty_seconds
        )
        if local < governed_start:
            return self._abstain(local, "SCAN_BEFORE_OPEN_PLUS_30_MINUTES")
        if local >= governed_end:
            return self._abstain(local, "SCAN_AFTER_TRADING_SESSION")

        if self.security_master is None:
            return self._abstain(local, "IDENTITY_MASTER_REQUIRED")

        rows = tuple(observations)
        if any(not isinstance(row, PostOpenObservation) for row in rows):
            raise ValueError("observations must be PostOpenObservation records")
        selectable = self.security_master.selectable_on(
            as_of=local.date(),
            known_at=scan_at,
        )
        expected_codes = {record.official_code for record in selectable}
        observed_counts = Counter(row.official_code for row in rows)
        observed_codes = set(observed_counts)
        if not expected_codes:
            result = self._abstain(local, "EMPTY_OR_UNVERIFIED_UNIVERSE")
            result.update(
                {
                    "denominator_complete": False,
                    "expected_security_count": 0,
                    "observed_security_count": len(observed_codes),
                    "input_record_count": len(rows),
                    "missing_official_codes": [],
                    "unexpected_official_codes": sorted(observed_codes),
                    "duplicate_official_codes": sorted(
                        code for code, count in observed_counts.items() if count != 1
                    ),
                }
            )
            return result
        missing_codes = sorted(expected_codes - observed_codes)
        unexpected_codes = sorted(observed_codes - expected_codes)
        duplicate_codes = sorted(
            code for code, count in observed_counts.items() if count != 1
        )
        if missing_codes or unexpected_codes or duplicate_codes:
            result = self._abstain(local, "INCOMPLETE_OBSERVATION_DENOMINATOR")
            result.update(
                {
                    "denominator_complete": False,
                    "expected_security_count": len(expected_codes),
                    "observed_security_count": len(observed_codes),
                    "input_record_count": len(rows),
                    "missing_official_codes": missing_codes,
                    "unexpected_official_codes": unexpected_codes,
                    "duplicate_official_codes": duplicate_codes,
                }
            )
            return result

        admitted: list[PostOpenObservation] = []
        rejected: list[dict[str, str]] = []
        seen_codes: set[str] = set()
        for observation in rows:
            reason: str | None = None
            observed_local = observation.observed_at.astimezone(self._riyadh)
            if {
                factor.factor_id for factor in observation.factors
            } != required_factor_ids:
                reason = "FACTOR_SET_MISMATCH"
            elif observed_local < continuous.start + timedelta(
                seconds=session.boundary_uncertainty_seconds
            ):
                reason = "OBSERVATION_BEFORE_GOVERNED_CONTINUOUS_TRADING"
            elif observation.official_code in seen_codes:
                reason = "DUPLICATE_SECURITY_OBSERVATION"
            elif observed_local > local:
                reason = "OBSERVATION_FROM_FUTURE"
            elif local - observed_local > self.maximum_market_age:
                reason = "STALE_MARKET_OBSERVATION"
            elif observation.latency_class == "END_OF_DAY":
                reason = "END_OF_DAY_DATA_NOT_VALID_FOR_POST_OPEN_SCAN"
            else:
                try:
                    self.security_master.resolve_selectable(
                        observation.official_code,
                        as_of=local.date(),
                        known_at=scan_at,
                    )
                except LookupError:
                    reason = "IDENTITY_NOT_SELECTABLE_MAIN_ORDINARY_EQUITY"
            if reason is None and any(
                _utc(factor.known_at) > _utc(scan_at)
                for factor in observation.factors
            ):
                reason = "FEATURE_LEAKAGE_AFTER_SCAN_CUTOFF"
            elif reason is None and any(
                local - factor.known_at.astimezone(self._riyadh)
                > self.maximum_market_age
                for factor in observation.factors
            ):
                reason = "STALE_FACTOR_OBSERVATION"
            elif (
                reason is None
                and observation.average_daily_turnover_sar
                < self.minimum_turnover_sar
            ):
                reason = "LIQUIDITY_FLOOR_NOT_MET"
            if reason:
                rejected.append({"official_code": observation.official_code, "reason": reason})
                continue
            seen_codes.add(observation.official_code)
            admitted.append(observation)
        integrity_rejected_codes = {
            item["official_code"]
            for item in rejected
            if item["reason"] != "LIQUIDITY_FLOOR_NOT_MET"
        }
        if integrity_rejected_codes:
            result = self._abstain(local, "INCOMPLETE_OBSERVATION_DENOMINATOR")
            result["rejected"] = rejected
            result.update(
                {
                    "denominator_complete": False,
                    "expected_security_count": len(expected_codes),
                    "observed_security_count": len(observed_codes),
                    "input_record_count": len(rows),
                    "missing_official_codes": sorted(integrity_rejected_codes),
                    "unexpected_official_codes": [],
                    "duplicate_official_codes": [],
                }
            )
            return result
        if not admitted:
            result = self._abstain(local, "NO_SECURITIES_MEET_LIQUIDITY_FLOOR")
            result["rejected"] = rejected
            result.update(
                {
                    "denominator_complete": True,
                    "expected_security_count": len(expected_codes),
                    "observed_security_count": len(observed_codes),
                    "input_record_count": len(rows),
                    "admitted_security_count": 0,
                }
            )
            return result

        by_horizon: dict[str, list[dict[str, object]]] = {}
        for horizon in ALL_HORIZONS:
            weights = horizon_weights[horizon]
            scored = sorted(
                (
                    (
                        round(_score(observation.factors, weights), 12),
                        observation,
                    )
                    for observation in admitted
                ),
                key=lambda item: (-item[0], item[1].official_code),
            )
            candidate_rows: list[dict[str, object]] = []
            for rank, (score, observation) in enumerate(
                scored[:maximum_candidates_per_horizon], start=1
            ):
                candidate_rows.append(
                    {
                        "rank": rank,
                        "official_code": observation.official_code,
                        "horizon": horizon.value,
                        "research_score": score,
                        "research_status": (
                            "RESEARCH_CANDIDATE" if score > 0 else "RESEARCH_WATCHLIST"
                        ),
                        "observed_at": observation.observed_at.isoformat(),
                        "latency_class": observation.latency_class,
                        "currency": SAR,
                        "last_price_sar": observation.last_price_sar,
                        "source_id": observation.source_id,
                        "probability": None,
                        "recommendation": None,
                        "order": None,
                    }
                )
            by_horizon[horizon.value] = candidate_rows
        revision = self.calendar.revision
        return {
            # The core API cannot prove that arbitrary in-memory observations
            # and weights came from the bytes bound by an admission receipt.
            # Only the CLI, which parses every object from those verified bytes,
            # may promote this structural result to an admitted status.
            "status": "UNAUTHENTICATED_RESEARCH_CANDIDATES",
            "market": "SAUDI_EXCHANGE",
            "scan_at": local.isoformat(),
            "governed_start": governed_start.isoformat(),
            "governed_end": governed_end.isoformat(),
            "calendar_revision_id": session.calendar_revision_id,
            "calendar_source_id": session.source_id,
            "evidence_class": revision.evidence_class if revision else "UNVERIFIED",
            "input_admission_authenticated": False,
            "denominator_complete": True,
            "expected_security_count": len(expected_codes),
            "observed_security_count": len(observed_codes),
            "input_record_count": len(rows),
            "admitted_security_count": len(admitted),
            "rejected": rejected,
            "candidates_by_horizon": by_horizon,
            "claim_boundary": (
                "In-memory library result only; inputs are not proven to match admission "
                "artifact bytes, and no market-evidence or trading claim is produced"
            ),
        }

    @staticmethod
    def _abstain(scan_at: datetime, reason: str) -> dict[str, object]:
        return {
            "status": "ABSTAIN",
            "market": "SAUDI_EXCHANGE",
            "scan_at": scan_at.isoformat(),
            "reason": reason,
            "candidates_by_horizon": {},
            "probability": None,
            "recommendation": None,
            "order": None,
            "claim_boundary": "No candidate or trading claim was produced",
        }


def post_open_observation_from_mapping(
    payload: Mapping[str, Any], *, admission: VerifiedSaudiAdmission
) -> PostOpenObservation:
    required = {
        "official_code",
        "observed_at",
        "source_id",
        "source_role",
        "rights_status",
        "latency_class",
        "last_price_sar",
        "average_daily_turnover_sar",
        "factors",
    }
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extra = sorted(set(payload) - required)
        raise ValueError(f"observation fields mismatch; missing={missing}; extra={extra}")
    require_verified_saudi_admission(
        admission, purpose=AdmissionPurpose.POST_OPEN_MODEL_USE
    )

    def timestamp(value: object, field: str) -> datetime:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be an ISO timestamp string")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{field} must be timezone-aware")
        return parsed

    def text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return value

    def number(value: object, field: str) -> float:
        if (
            isinstance(value, bool)
            or not _is_finite_json_number(value)
        ):
            raise ValueError(f"{field} must be a finite JSON number")
        return float(value)

    factor_payload = payload["factors"]
    if not isinstance(factor_payload, list):
        raise ValueError("factors must be an array")
    factor_fields = {"factor_id", "value", "known_at", "source_id", "rights_status"}
    if any(
        not isinstance(item, Mapping) or set(item) != factor_fields
        for item in factor_payload
    ):
        raise ValueError("factor entries must use the strict governed fields")
    factors = tuple(
        FactorObservation(
            factor_id=text(item["factor_id"], "factor_id"),
            value=number(item["value"], "factor value"),
            known_at=timestamp(item["known_at"], "factor known_at"),
            source_id=text(item["source_id"], "factor source_id"),
            rights_status=text(item["rights_status"], "factor rights_status"),
        )
        for item in factor_payload
    )
    return PostOpenObservation(
        official_code=text(payload["official_code"], "official_code"),
        observed_at=timestamp(payload["observed_at"], "observed_at"),
        source_id=text(payload["source_id"], "source_id"),
        source_role=text(payload["source_role"], "source_role"),
        rights_status=text(payload["rights_status"], "rights_status"),
        latency_class=text(payload["latency_class"], "latency_class"),
        last_price_sar=number(payload["last_price_sar"], "last_price_sar"),
        average_daily_turnover_sar=number(
            payload["average_daily_turnover_sar"],
            "average_daily_turnover_sar",
        ),
        factors=factors,
    )
