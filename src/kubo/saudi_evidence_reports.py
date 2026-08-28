"""Strict Saudi nightly evidence-report contracts.

These reports bind denominator and corporate-action attestations to the same
input corpus.  Parsing is intentionally strict: values are never coerced and
only the documented JSON fields are admitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any, ClassVar, Mapping, Self

from .foundation_io import strict_json_object


SCHEMA_VERSION = "1.0"
DENOMINATOR_REPORT_ROLE = "SAUDI_DENOMINATOR_REPORT"
CORPORATE_ACTIONS_REPORT_ROLE = "SAUDI_CORPORATE_ACTIONS_REPORT"
PASS_STATUS = "PASS"
CORPORATE_ACTION_ADJUSTMENT_BASIS = (
    "CORPORATE_ACTION_ADJUSTED_TOTAL_RETURN"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,254}$")
_ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_COMMON_FIELDS = {
    "schema_version",
    "role",
    "status",
    "run_id",
    "input_sha256",
    "coverage_from",
    "coverage_through",
    "event_count",
    "security_set_sha256",
}
_DENOMINATOR_FIELDS = _COMMON_FIELDS
_CORPORATE_ACTIONS_FIELDS = _COMMON_FIELDS | {
    "unresolved_material_actions",
    "adjustment_basis",
}


class SaudiEvidenceReportError(ValueError):
    """A malformed or cross-inconsistent Saudi evidence report."""


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise SaudiEvidenceReportError(f"{field} must be a string")
    return value


def _require_sha256(value: object, field: str) -> str:
    text = _require_string(value, field)
    if not _SHA256_RE.fullmatch(text):
        raise SaudiEvidenceReportError(f"{field} must be a lowercase SHA-256")
    return text


def _require_run_id(value: object) -> str:
    run_id = _require_string(value, "run_id")
    if not _RUN_ID_RE.fullmatch(run_id):
        raise SaudiEvidenceReportError("run_id is invalid")
    return run_id


def _require_date(value: object, field: str) -> date:
    text = _require_string(value, field)
    if not _ISO_DATE_RE.fullmatch(text):
        raise SaudiEvidenceReportError(f"{field} must be an ISO date")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise SaudiEvidenceReportError(f"{field} must be an ISO date") from exc
    if parsed.isoformat() != text:
        raise SaudiEvidenceReportError(f"{field} must be a canonical ISO date")
    return parsed


def _require_count(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SaudiEvidenceReportError(
            f"{field} must be a non-negative integer"
        )
    return value


def _require_date_value(value: object, field: str) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise SaudiEvidenceReportError(f"{field} must be a date")
    return value


def _validate_common_values(
    *,
    schema_version: object,
    role: object,
    expected_role: str,
    status: object,
    run_id: object,
    input_sha256: object,
    coverage_from: object,
    coverage_through: object,
    event_count: object,
    security_set_sha256: object,
) -> None:
    if schema_version != SCHEMA_VERSION or not isinstance(schema_version, str):
        raise SaudiEvidenceReportError("unsupported evidence report schema")
    if role != expected_role or not isinstance(role, str):
        raise SaudiEvidenceReportError("evidence report role mismatch")
    if status != PASS_STATUS or not isinstance(status, str):
        raise SaudiEvidenceReportError("evidence report status must be PASS")
    _require_run_id(run_id)
    _require_sha256(input_sha256, "input_sha256")
    start = _require_date_value(coverage_from, "coverage_from")
    through = _require_date_value(coverage_through, "coverage_through")
    if start > through:
        raise SaudiEvidenceReportError("coverage_from follows coverage_through")
    _require_count(event_count, "event_count")
    _require_sha256(security_set_sha256, "security_set_sha256")


def _strict_object(content: bytes, field: str) -> dict[str, Any]:
    if not isinstance(content, bytes):
        raise SaudiEvidenceReportError(f"{field} content must be bytes")
    try:
        return strict_json_object(content, field)
    except ValueError as exc:
        raise SaudiEvidenceReportError(str(exc)) from exc


def _parse_common(
    payload: Mapping[str, Any], *, fields: set[str], role: str
) -> dict[str, object]:
    if set(payload) != fields:
        missing = sorted(fields - set(payload))
        extra = sorted(set(payload) - fields)
        raise SaudiEvidenceReportError(
            f"evidence report fields mismatch; missing={missing}; extra={extra}"
        )
    schema_version = _require_string(payload["schema_version"], "schema_version")
    actual_role = _require_string(payload["role"], "role")
    status = _require_string(payload["status"], "status")
    if schema_version != SCHEMA_VERSION:
        raise SaudiEvidenceReportError("unsupported evidence report schema")
    if actual_role != role:
        raise SaudiEvidenceReportError("evidence report role mismatch")
    if status != PASS_STATUS:
        raise SaudiEvidenceReportError("evidence report status must be PASS")
    coverage_from = _require_date(payload["coverage_from"], "coverage_from")
    coverage_through = _require_date(
        payload["coverage_through"], "coverage_through"
    )
    if coverage_from > coverage_through:
        raise SaudiEvidenceReportError("coverage_from follows coverage_through")
    return {
        "schema_version": schema_version,
        "role": actual_role,
        "status": status,
        "run_id": _require_run_id(payload["run_id"]),
        "input_sha256": _require_sha256(payload["input_sha256"], "input_sha256"),
        "coverage_from": coverage_from,
        "coverage_through": coverage_through,
        "event_count": _require_count(payload["event_count"], "event_count"),
        "security_set_sha256": _require_sha256(
            payload["security_set_sha256"], "security_set_sha256"
        ),
    }


def _validate_expected_values(
    *,
    expected_run_id: object,
    expected_input_sha256: object,
    expected_coverage_from: object,
    expected_coverage_through: object,
    expected_event_count: object,
) -> tuple[str, str, date, date, int]:
    run_id = _require_run_id(expected_run_id)
    input_sha256 = _require_sha256(
        expected_input_sha256, "expected_input_sha256"
    )
    coverage_from = _require_date_value(
        expected_coverage_from, "expected_coverage_from"
    )
    coverage_through = _require_date_value(
        expected_coverage_through, "expected_coverage_through"
    )
    if coverage_from > coverage_through:
        raise SaudiEvidenceReportError(
            "expected_coverage_from follows expected_coverage_through"
        )
    event_count = _require_count(expected_event_count, "expected_event_count")
    return run_id, input_sha256, coverage_from, coverage_through, event_count


def _cross_validate(
    report: "SaudiDenominatorReport | SaudiCorporateActionsReport",
    *,
    expected_run_id: str,
    expected_input_sha256: str,
    expected_coverage_from: date,
    expected_coverage_through: date,
    expected_event_count: int,
) -> None:
    expected = _validate_expected_values(
        expected_run_id=expected_run_id,
        expected_input_sha256=expected_input_sha256,
        expected_coverage_from=expected_coverage_from,
        expected_coverage_through=expected_coverage_through,
        expected_event_count=expected_event_count,
    )
    actual = (
        report.run_id,
        report.input_sha256,
        report.coverage_from,
        report.coverage_through,
        report.event_count,
    )
    names = (
        "run_id",
        "input_sha256",
        "coverage_from",
        "coverage_through",
        "event_count",
    )
    mismatches = [
        name
        for name, actual_value, expected_value in zip(names, actual, expected)
        if actual_value != expected_value
    ]
    if mismatches:
        raise SaudiEvidenceReportError(
            "evidence report cross-validation failed: " + ",".join(mismatches)
        )


@dataclass(frozen=True)
class SaudiDenominatorReport:
    schema_version: str
    role: str
    status: str
    run_id: str
    input_sha256: str
    coverage_from: date
    coverage_through: date
    event_count: int
    security_set_sha256: str

    ROLE: ClassVar[str] = DENOMINATOR_REPORT_ROLE

    def __post_init__(self) -> None:
        _validate_common_values(
            schema_version=self.schema_version,
            role=self.role,
            expected_role=self.ROLE,
            status=self.status,
            run_id=self.run_id,
            input_sha256=self.input_sha256,
            coverage_from=self.coverage_from,
            coverage_through=self.coverage_through,
            event_count=self.event_count,
            security_set_sha256=self.security_set_sha256,
        )

    @classmethod
    def from_bytes(cls, content: bytes) -> Self:
        payload = _strict_object(content, "Saudi denominator report")
        return cls(**_parse_common(payload, fields=_DENOMINATOR_FIELDS, role=cls.ROLE))

    def cross_validate(
        self,
        *,
        expected_run_id: str,
        expected_input_sha256: str,
        expected_coverage_from: date,
        expected_coverage_through: date,
        expected_event_count: int,
    ) -> None:
        _cross_validate(
            self,
            expected_run_id=expected_run_id,
            expected_input_sha256=expected_input_sha256,
            expected_coverage_from=expected_coverage_from,
            expected_coverage_through=expected_coverage_through,
            expected_event_count=expected_event_count,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "role": self.role,
            "status": self.status,
            "run_id": self.run_id,
            "input_sha256": self.input_sha256,
            "coverage_from": self.coverage_from.isoformat(),
            "coverage_through": self.coverage_through.isoformat(),
            "event_count": self.event_count,
            "security_set_sha256": self.security_set_sha256,
        }


@dataclass(frozen=True)
class SaudiCorporateActionsReport:
    schema_version: str
    role: str
    status: str
    run_id: str
    input_sha256: str
    coverage_from: date
    coverage_through: date
    event_count: int
    security_set_sha256: str
    unresolved_material_actions: int
    adjustment_basis: str

    ROLE: ClassVar[str] = CORPORATE_ACTIONS_REPORT_ROLE

    def __post_init__(self) -> None:
        _validate_common_values(
            schema_version=self.schema_version,
            role=self.role,
            expected_role=self.ROLE,
            status=self.status,
            run_id=self.run_id,
            input_sha256=self.input_sha256,
            coverage_from=self.coverage_from,
            coverage_through=self.coverage_through,
            event_count=self.event_count,
            security_set_sha256=self.security_set_sha256,
        )
        unresolved = _require_count(
            self.unresolved_material_actions, "unresolved_material_actions"
        )
        if unresolved != 0:
            raise SaudiEvidenceReportError(
                "unresolved_material_actions must be zero"
            )
        if (
            not isinstance(self.adjustment_basis, str)
            or self.adjustment_basis != CORPORATE_ACTION_ADJUSTMENT_BASIS
        ):
            raise SaudiEvidenceReportError("adjustment_basis is invalid")

    @classmethod
    def from_bytes(cls, content: bytes) -> Self:
        payload = _strict_object(content, "Saudi corporate-actions report")
        values = _parse_common(
            payload,
            fields=_CORPORATE_ACTIONS_FIELDS,
            role=cls.ROLE,
        )
        unresolved = _require_count(
            payload["unresolved_material_actions"],
            "unresolved_material_actions",
        )
        if unresolved != 0:
            raise SaudiEvidenceReportError(
                "unresolved_material_actions must be zero"
            )
        adjustment_basis = _require_string(
            payload["adjustment_basis"], "adjustment_basis"
        )
        if adjustment_basis != CORPORATE_ACTION_ADJUSTMENT_BASIS:
            raise SaudiEvidenceReportError("adjustment_basis is invalid")
        return cls(
            **values,
            unresolved_material_actions=unresolved,
            adjustment_basis=adjustment_basis,
        )

    def cross_validate(
        self,
        *,
        expected_run_id: str,
        expected_input_sha256: str,
        expected_coverage_from: date,
        expected_coverage_through: date,
        expected_event_count: int,
    ) -> None:
        _cross_validate(
            self,
            expected_run_id=expected_run_id,
            expected_input_sha256=expected_input_sha256,
            expected_coverage_from=expected_coverage_from,
            expected_coverage_through=expected_coverage_through,
            expected_event_count=expected_event_count,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "role": self.role,
            "status": self.status,
            "run_id": self.run_id,
            "input_sha256": self.input_sha256,
            "coverage_from": self.coverage_from.isoformat(),
            "coverage_through": self.coverage_through.isoformat(),
            "event_count": self.event_count,
            "security_set_sha256": self.security_set_sha256,
            "unresolved_material_actions": self.unresolved_material_actions,
            "adjustment_basis": self.adjustment_basis,
        }


def denominator_report_from_bytes(content: bytes) -> SaudiDenominatorReport:
    return SaudiDenominatorReport.from_bytes(content)


def corporate_actions_report_from_bytes(
    content: bytes,
) -> SaudiCorporateActionsReport:
    return SaudiCorporateActionsReport.from_bytes(content)


def cross_validate_evidence_reports(
    denominator: SaudiDenominatorReport,
    corporate_actions: SaudiCorporateActionsReport,
    *,
    expected_run_id: str,
    expected_input_sha256: str,
    expected_coverage_from: date,
    expected_coverage_through: date,
    expected_event_count: int,
) -> None:
    """Require both reports to bind the same expected corpus and security set."""

    if not isinstance(denominator, SaudiDenominatorReport):
        raise SaudiEvidenceReportError("denominator report type is invalid")
    if not isinstance(corporate_actions, SaudiCorporateActionsReport):
        raise SaudiEvidenceReportError("corporate-actions report type is invalid")
    arguments = {
        "expected_run_id": expected_run_id,
        "expected_input_sha256": expected_input_sha256,
        "expected_coverage_from": expected_coverage_from,
        "expected_coverage_through": expected_coverage_through,
        "expected_event_count": expected_event_count,
    }
    denominator.cross_validate(**arguments)
    corporate_actions.cross_validate(**arguments)
    if denominator.security_set_sha256 != corporate_actions.security_set_sha256:
        raise SaudiEvidenceReportError(
            "evidence report cross-validation failed: security_set_sha256"
        )


__all__ = [
    "CORPORATE_ACTION_ADJUSTMENT_BASIS",
    "CORPORATE_ACTIONS_REPORT_ROLE",
    "DENOMINATOR_REPORT_ROLE",
    "PASS_STATUS",
    "SCHEMA_VERSION",
    "SaudiCorporateActionsReport",
    "SaudiDenominatorReport",
    "SaudiEvidenceReportError",
    "corporate_actions_report_from_bytes",
    "cross_validate_evidence_reports",
    "denominator_report_from_bytes",
]
