from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from kubo.markets.saudi.engine import SaudiResearchEngine
from kubo.markets.saudi.identity import SaudiSecurityMaster


ROOT = Path(__file__).resolve().parents[2]


class SaudiSnapshotSchemaRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(
            (ROOT / "schemas/saudi-market-snapshot.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(
            schema,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        cls.engine = SaudiResearchEngine(security_master=SaudiSecurityMaster())
        cls.as_of = date(2026, 8, 25)
        cls.known_at = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)

    def assert_valid_snapshot(self, payload: object) -> None:
        errors = sorted(
            self.validator.iter_errors(payload),
            key=lambda item: (list(item.absolute_path), item.message),
        )
        self.assertEqual(errors, [], [error.message for error in errors])

    def test_main_runtime_snapshot_matches_schema(self) -> None:
        snapshot = self.engine.snapshot(
            as_of=self.as_of,
            known_at=self.known_at,
        )

        self.assertEqual(snapshot["segment"], "MAIN")
        self.assertIn("membership_denominator_size", snapshot)
        self.assertIn("coverage_known", snapshot["session"])
        self.assertIn("calendar_revision_id", snapshot["session"])
        self.assert_valid_snapshot(snapshot)

    def test_unsupported_scope_runtime_snapshot_matches_schema(self) -> None:
        snapshot = self.engine.snapshot(
            as_of=self.as_of,
            known_at=self.known_at,
            segment="NOMU",
        )

        self.assertEqual(snapshot["status"], "ABSTAIN")
        self.assertEqual(snapshot["blocked_reasons"], ["UNSUPPORTED_PRODUCT_SCOPE"])
        self.assert_valid_snapshot(snapshot)

    def test_schema_remains_closed_against_unpublished_runtime_fields(self) -> None:
        snapshot = self.engine.snapshot(
            as_of=self.as_of,
            known_at=self.known_at,
        )
        snapshot["uncontracted"] = True

        self.assertTrue(list(self.validator.iter_errors(snapshot)))


if __name__ == "__main__":
    unittest.main()
