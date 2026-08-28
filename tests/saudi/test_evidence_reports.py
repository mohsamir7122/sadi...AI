from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from kubo.saudi_evidence_reports import (
    CORPORATE_ACTION_ADJUSTMENT_BASIS,
    CORPORATE_ACTIONS_REPORT_ROLE,
    DENOMINATOR_REPORT_ROLE,
    SaudiCorporateActionsReport,
    SaudiDenominatorReport,
    SaudiEvidenceReportError,
    corporate_actions_report_from_bytes,
    cross_validate_evidence_reports,
    denominator_report_from_bytes,
)


ROOT = Path(__file__).resolve().parents[2]
INPUT_SHA256 = "1" * 64
SECURITY_SET_SHA256 = "2" * 64


def denominator_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "role": DENOMINATOR_REPORT_ROLE,
        "status": "PASS",
        "run_id": "saudi-nightly-2026-08-25",
        "input_sha256": INPUT_SHA256,
        "coverage_from": "2016-08-25",
        "coverage_through": "2026-08-25",
        "event_count": 560,
        "security_set_sha256": SECURITY_SET_SHA256,
    }
    payload.update(overrides)
    return payload


def corporate_actions_payload(**overrides: object) -> dict[str, object]:
    payload = denominator_payload(
        role=CORPORATE_ACTIONS_REPORT_ROLE,
        unresolved_material_actions=0,
        adjustment_basis=CORPORATE_ACTION_ADJUSTMENT_BASIS,
    )
    payload.update(overrides)
    return payload


