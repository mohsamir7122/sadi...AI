"""Governed Saudi Exchange research scan thirty minutes after the open."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from ..markets.saudi.calendar import SaudiTradingCalendar
from ..markets.saudi.config import RIYADH_TZ, SAR
from .nightly_lab import (
    ALL_HORIZONS,
    ALLOWED_RIGHTS,
    ALLOWED_SOURCE_ROLES,
    FactorObservation,
    Horizon,
)


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
    identity_verified: bool
    factors: tuple[FactorObservation, ...]

    def __post_init__(self) -> None:
        if len(self.official_code) != 4 or not self.official_code.isdigit():
            raise ValueError("official_code must be a four-digit Saudi code")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if self.source_role not in ALLOWED_SOURCE_ROLES:
            raise ValueError("source role is not admitted")
        if self.rights_status not in ALLOWED_RIGHTS:
            raise ValueError("source rights are not admitted")
        if self.latency_class not in {"REAL_TIME", "DELAYED", "END_OF_DAY"}:
            raise ValueError("latency_class must be explicit")
        if not math.isfinite(self.last_price_sar) or self.last_price_sar <= 0:
            raise ValueError("last_price_sar must be finite and positive")
        if (
            not math.isfinite(self.average_daily_turnover_sar)
            or self.average_daily_turnover_sar <= 0
        ):
            raise ValueError("average_daily_turnover_sar must be finite and positive")
        if not self.factors:
            raise ValueError("at least one admitted factor is required")
        factor_ids = [factor.factor_id for factor in self.factors]
        if len(factor_ids) != len(set(factor_ids)):
            raise ValueError("factor IDs must be unique")

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
            "identity_verified": self.identity_verified,
            "factors": [factor.to_dict() for factor in self.factors],
        }


def _score(
    factors: Iterable[FactorObservation], weights: Mapping[str, float]
) -> float:
    return sum(weights.get(factor.factor_id, 0.0) * factor.value for factor in factors)


class SaudiPostOpenScanner:
    """Rank source-backed research candidates; never emit orders or advice."""

    def __init__(
        self,
        *,
        calendar: SaudiTradingCalendar | None = None,
        maximum_market_age: timedelta = timedelta(minutes=15),
        minimum_turnover_sar: float = 0.0,
    ) -> None:
        if maximum_market_age <= timedelta(0):
            raise ValueError("maximum_market_age must be positive")
        if minimum_turnover_sar < 0:
            raise ValueError("minimum_turnover_sar cannot be negative")
        self.calendar = calendar or SaudiTradingCalendar()
        self.maximum_market_age = maximum_market_age
        self.minimum_turnover_sar = minimum_turnover_sar
        self._riyadh = ZoneInfo(RIYADH_TZ)

    def scan(
        self,
        observations: Iterable[PostOpenObservation],
        *,
        scan_at: datetime,
        horizon_weights: Mapping[Horizon, Mapping[str, float]],
        maximum_candidates_per_horizon: int = 25,
    ) -> dict[str, object]:
        if scan_at.tzinfo is None or scan_at.utcoffset() is None:
            raise ValueError("scan_at must be timezone-aware")
        if maximum_candidates_per_horizon <= 0:
            raise ValueError("maximum_candidates_per_horizon must be positive")
        if set(horizon_weights) != set(ALL_HORIZONS):
            raise ValueError("weights are required for all five governed horizons")
        for weights in horizon_weights.values():
            if not weights or any(not math.isfinite(float(value)) for value in weights.values()):
                raise ValueError("each horizon requires finite factor weights")
        local = scan_at.astimezone(self._riyadh)
        session = self.calendar.session_for(local.date())
        if not session.is_trading_day:
            return self._abstain(local, session.closed_reason or "MARKET_CLOSED")
        continuous = next(phase for phase in session.phases if phase.name == "CONTINUOUS_TRADING")
        governed_start = continuous.start + timedelta(minutes=30)
        session_end = session.phases[-1].end
        if local < governed_start:
            return self._abstain(local, "SCAN_BEFORE_OPEN_PLUS_30_MINUTES")
        if local > session_end:
            return self._abstain(local, "SCAN_AFTER_TRADING_SESSION")

        admitted: list[PostOpenObservation] = []
        rejected: list[dict[str, str]] = []
        seen_codes: set[str] = set()
        for observation in observations:
            reason: str | None = None
            observed_local = observation.observed_at.astimezone(self._riyadh)
            if observation.official_code in seen_codes:
                reason = "DUPLICATE_SECURITY_OBSERVATION"
            elif observed_local > local:
                reason = "OBSERVATION_FROM_FUTURE"
            elif local - observed_local > self.maximum_market_age:
                reason = "STALE_MARKET_OBSERVATION"
            elif observation.latency_class == "END_OF_DAY":
                reason = "END_OF_DAY_DATA_NOT_VALID_FOR_POST_OPEN_SCAN"
            elif not observation.identity_verified:
                reason = "IDENTITY_UNVERIFIED"
            elif observation.average_daily_turnover_sar < self.minimum_turnover_sar:
                reason = "LIQUIDITY_FLOOR_NOT_MET"
            elif any(factor.known_at > scan_at for factor in observation.factors):
                reason = "FEATURE_LEAKAGE_AFTER_SCAN_CUTOFF"
            if reason:
                rejected.append({"official_code": observation.official_code, "reason": reason})
                continue
            seen_codes.add(observation.official_code)
            admitted.append(observation)
        if not admitted:
            result = self._abstain(local, "NO_FRESH_ADMITTED_UNIVERSE")
            result["rejected"] = rejected
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
            rows: list[dict[str, object]] = []
            for rank, (score, observation) in enumerate(
                scored[:maximum_candidates_per_horizon], start=1
            ):
                rows.append(
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
            by_horizon[horizon.value] = rows
        return {
            "status": "RESEARCH_CANDIDATES_READY",
            "market": "SAUDI_EXCHANGE",
            "scan_at": local.isoformat(),
            "governed_start": governed_start.isoformat(),
            "admitted_security_count": len(admitted),
            "rejected": rejected,
            "candidates_by_horizon": by_horizon,
            "claim_boundary": (
                "Source-backed idea candidates only; no personalized recommendation, "
                "probability, order, or execution"
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


def post_open_observation_from_mapping(payload: Mapping[str, Any]) -> PostOpenObservation:
    required = {
        "official_code",
        "observed_at",
        "source_id",
        "source_role",
        "rights_status",
        "latency_class",
        "last_price_sar",
        "average_daily_turnover_sar",
        "identity_verified",
        "factors",
    }
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extra = sorted(set(payload) - required)
        raise ValueError(f"observation fields mismatch; missing={missing}; extra={extra}")

    def timestamp(value: object, field: str) -> datetime:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be an ISO timestamp string")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(f"{field} must be timezone-aware")
        return parsed

    factor_payload = payload["factors"]
    if not isinstance(factor_payload, list):
        raise ValueError("factors must be an array")
    factor_fields = {"factor_id", "value", "known_at", "source_id", "rights_status"}
    if any(not isinstance(item, dict) or set(item) != factor_fields for item in factor_payload):
        raise ValueError("factor entries must use the strict governed fields")
    factors = tuple(
        FactorObservation(
            factor_id=str(item["factor_id"]),
            value=float(item["value"]),
            known_at=timestamp(item["known_at"], "factor known_at"),
            source_id=str(item["source_id"]),
            rights_status=str(item["rights_status"]),
        )
        for item in factor_payload
    )
    return PostOpenObservation(
        official_code=str(payload["official_code"]),
        observed_at=timestamp(payload["observed_at"], "observed_at"),
        source_id=str(payload["source_id"]),
        source_role=str(payload["source_role"]),
        rights_status=str(payload["rights_status"]),
        latency_class=str(payload["latency_class"]),
        last_price_sar=float(payload["last_price_sar"]),
        average_daily_turnover_sar=float(payload["average_daily_turnover_sar"]),
        identity_verified=payload["identity_verified"] is True,
        factors=factors,
    )
