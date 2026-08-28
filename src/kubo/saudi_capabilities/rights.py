"""Canonical Saudi research and model-use rights grants.

Review states and contract requirements are not runtime grants.  Values are
matched exactly: this module never trims, case-folds, or promotes a weaker
grant to model use.
"""
from __future__ import annotations

from enum import Enum


class RightsUse(str, Enum):
    RESEARCH = "RESEARCH"
    MODEL_USE = "MODEL_USE"


PUBLIC_RESEARCH_ALLOWED = "PUBLIC_RESEARCH_ALLOWED"
LICENSED_RESEARCH_ALLOWED = "LICENSED_RESEARCH_ALLOWED"
LICENSED_MODEL_USE = "LICENSED_MODEL_USE"

KNOWN_RIGHTS = frozenset(
    {
        PUBLIC_RESEARCH_ALLOWED,
        LICENSED_RESEARCH_ALLOWED,
        LICENSED_MODEL_USE,
    }
)
RESEARCH_RIGHTS = frozenset(
    {
        PUBLIC_RESEARCH_ALLOWED,
        LICENSED_RESEARCH_ALLOWED,
        LICENSED_MODEL_USE,
    }
)
MODEL_USE_RIGHTS = frozenset(
    {
        PUBLIC_RESEARCH_ALLOWED,
        LICENSED_MODEL_USE,
    }
)


def require_known_rights(value: str) -> str:
    if not isinstance(value, str) or value not in KNOWN_RIGHTS:
        raise ValueError("UNKNOWN_RIGHTS_STATUS")
    return value


def require_rights(value: str, *, use: RightsUse) -> str:
    grant = require_known_rights(value)
    allowed = RESEARCH_RIGHTS if use is RightsUse.RESEARCH else MODEL_USE_RIGHTS
    if grant not in allowed:
        raise ValueError(f"{use.value}_RIGHTS_NOT_ADMITTED")
    return grant


__all__ = [
    "KNOWN_RIGHTS",
    "LICENSED_MODEL_USE",
    "LICENSED_RESEARCH_ALLOWED",
    "MODEL_USE_RIGHTS",
    "PUBLIC_RESEARCH_ALLOWED",
    "RESEARCH_RIGHTS",
    "RightsUse",
    "require_known_rights",
    "require_rights",
]
