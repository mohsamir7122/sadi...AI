from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from kubo.saudi_capabilities.factor9 import FactorDefinition, FactorRegistry
from kubo.saudi_capabilities.nightly_lab import FactorObservation
from kubo.saudi_capabilities.rights import (
    LICENSED_MODEL_USE,
    LICENSED_RESEARCH_ALLOWED,
    MODEL_USE_RIGHTS,
    PUBLIC_RESEARCH_ALLOWED,
    RightsUse,
    require_rights,
)


ROOT = Path(__file__).resolve().parents[2]


class SaudiRightsContractTests(unittest.TestCase):
    known_at = datetime(2026, 8, 25, tzinfo=timezone.utc)

    def definition(self, rights_status: str) -> FactorDefinition:
        return FactorDefinition(
            factor_id="F9-rights-test",
            name="Rights test",
            direction="NEUTRAL",
            data_role="FEATURE",
            source_ids=("source",),
            available_from=self.known_at,
            freshness_hours=24,
            rights_status=rights_status,
            point_in_time_tested=True,
        )

    def test_model_use_grants_are_consistent_across_registry_and_observation(self):
        for grant in sorted(MODEL_USE_RIGHTS):
            with self.subTest(grant=grant):
                registry = FactorRegistry((self.definition(grant),))
                registry.admit("F9-rights-test", known_at=self.known_at)
                observation = FactorObservation(
                    factor_id="F9-rights-test",
                    value=1.0,
                    known_at=self.known_at,
                    source_id="source",
                    rights_status=grant,
                )
                self.assertEqual(observation.rights_status, grant)

    def test_research_only_grant_is_not_silently_promoted_to_model_use(self):
        registry = FactorRegistry((self.definition(LICENSED_RESEARCH_ALLOWED),))
        with self.assertRaisesRegex(ValueError, "MODEL_USE_RIGHTS_NOT_ADMITTED"):
            registry.admit("F9-rights-test", known_at=self.known_at)
        with self.assertRaisesRegex(ValueError, "MODEL_USE_RIGHTS_NOT_ADMITTED"):
            FactorObservation(
                factor_id="F9-rights-test",
                value=1.0,
                known_at=self.known_at,
                source_id="source",
                rights_status=LICENSED_RESEARCH_ALLOWED,
            )

    def test_unknown_review_and_noncanonical_values_fail_closed(self):
        for value in ("REVIEW_REQUIRED", "licensed_model_use", " LICENSED_MODEL_USE"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "UNKNOWN_RIGHTS_STATUS"
            ):
                require_rights(value, use=RightsUse.MODEL_USE)

    def test_runtime_schemas_match_canonical_model_use_grants(self):
        expected = sorted(MODEL_USE_RIGHTS)
        for relative in (
            "schemas/saudi-nightly-event.schema.json",
            "schemas/saudi-post-open-observation.schema.json",
        ):
            with self.subTest(schema=relative):
                schema = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                self.assertEqual(sorted(schema["properties"]["rights_status"]["enum"]), expected)
                factor_enum = schema["properties"]["factors"]["items"]["properties"]["rights_status"]["enum"]
                self.assertEqual(sorted(factor_enum), expected)

    def test_public_and_licensed_model_use_are_the_only_model_grants(self):
        self.assertEqual(
            MODEL_USE_RIGHTS,
            frozenset({PUBLIC_RESEARCH_ALLOWED, LICENSED_MODEL_USE}),
        )


if __name__ == "__main__":
    unittest.main()
