"""Dated Saudi rules that must be re-verified before live use."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .config import MAIN_MARKET, NOMU, RIYADH_TZ, SAR


@dataclass(frozen=True)
class SaudiRuleSet:
    effective_from: date
    source_url: str
    currency: str = SAR
    timezone: str = RIYADH_TZ
    enabled_segments: tuple[str, ...] = (MAIN_MARKET,)
    nomu_enabled: bool = False
    status: str = "DEFINED_ONLY"

    def validate_segment(self, segment: str) -> None:
        if segment == NOMU and not self.nomu_enabled:
            raise ValueError("Nomu is disabled by default; it needs a separate approved policy")
        if segment not in self.enabled_segments and segment != NOMU:
            raise ValueError(f"unsupported Saudi segment: {segment}")
