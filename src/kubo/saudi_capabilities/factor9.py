"""Governed Factor 9 foundation concepts adapted from AI-Mincy.

This module validates an admission packet; it does not turn a factor score
into a probability or permit model use when provenance, rights, or temporal
availability is incomplete.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Any


class FactorStatus(str, Enum):
    DEFINED = "DEFINED"
    ADMITTED = "ADMITTED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class FactorDefinition:
    factor_id: str
    name: str
    direction: str
    data_role: str
    source_ids: tuple[str, ...]
    available_from: datetime
    freshness_hours: int
    rights_status: str
    point_in_time_tested: bool
    status: FactorStatus = FactorStatus.DEFINED

    def __post_init__(self) -> None:
        if not self.factor_id.startswith("F9-"):
            raise ValueError("Factor 9 IDs must start with F9-")
        if self.direction not in {"POSITIVE", "NEGATIVE", "NEUTRAL"}:
            raise ValueError("factor direction is invalid")
        if self.data_role not in {"FEATURE", "LABEL", "CONTEXT"}:
            raise ValueError("factor data_role is invalid")
        if not self.source_ids or self.freshness_hours <= 0:
            raise ValueError("factor needs sources and a positive freshness window")


class FactorRegistry:
    def __init__(self, factors: tuple[FactorDefinition, ...] = ()):
        self._factors = {factor.factor_id: factor for factor in factors}

    def add(self, factor: FactorDefinition) -> None:
        if factor.factor_id in self._factors:
            raise ValueError("duplicate factor_id")
        self._factors[factor.factor_id] = factor

    def admit(self, factor_id: str, *, known_at: datetime) -> FactorDefinition:
        factor = self._factors[factor_id]
        reasons: list[str] = []
        if factor.rights_status not in {"PUBLIC_RESEARCH_ALLOWED", "LICENSED_MODEL_USE"}:
            reasons.append("RIGHTS_NOT_ADMITTED")
        if not factor.point_in_time_tested:
            reasons.append("POINT_IN_TIME_UNTESTED")
        if known_at < factor.available_from:
            reasons.append("NOT_AVAILABLE_AT_KNOWN_AT")
        if reasons:
            raise ValueError("factor admission blocked: " + ",".join(reasons))
        admitted = FactorDefinition(**{**factor.__dict__, "status": FactorStatus.ADMITTED})
        self._factors[factor_id] = admitted
        return admitted

    def fingerprint(self) -> str:
        payload = [self._factors[key].__dict__ for key in sorted(self._factors)]
        encoded = json.dumps(payload, default=str, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