def encoded(payload: dict[str, object]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")


class SaudiEvidenceReportTests(unittest.TestCase):
    expected = {
        "expected_run_id": "saudi-nightly-2026-08-25",
        "expected_input_sha256": INPUT_SHA256,
        "expected_coverage_from": date(2016, 8, 25),
        "expected_coverage_through": date(2026, 8, 25),
        "expected_event_count": 560,
    }

    def test_from_bytes_returns_immutable_strict_reports(self):
        denominator = denominator_report_from_bytes(encoded(denominator_payload()))
        corporate_actions = corporate_actions_report_from_bytes(
            encoded(corporate_actions_payload())
        )

        self.assertIsInstance(denominator, SaudiDenominatorReport)
        self.assertIsInstance(corporate_actions, SaudiCorporateActionsReport)
        self.assertEqual(denominator.coverage_from, date(2016, 8, 25))
        self.assertEqual(corporate_actions.unresolved_material_actions, 0)
        self.assertEqual(denominator.to_dict(), denominator_payload())
        self.assertEqual(corporate_actions.to_dict(), corporate_actions_payload())
        denominator.cross_validate(**self.expected)
        corporate_actions.cross_validate(**self.expected)
        cross_validate_evidence_reports(
            denominator,
            corporate_actions,
            **self.expected,
        )

        with self.assertRaises(FrozenInstanceError):
            denominator.event_count = 1  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            corporate_actions.status = "FAIL"  # type: ignore[misc]

    def test_duplicate_keys_nonfinite_json_and_nonbytes_fail_closed(self):
        malformed_rows = (
            b'{"schema_version":"1.0","schema_version":"1.0"}',
            b'{"event_count":NaN}',
        )
        for parser in (
            denominator_report_from_bytes,
            corporate_actions_report_from_bytes,
        ):
            for content in malformed_rows:
                with self.subTest(parser=parser.__name__, content=content):
                    with self.assertRaises(SaudiEvidenceReportError):
                        parser(content)
            with self.subTest(parser=parser.__name__, content="not-bytes"):
                with self.assertRaisesRegex(
                    SaudiEvidenceReportError, "content must be bytes"
                ):
                    parser("not-bytes")  # type: ignore[arg-type]

    def test_denominator_rejects_coercion_wrong_constants_and_field_drift(self):
        invalid = {
            "numeric_schema": {"schema_version": 1.0},
            "wrong_role": {"role": CORPORATE_ACTIONS_REPORT_ROLE},
            "wrong_status": {"status": "FAIL"},
            "numeric_run_id": {"run_id": 25},
            "numeric_code": {"input_sha256": 1},
            "upper_hash": {"input_sha256": "A" * 64},
            "numeric_date": {"coverage_from": 20160825},
            "basic_date": {"coverage_from": "20160825"},
            "boolean_count": {"event_count": True},
            "string_count": {"event_count": "560"},
            "numeric_security_hash": {"security_set_sha256": 2},
            "reverse_coverage": {
                "coverage_from": "2026-08-26",
                "coverage_through": "2026-08-25",
            },
            "extra_field": {"unexpected": True},
        }
        for name, overrides in invalid.items():
            with self.subTest(name=name):
                with self.assertRaises(SaudiEvidenceReportError):
                    denominator_report_from_bytes(
                        encoded(denominator_payload(**overrides))
                    )

        missing = denominator_payload()
        missing.pop("status")
        with self.assertRaisesRegex(SaudiEvidenceReportError, "fields mismatch"):
            denominator_report_from_bytes(encoded(missing))

    def test_corporate_actions_requires_zero_and_fixed_adjustment_basis(self):
        for value in (True, 1, "0", -1):
            with self.subTest(unresolved_material_actions=value):
                with self.assertRaises(SaudiEvidenceReportError):
                    corporate_actions_report_from_bytes(
                        encoded(
                            corporate_actions_payload(
                                unresolved_material_actions=value
                            )
                        )
                    )
        for value in (None, 7, "RAW_CLOSE"):
            with self.subTest(adjustment_basis=value):
                with self.assertRaises(SaudiEvidenceReportError):
                    corporate_actions_report_from_bytes(
                        encoded(corporate_actions_payload(adjustment_basis=value))
                    )

    def test_direct_dataclass_construction_enforces_the_same_contract(self):
        values = {
            "schema_version": "1.0",
            "role": DENOMINATOR_REPORT_ROLE,
            "status": "PASS",
            "run_id": "run-1",
            "input_sha256": INPUT_SHA256,
            "coverage_from": date(2026, 1, 1),
            "coverage_through": date(2026, 1, 2),
            "event_count": True,
            "security_set_sha256": SECURITY_SET_SHA256,
        }
        with self.assertRaisesRegex(SaudiEvidenceReportError, "event_count"):
            SaudiDenominatorReport(**values)  # type: ignore[arg-type]

    def test_cross_validation_names_every_expected_mismatch(self):
        report = denominator_report_from_bytes(encoded(denominator_payload()))
        mismatches = {
            "run_id": {"expected_run_id": "different-run"},
            "input_sha256": {"expected_input_sha256": "3" * 64},
            "coverage_from": {
                "expected_coverage_from": date(2016, 8, 24)
            },
            "coverage_through": {
                "expected_coverage_through": date(2026, 8, 24)
            },
            "event_count": {"expected_event_count": 559},
        }
        for name, override in mismatches.items():
            arguments = {**self.expected, **override}
            with self.subTest(name=name):
                with self.assertRaisesRegex(SaudiEvidenceReportError, name):
                    report.cross_validate(**arguments)

        with self.assertRaisesRegex(SaudiEvidenceReportError, "must be a date"):
            report.cross_validate(
                **{
                    **self.expected,
                    "expected_coverage_from": "2016-08-25",
                }
            )

    def test_pair_cross_validation_requires_the_same_security_set(self):
        denominator = denominator_report_from_bytes(encoded(denominator_payload()))
        corporate_actions = corporate_actions_report_from_bytes(
            encoded(corporate_actions_payload(security_set_sha256="4" * 64))
        )
        with self.assertRaisesRegex(
            SaudiEvidenceReportError, "security_set_sha256"
        ):
            cross_validate_evidence_reports(
                denominator,
                corporate_actions,
                **self.expected,
            )

    def test_json_schemas_validate_outputs_and_reject_coercions(self):
        rows = (
            (
                "saudi-denominator-report.schema.json",
                denominator_payload(),
            ),
            (
                "saudi-corporate-actions-report.schema.json",
                corporate_actions_payload(),
            ),
        )
        for name, payload in rows:
            schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(
                schema,
                format_checker=FormatChecker(),
            )
            validator.validate(payload)
            invalid = dict(payload)
            invalid["event_count"] = True
            with self.assertRaises(ValidationError):
                validator.validate(invalid)


if __name__ == "__main__":
    unittest.main()
