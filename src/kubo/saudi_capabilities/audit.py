"""Fail-closed audit contracts for backtests and claims."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class AuditStatus(str, Enum):
    PASS_BACKTEST = "PASS_BACKTEST"
    STOP_BACKTEST = "STOP_BACKTEST"


@dataclass(frozen=True)
class Claim:
    claim_id: str
    claim_type: str
    evidence_count: int
    denominator_complete: bool
    point_in_time: bool
    corporate_actions_reconciled: bool
    authority_verified: bool


def audit_claims(claims: Iterable[Claim]) -> dict[str, object]:
    rows = list(claims)
    failures: list[str] = []
    for claim in rows:
        if claim.evidence_count <= 0:
            failures.append(f"{claim.claim_id}:NO_EVIDENCE")
        if not claim.denominator_complete:
            failures.append(f"{claim.claim_id}:INCOMPLETE_DENOMINATOR")
        if not claim.point_in_time:
            failures.append(f"{claim.claim_id}:POINT_IN_TIME_FAILURE")
        if not claim.corporate_actions_reconciled:
            failures.append(f"{claim.claim_id}:CORPORATE_ACTIONS_UNRECONCILED")
        if not claim.authority_verified:
            failures.append(f"{claim.claim_id}:AUTHORITY_UNVERIFIED")
    status = AuditStatus.PASS_BACKTEST if rows and not failures else AuditStatus.STOP_BACKTEST
    return {"status": status.value, "metrics": None if status is AuditStatus.STOP_BACKTEST else {"claims": len(rows)}, "failures": failures, "accuracy_claim_allowed": status is AuditStatus.PASS_BACKTEST}
