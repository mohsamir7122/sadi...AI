"""Unified Saudi workflows inspired by AI-Mincy donor capabilities.

These are orchestration contracts only: collectors and model providers must
plug into KU-BO's evidence/runtime gates before they can produce a decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from ..markets.saudi.config import MAIN_MARKET, RIYADH_TZ, SAR
from ..markets.saudi.identity import SaudiSecurityMaster


class WorkflowStatus(str, Enum):
    READY = "READY"
    ABSTAIN = "ABSTAIN"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class SaudiResearchRequest:
    as_of: date
    known_at: datetime
    segment: str = MAIN_MARKET
    benchmark: str = "TASI"
    max_securities: int = 100

    def __post_init__(self) -> None:
        if self.known_at.tzinfo is None or self.known_at.utcoffset() is None:
            raise ValueError("known_at must be timezone-aware")
        if self.max_securities <= 0:
            raise ValueError("max_securities must be positive")
        if self.segment != MAIN_MARKET:
            raise ValueError("Saudi v1 workflow supports Main Market only")


@dataclass(frozen=True)
class Checkpoint:
    run_id: str
    step: str
    state: str
    updated_at: datetime
    artifact_sha256: str | None = None


class ResumeLedger:
    """Append-only, idempotent run state; a later step cannot overwrite history."""

    def __init__(self) -> None:
        self._entries: list[Checkpoint] = []

    def append(self, checkpoint: Checkpoint) -> None:
        if checkpoint.updated_at.tzinfo is None or checkpoint.updated_at.utcoffset() is None:
            raise ValueError("checkpoint timestamp must be timezone-aware")
        if self._entries and checkpoint.updated_at < self._entries[-1].updated_at:
            raise ValueError("checkpoint timestamps must be monotonic")
        if any(item.run_id == checkpoint.run_id and item.step == checkpoint.step for item in self._entries):
            raise ValueError("checkpoint step already exists; append a new step instead")
        self._entries.append(checkpoint)

    def latest(self, run_id: str) -> Checkpoint | None:
        entries = [item for item in self._entries if item.run_id == run_id]
        return entries[-1] if entries else None


@dataclass(frozen=True)
class SaudiObservation:
    official_code: str
    observed_at: datetime
    source_id: str
    latency_class: str
    close_sar: float | None
    volume: float | None
    evidence_class: str

    def __post_init__(self) -> None:
        if len(self.official_code) != 4 or not self.official_code.isdigit():
            raise ValueError("observations require the official four-digit Saudi code")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.latency_class not in {"REAL_TIME", "DELAYED", "END_OF_DAY"}:
            raise ValueError("latency_class must be explicit")
        if self.close_sar is not None and self.close_sar < 0:
            raise ValueError("close_sar cannot be negative")


class SaudiOpportunityScanner:
    """Create context leads only; no recommendation or probability is emitted."""

    def __init__(self, master: SaudiSecurityMaster):
        self.master = master

    def scan(self, observations: Iterable[SaudiObservation], *, request: SaudiResearchRequest) -> dict[str, Any]:
        leads: list[dict[str, Any]] = []
        rejected: list[dict[str, str]] = []
        for observation in observations:
            try:
                security = self.master.resolve(observation.official_code, as_of=request.as_of, known_at=request.known_at)
            except LookupError as exc:
                rejected.append({"official_code": observation.official_code, "reason": str(exc)})
                continue
            if observation.evidence_class != "OFFICIAL_VERIFICATION":
                rejected.append({"official_code": observation.official_code, "reason": "CONTEXT_ONLY_SOURCE"})
                continue
            leads.append({
                "official_code": security.official_code,
                "symbol": security.symbol_en,
                "segment": security.segment,
                "currency": SAR,
                "latency_class": observation.latency_class,
                "status": "CANDIDATE_CONTEXT_ONLY",
            })
        return {
            "market": "SAUDI_EXCHANGE",
            "as_of": request.as_of.isoformat(),
            "known_at": request.known_at.isoformat(),
            "status": WorkflowStatus.READY.value if leads else WorkflowStatus.ABSTAIN.value,
            "leads": leads[: request.max_securities],
            "rejected": rejected,
            "claim_boundary": "No recommendation, probability, accuracy, or execution claim",
        }


@dataclass(frozen=True)
class PortfolioPosition:
    official_code: str
    quantity: float
    average_cost_sar: float


class SaudiPortfolioValidator:
    """Validate a SAR snapshot structurally; never places or infers orders."""

    def validate(self, *, currency: str, positions: Iterable[PortfolioPosition], as_of: date, known_at: datetime) -> dict[str, Any]:
        errors: list[str] = []
        if currency != SAR:
            errors.append("CURRENCY_MUST_BE_SAR")
        if known_at.tzinfo is None or known_at.utcoffset() is None:
            errors.append("KNOWN_AT_MUST_BE_AWARE")
        normalized: list[dict[str, Any]] = []
        for position in positions:
            if len(position.official_code) != 4 or not position.official_code.isdigit():
                errors.append("OFFICIAL_CODE_REQUIRED")
            if position.quantity < 0 or position.average_cost_sar < 0:
                errors.append("NEGATIVE_POSITION_VALUE")
            normalized.append({"official_code": position.official_code, "quantity": position.quantity, "average_cost_sar": position.average_cost_sar})
        return {"status": WorkflowStatus.BLOCKED.value if errors else WorkflowStatus.READY.value, "currency": currency, "as_of": as_of.isoformat(), "positions": normalized, "errors": sorted(set(errors)), "claim_boundary": "Structural validation only; no execution"}
