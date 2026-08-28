from __future__ import annotations

import copy
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

from kubo.markets.saudi.calendar import (
    SaudiTradingCalendar,
    calendar_revision_from_mapping,
)
from kubo.markets.saudi.identity import (
    SaudiSecurityMaster,
    saudi_security_record_from_mapping,
)
from kubo.saudi_admission import AdmissionPurpose, verify_saudi_admission_receipt
from kubo.saudi_capabilities.nightly_lab import ALL_HORIZONS, FactorObservation
from kubo.saudi_capabilities.post_open import (
    PostOpenObservation,
    SaudiPostOpenScanner,
)
from kubo.saudi_post_open_cli import main as post_open_main
from tests.saudi.helpers import (
    identity_payload,
    synthetic_calendar_payload,
    write_admission_receipt,
)


ROOT = Path(__file__).resolve().parents[2]


class SaudiPostOpenReportSchemaTests(unittest.TestCase):
    timezone = ZoneInfo("Asia/Riyadh")
    scan_at = datetime(2026, 8, 25, 10, 30, 30, tzinfo=timezone)

    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "saudi-post-open-report.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(
            schema,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.calendar = SaudiTradingCalendar(
            revision=calendar_revision_from_mapping(
                synthetic_calendar_payload(),
                known_at=self.scan_at,
            )
        )
        self.codes = tuple(f"{1000 + index:04d}" for index in range(26))
        self.master = SaudiSecurityMaster(
            tuple(
                saudi_security_record_from_mapping(identity_payload(code))
                for code in self.codes
            )
        )
        self.artifact_paths = {
            role: self.root / f"core-{role}.json"
            for role in ("input", "identity", "calendar", "weights")
        }
        for role, path in self.artifact_paths.items():
            path.write_text(
                json.dumps({"role": role, "synthetic": True}, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        self.execution_contract = {
            "scan_at": self.scan_at.isoformat(),
            "maximum_market_age_minutes": 15,
            "minimum_turnover_sar": 0.0,
            "maximum_candidates_per_horizon": 25,
        }
        receipt = self.root / "core-admission.json"
        write_admission_receipt(
            receipt,
            purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
            artifact_paths=self.artifact_paths,
            decision_at=self.scan_at,
            execution_contract=self.execution_contract,
        )
        self.admission = verify_saudi_admission_receipt(
            receipt,
            purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
            artifact_paths=self.artifact_paths,
            decision_at=self.scan_at,
            expected_execution_contract=self.execution_contract,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assertValidReport(self, report: object) -> None:
        errors = sorted(
            self.validator.iter_errors(report),
            key=lambda item: (list(item.absolute_path), item.message),
        )
        self.assertEqual(errors, [], [error.message for error in errors])

    def assertInvalidReport(self, report: object) -> None:
        self.assertTrue(list(self.validator.iter_errors(report)))

    def weights(self):
        return {
            horizon: {"F9-governed-signal": 1.0}
            for horizon in ALL_HORIZONS
        }

    def observation(
        self,
        code: str = "1000",
        *,
        known_at: datetime | None = None,
    ) -> PostOpenObservation:
        timestamp = known_at or self.scan_at - timedelta(minutes=5)
        return PostOpenObservation(
            official_code=code,
            observed_at=timestamp,
            source_id="licensed-saudi-market-feed",
            source_role="LICENSED_MARKET_DATA",
            rights_status="LICENSED_MODEL_USE",
            latency_class="DELAYED",
            last_price_sar=123.4,
            average_daily_turnover_sar=5_000_000.0,
            factors=(
                FactorObservation(
                    factor_id="F9-governed-signal",
                    value=0.75,
                    known_at=timestamp,
                    source_id="licensed-saudi-market-feed",
                    rights_status="LICENSED_MODEL_USE",
                ),
            ),
        )

    def scanner(self) -> SaudiPostOpenScanner:
        return SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=self.master,
        )

    def test_core_runtime_branches_validate_and_candidate_requires_envelope(self):
        candidate_report = self.scanner().scan(
            tuple(self.observation(code) for code in self.codes),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(
            candidate_report["status"],
            "UNAUTHENTICATED_RESEARCH_CANDIDATES",
        )
        self.assertValidReport(candidate_report)

        abstain_report = self.scanner().scan(
            (self.observation(),),
            admission=self.admission,
            scan_at=self.scan_at - timedelta(seconds=1),
            horizon_weights=self.weights(),
        )
        self.assertEqual(abstain_report["status"], "ABSTAIN")
        self.assertValidReport(abstain_report)

        incomplete_report = self.scanner().scan(
            tuple(self.observation(code) for code in self.codes[:-1]),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(
            incomplete_report["reason"],
            "INCOMPLETE_OBSERVATION_DENOMINATOR",
        )
        self.assertFalse(incomplete_report["denominator_complete"])
        self.assertEqual(incomplete_report["missing_official_codes"], ["1025"])
        self.assertValidReport(incomplete_report)

        empty_report = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=SaudiSecurityMaster(),
        ).scan(
            (),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(
            empty_report["reason"], "EMPTY_OR_UNVERIFIED_UNIVERSE"
        )
        self.assertFalse(empty_report["denominator_complete"])
        self.assertValidReport(empty_report)

        forged_complete_denominator = copy.deepcopy(incomplete_report)
        forged_complete_denominator["denominator_complete"] = True
        self.assertInvalidReport(forged_complete_denominator)

        detached_row = candidate_report["candidates_by_horizon"]["INTRADAY"][0]
        self.assertInvalidReport(detached_row)

        forged_authentication = copy.deepcopy(candidate_report)
        forged_authentication["input_admission_authenticated"] = True
        self.assertInvalidReport(forged_authentication)

        forged_horizon = copy.deepcopy(candidate_report)
        forged_horizon["candidates_by_horizon"]["INTRADAY"][0][
            "horizon"
        ] = "YEAR"
        self.assertInvalidReport(forged_horizon)

    def test_exact_fifteen_minute_threshold_is_inclusive(self):
        single_master = SaudiSecurityMaster(
            (saudi_security_record_from_mapping(identity_payload("1000")),)
        )
        scanner = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=single_master,
        )
        exact_timestamp = self.scan_at - timedelta(minutes=15)
        exact_report = scanner.scan(
            (self.observation(known_at=exact_timestamp),),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(
            exact_report["status"],
            "UNAUTHENTICATED_RESEARCH_CANDIDATES",
        )
        self.assertValidReport(exact_report)

        stale_timestamp = exact_timestamp - timedelta(microseconds=1)
        stale_report = scanner.scan(
            (self.observation(known_at=stale_timestamp),),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(stale_report["status"], "ABSTAIN")
        self.assertEqual(
            stale_report["rejected"][0]["reason"],
            "STALE_MARKET_OBSERVATION",
        )
        self.assertValidReport(stale_report)

    def test_twenty_six_admitted_rows_are_capped_at_twenty_five(self):
        report = self.scanner().scan(
            tuple(self.observation(code) for code in self.codes),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
            maximum_candidates_per_horizon=25,
        )
        self.assertEqual(report["admitted_security_count"], 26)
        self.assertTrue(report["denominator_complete"])
        self.assertEqual(report["expected_security_count"], 26)
        self.assertEqual(report["observed_security_count"], 26)
        self.assertEqual(report["input_record_count"], 26)
        self.assertEqual(
            {len(rows) for rows in report["candidates_by_horizon"].values()},
            {25},
        )
        self.assertValidReport(report)

        overfilled = copy.deepcopy(report)
        overfilled["candidates_by_horizon"]["INTRADAY"].append(
            copy.deepcopy(overfilled["candidates_by_horizon"]["INTRADAY"][0])
        )
        self.assertInvalidReport(overfilled)

    def test_liquidity_filter_preserves_complete_observation_denominator(self):
        one_low_turnover = tuple(
            replace(self.observation(code), average_daily_turnover_sar=1.0)
            if code == self.codes[-1]
            else self.observation(code)
            for code in self.codes
        )
        partially_admitted = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=self.master,
            minimum_turnover_sar=100.0,
        ).scan(
            one_low_turnover,
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertTrue(partially_admitted["denominator_complete"])
        self.assertEqual(partially_admitted["expected_security_count"], 26)
        self.assertEqual(partially_admitted["observed_security_count"], 26)
        self.assertEqual(partially_admitted["input_record_count"], 26)
        self.assertEqual(partially_admitted["admitted_security_count"], 25)
        self.assertEqual(
            partially_admitted["rejected"],
            [
                {
                    "official_code": self.codes[-1],
                    "reason": "LIQUIDITY_FLOOR_NOT_MET",
                }
            ],
        )
        self.assertValidReport(partially_admitted)

        none_admitted = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=self.master,
            minimum_turnover_sar=10_000_000.0,
        ).scan(
            tuple(self.observation(code) for code in self.codes),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(
            none_admitted["reason"],
            "NO_SECURITIES_MEET_LIQUIDITY_FLOOR",
        )
        self.assertTrue(none_admitted["denominator_complete"])
        self.assertEqual(none_admitted["admitted_security_count"], 0)
        self.assertValidReport(none_admitted)

    def test_cli_synthetic_and_abstain_reports_validate_with_trust_relations(self):
        observations = self.root / "observations.jsonl"
        observations.write_text(
            json.dumps(self.observation().to_dict(), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        identity = self.root / "identity.json"
        identity.write_text(
            json.dumps([identity_payload("1000")], sort_keys=True) + "\n",
            encoding="utf-8",
        )
        calendar = self.root / "calendar.json"
        calendar.write_text(
            json.dumps(synthetic_calendar_payload(), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        weights = self.root / "weights.json"
        weights.write_text(
            json.dumps(
                {
                    horizon.value: {"F9-governed-signal": 1.0}
                    for horizon in ALL_HORIZONS
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        artifact_paths = {
            "input": observations,
            "identity": identity,
            "calendar": calendar,
            "weights": weights,
        }

        receipt = self.root / "cli-admission.json"
        write_admission_receipt(
            receipt,
            purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
            artifact_paths=artifact_paths,
            decision_at=self.scan_at,
        )
        output = self.root / "cli-output"
        with redirect_stdout(StringIO()):
            code = post_open_main(
                [
                    "--observations",
                    str(observations),
                    "--weights",
                    str(weights),
                    "--identity-file",
                    str(identity),
                    "--calendar-file",
                    str(calendar),
                    "--admission-receipt",
                    str(receipt),
                    "--scan-at",
                    self.scan_at.isoformat(),
                    "--output-root",
                    str(output),
                ]
            )
        self.assertEqual(code, 0)
        synthetic_report = json.loads(
            (output / "post_open_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            synthetic_report["status"], "SYNTHETIC_RESEARCH_CANDIDATES"
        )
        self.assertValidReport(synthetic_report)

        forged_ready = copy.deepcopy(synthetic_report)
        forged_ready["status"] = "RESEARCH_CANDIDATES_READY"
        self.assertInvalidReport(forged_ready)

        modeled_ready = copy.deepcopy(synthetic_report)
        modeled_ready["status"] = "RESEARCH_CANDIDATES_READY"
        modeled_ready["evidence_class"] = "RECORDED_AUTHORIZED_FIXTURE"
        modeled_ready["admission_trust_class"] = "PRODUCTION_SIGNED"
        modeled_ready["admission"]["trust_class"] = "PRODUCTION_SIGNED"
        modeled_ready["admission"][
            "market_evidence_trust_class"
        ] = "PRODUCTION_SIGNED"
        modeled_ready["admission"][
            "authenticated_key_id"
        ] = "production-ed25519-v1"
        modeled_ready["claim_boundary"] = (
            "Admission-bound research candidates only; no personalized "
            "recommendation, probability, order, or execution"
        )
        self.assertValidReport(modeled_ready)

        early_scan = self.scan_at - timedelta(seconds=1)
        early_receipt = self.root / "early-cli-admission.json"
        write_admission_receipt(
            early_receipt,
            purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
            artifact_paths=artifact_paths,
            decision_at=early_scan,
        )
        early_output = self.root / "early-cli-output"
        with redirect_stdout(StringIO()):
            early_code = post_open_main(
                [
                    "--observations",
                    str(observations),
                    "--weights",
                    str(weights),
                    "--identity-file",
                    str(identity),
                    "--calendar-file",
                    str(calendar),
                    "--admission-receipt",
                    str(early_receipt),
                    "--scan-at",
                    early_scan.isoformat(),
                    "--output-root",
                    str(early_output),
                ]
            )
        self.assertEqual(early_code, 2)
        admission_bound_abstain = json.loads(
            (early_output / "post_open_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(admission_bound_abstain["status"], "ABSTAIN")
        self.assertTrue(
            admission_bound_abstain["input_admission_authenticated"]
        )
        self.assertValidReport(admission_bound_abstain)

        incomplete_identity = self.root / "incomplete-identity.json"
        incomplete_identity.write_text(
            json.dumps(
                [identity_payload("1000"), identity_payload("1001")],
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        incomplete_artifacts = {
            **artifact_paths,
            "identity": incomplete_identity,
        }
        incomplete_receipt = self.root / "incomplete-cli-admission.json"
        write_admission_receipt(
            incomplete_receipt,
            purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
            artifact_paths=incomplete_artifacts,
            decision_at=self.scan_at,
        )
        incomplete_output = self.root / "incomplete-cli-output"
        with redirect_stdout(StringIO()):
            incomplete_code = post_open_main(
                [
                    "--observations",
                    str(observations),
                    "--weights",
                    str(weights),
                    "--identity-file",
                    str(incomplete_identity),
                    "--calendar-file",
                    str(calendar),
                    "--admission-receipt",
                    str(incomplete_receipt),
                    "--scan-at",
                    self.scan_at.isoformat(),
                    "--output-root",
                    str(incomplete_output),
                ]
            )
        self.assertEqual(incomplete_code, 2)
        admission_bound_incomplete = json.loads(
            (incomplete_output / "post_open_report.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            admission_bound_incomplete["reason"],
            "INCOMPLETE_OBSERVATION_DENOMINATOR",
        )
        self.assertFalse(admission_bound_incomplete["denominator_complete"])
        self.assertEqual(
            admission_bound_incomplete["missing_official_codes"],
            ["1001"],
        )
        self.assertValidReport(admission_bound_incomplete)

        empty_observations = self.root / "empty-observations.jsonl"
        empty_observations.write_text("", encoding="utf-8")
        empty_identity = self.root / "empty-identity.json"
        empty_identity.write_text("[]\n", encoding="utf-8")
        empty_artifacts = {
            "input": empty_observations,
            "identity": empty_identity,
            "calendar": calendar,
            "weights": weights,
        }
        empty_receipt = self.root / "empty-cli-admission.json"
        write_admission_receipt(
            empty_receipt,
            purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
            artifact_paths=empty_artifacts,
            decision_at=self.scan_at,
        )
        empty_output = self.root / "empty-cli-output"
        with redirect_stdout(StringIO()):
            empty_code = post_open_main(
                [
                    "--observations",
                    str(empty_observations),
                    "--weights",
                    str(weights),
                    "--identity-file",
                    str(empty_identity),
                    "--calendar-file",
                    str(calendar),
                    "--admission-receipt",
                    str(empty_receipt),
                    "--scan-at",
                    self.scan_at.isoformat(),
                    "--output-root",
                    str(empty_output),
                ]
            )
        self.assertEqual(empty_code, 2)
        admission_bound_empty = json.loads(
            (empty_output / "post_open_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            admission_bound_empty["reason"], "EMPTY_OR_UNVERIFIED_UNIVERSE"
        )
        self.assertFalse(admission_bound_empty["denominator_complete"])
        self.assertValidReport(admission_bound_empty)


if __name__ == "__main__":
    unittest.main()
