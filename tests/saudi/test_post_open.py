from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from kubo.saudi_capabilities.nightly_lab import ALL_HORIZONS, FactorObservation
from kubo.saudi_capabilities.post_open import (
    PostOpenObservation,
    SaudiPostOpenScanner,
    post_open_observation_from_mapping,
)
from kubo.markets.saudi.calendar import (
    CALENDAR_REVISION_NOT_KNOWN,
    SaudiTradingCalendar,
    calendar_revision_from_mapping,
)
from kubo.markets.saudi.identity import SaudiSecurityMaster, saudi_security_record_from_mapping
from kubo.saudi_post_open_cli import main as post_open_main
from kubo.saudi_admission import (
    AdmissionPurpose,
    verify_saudi_admission_receipt,
)
from tests.saudi.helpers import (
    identity_payload,
    synthetic_calendar_payload,
    write_admission_receipt,
)


class PostOpenScannerTests(unittest.TestCase):
    timezone = ZoneInfo("Asia/Riyadh")
    scan_at = datetime(2026, 8, 25, 10, 30, 30, tzinfo=timezone)

    def setUp(self):
        self.calendar = SaudiTradingCalendar(
            revision=calendar_revision_from_mapping(
                synthetic_calendar_payload(),
                known_at=self.scan_at,
            )
        )
        self.master = SaudiSecurityMaster(
            (saudi_security_record_from_mapping(identity_payload("2222")),)
        )
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        artifact_paths = {
            role: root / f"{role}.json"
            for role in ("input", "identity", "calendar", "weights")
        }
        for role, path in artifact_paths.items():
            path.write_text(
                json.dumps({"role": role, "synthetic": True}, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        execution_contract = {
            "scan_at": self.scan_at.isoformat(),
            "maximum_market_age_minutes": 15,
            "minimum_turnover_sar": 0.0,
            "maximum_candidates_per_horizon": 25,
        }
        receipt = root / "admission.json"
        write_admission_receipt(
            receipt,
            purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
            artifact_paths=artifact_paths,
            decision_at=self.scan_at,
            execution_contract=execution_contract,
        )
        self.admission = verify_saudi_admission_receipt(
            receipt,
            purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
            artifact_paths=artifact_paths,
            decision_at=self.scan_at,
            expected_execution_contract=execution_contract,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def scanner(self):
        return SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=self.master,
        )

    def weights(self):
        return {horizon: {"F9-governed-signal": 1.0} for horizon in ALL_HORIZONS}

    def observation(self, code="2222"):
        known_at = self.scan_at - timedelta(minutes=5)
        return PostOpenObservation(
            official_code=code,
            observed_at=known_at,
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
                    known_at=known_at,
                    source_id="licensed-saudi-market-feed",
                    rights_status="LICENSED_MODEL_USE",
                ),
            ),
        )

    def test_scan_abstains_before_open_plus_thirty_minutes(self):
        report = self.scanner().scan(
            (self.observation(),),
            admission=self.admission,
            scan_at=self.scan_at - timedelta(seconds=1),
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["reason"], "SCAN_BEFORE_OPEN_PLUS_30_MINUTES")

    def test_scan_emits_five_research_horizons_without_trade_advice(self):
        two_security_master = SaudiSecurityMaster(
            tuple(
                saudi_security_record_from_mapping(identity_payload(code))
                for code in ("1111", "2222")
            )
        )
        report = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=two_security_master,
        ).scan(
            (self.observation("2222"), self.observation("1111")),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "UNAUTHENTICATED_RESEARCH_CANDIDATES")
        self.assertFalse(report["input_admission_authenticated"])
        self.assertTrue(report["denominator_complete"])
        self.assertEqual(report["expected_security_count"], 2)
        self.assertEqual(
            set(report["candidates_by_horizon"]),
            {horizon.value for horizon in ALL_HORIZONS},
        )
        for rows in report["candidates_by_horizon"].values():
            self.assertEqual(rows[0]["research_status"], "RESEARCH_CANDIDATE")
            self.assertIsNone(rows[0]["recommendation"])
            self.assertIsNone(rows[0]["order"])
            self.assertIsNone(rows[0]["probability"])

    def test_incomplete_observation_denominator_abstains(self):
        two_security_master = SaudiSecurityMaster(
            tuple(
                saudi_security_record_from_mapping(identity_payload(code))
                for code in ("1111", "2222")
            )
        )
        report = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=two_security_master,
        ).scan(
            (self.observation("2222"),),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["reason"], "INCOMPLETE_OBSERVATION_DENOMINATOR")
        self.assertFalse(report["denominator_complete"])
        self.assertEqual(report["missing_official_codes"], ["1111"])

    def test_empty_identity_universe_is_not_a_complete_denominator(self):
        report = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=SaudiSecurityMaster(),
        ).scan(
            (),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["reason"], "EMPTY_OR_UNVERIFIED_UNIVERSE")
        self.assertFalse(report["denominator_complete"])
        self.assertEqual(report["expected_security_count"], 0)

    def test_liquidity_filter_does_not_turn_complete_data_into_missing_data(self):
        two_security_master = SaudiSecurityMaster(
            tuple(
                saudi_security_record_from_mapping(identity_payload(code))
                for code in ("1111", "2222")
            )
        )
        illiquid = replace(
            self.observation("1111"),
            average_daily_turnover_sar=500_000.0,
        )
        report = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=two_security_master,
            minimum_turnover_sar=1_000_000.0,
        ).scan(
            (illiquid, self.observation("2222")),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "UNAUTHENTICATED_RESEARCH_CANDIDATES")
        self.assertTrue(report["denominator_complete"])
        self.assertEqual(report["admitted_security_count"], 1)
        self.assertEqual(report["rejected"][0]["reason"], "LIQUIDITY_FLOOR_NOT_MET")

    def test_integrity_failure_takes_precedence_over_liquidity_exclusion(self):
        two_security_master = SaudiSecurityMaster(
            tuple(
                saudi_security_record_from_mapping(identity_payload(code))
                for code in ("1111", "2222")
            )
        )
        stale_illiquid = replace(
            self.observation("1111"),
            average_daily_turnover_sar=500_000.0,
            factors=(
                replace(
                    self.observation("1111").factors[0],
                    known_at=self.scan_at - timedelta(minutes=16),
                ),
            ),
        )
        report = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=two_security_master,
            minimum_turnover_sar=1_000_000.0,
        ).scan(
            (stale_illiquid, self.observation("2222")),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["reason"], "INCOMPLETE_OBSERVATION_DENOMINATOR")
        self.assertFalse(report["denominator_complete"])
        self.assertEqual(report["missing_official_codes"], ["1111"])
        self.assertEqual(report["rejected"][0]["reason"], "STALE_FACTOR_OBSERVATION")

    def test_missing_factor_cannot_be_silently_scored_as_zero(self):
        two_security_master = SaudiSecurityMaster(
            tuple(
                saudi_security_record_from_mapping(identity_payload(code))
                for code in ("1111", "2222")
            )
        )
        negative_factor = FactorObservation(
            factor_id="F9-negative",
            value=1.0,
            known_at=self.scan_at - timedelta(minutes=5),
            source_id="licensed-saudi-market-feed",
            rights_status="LICENSED_MODEL_USE",
        )
        complete = replace(
            self.observation("2222"),
            factors=self.observation("2222").factors + (negative_factor,),
        )
        weights = {
            horizon: {"F9-governed-signal": 1.0, "F9-negative": -10.0}
            for horizon in ALL_HORIZONS
        }
        report = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=two_security_master,
        ).scan(
            (self.observation("1111"), complete),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=weights,
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["reason"], "INCOMPLETE_OBSERVATION_DENOMINATOR")
        self.assertEqual(report["rejected"][0]["reason"], "FACTOR_SET_MISMATCH")

    def test_stale_or_end_of_day_market_rows_are_rejected(self):
        stale = replace(
            self.observation(),
            observed_at=self.scan_at - timedelta(minutes=16),
            factors=(
                replace(
                    self.observation().factors[0],
                    known_at=self.scan_at - timedelta(minutes=16),
                ),
            ),
        )
        report = self.scanner().scan(
            (stale,),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["rejected"][0]["reason"], "STALE_MARKET_OBSERVATION")

        stale_factor = replace(
            self.observation(),
            factors=(
                replace(
                    self.observation().factors[0],
                    known_at=self.scan_at - timedelta(minutes=16),
                ),
            ),
        )
        factor_report = self.scanner().scan(
            (stale_factor,),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(factor_report["status"], "ABSTAIN")
        self.assertEqual(
            factor_report["rejected"][0]["reason"],
            "STALE_FACTOR_OBSERVATION",
        )

    def test_scan_end_is_exclusive_with_calendar_uncertainty(self):
        last_safe_scan = datetime(2026, 8, 25, 15, 19, 29, tzinfo=self.timezone)
        observed_at = last_safe_scan - timedelta(minutes=5)
        observation = replace(
            self.observation(),
            observed_at=observed_at,
            factors=(replace(self.observation().factors[0], known_at=observed_at),),
        )
        accepted = self.scanner().scan(
            (observation,),
            admission=self.admission,
            scan_at=last_safe_scan,
            horizon_weights=self.weights(),
        )
        self.assertEqual(
            accepted["status"], "UNAUTHENTICATED_RESEARCH_CANDIDATES"
        )

        at_governed_end = self.scanner().scan(
            (observation,),
            admission=self.admission,
            scan_at=last_safe_scan + timedelta(seconds=1),
            horizon_weights=self.weights(),
        )
        self.assertEqual(at_governed_end["status"], "ABSTAIN")
        self.assertEqual(at_governed_end["reason"], "SCAN_AFTER_TRADING_SESSION")

    def test_scanner_rechecks_calendar_revision_at_scan_cutoff(self):
        payload = synthetic_calendar_payload()
        payload["known_to"] = "2026-08-26T00:00:00+03:00"
        calendar = SaudiTradingCalendar(
            revision=calendar_revision_from_mapping(payload, known_at=self.scan_at)
        )
        report = SaudiPostOpenScanner(
            calendar=calendar,
            security_master=self.master,
        ).scan(
            (),
            admission=self.admission,
            scan_at=datetime(2026, 8, 26, 10, 30, 30, tzinfo=self.timezone),
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["reason"], CALENDAR_REVISION_NOT_KNOWN)

    def test_post_open_mapping_and_weights_reject_json_type_coercion(self):
        payload = self.observation().to_dict()
        payload["official_code"] = 2222
        with self.assertRaisesRegex(ValueError, "official_code"):
            post_open_observation_from_mapping(
                payload,
                admission=self.admission,
            )

        with self.assertRaisesRegex(ValueError, "last_price_sar"):
            replace(self.observation(), last_price_sar=True)
        with self.assertRaisesRegex(ValueError, "non-empty tuple"):
            replace(
                self.observation(),
                factors=[self.observation().factors[0]],
            )
        with self.assertRaisesRegex(ValueError, "FactorObservation"):
            replace(self.observation(), factors=(object(),))
        new_york = ZoneInfo("America/New_York")
        observed_at = datetime(
            2026, 11, 1, 1, 30, tzinfo=new_york, fold=0
        )
        future_absolute_factor = replace(
            self.observation().factors[0],
            known_at=datetime(
                2026, 11, 1, 1, 15, tzinfo=new_york, fold=1
            ),
        )
        with self.assertRaisesRegex(ValueError, "known after"):
            replace(
                self.observation(),
                observed_at=observed_at,
                factors=(future_absolute_factor,),
            )
        invalid_weights = self.weights()
        invalid_weights[ALL_HORIZONS[0]] = {"F9-governed-signal": True}
        with self.assertRaisesRegex(ValueError, "finite factor weights"):
            self.scanner().scan(
                (self.observation(),),
                admission=self.admission,
                scan_at=self.scan_at,
                horizon_weights=invalid_weights,
            )
        with self.assertRaisesRegex(ValueError, "minimum_turnover_sar"):
            SaudiPostOpenScanner(minimum_turnover_sar=True)
        with self.assertRaisesRegex(ValueError, "governed maximum"):
            SaudiPostOpenScanner(maximum_market_age=timedelta(minutes=16))
        with self.assertRaisesRegex(ValueError, "maximum_candidates_per_horizon"):
            self.scanner().scan(
                (self.observation(),),
                admission=self.admission,
                scan_at=self.scan_at,
                horizon_weights=self.weights(),
                maximum_candidates_per_horizon=True,
            )
        with self.assertRaisesRegex(ValueError, "governed maximum"):
            self.scanner().scan(
                (self.observation(),),
                admission=self.admission,
                scan_at=self.scan_at,
                horizon_weights=self.weights(),
                maximum_candidates_per_horizon=26,
            )
        inconsistent_horizon_factors = self.weights()
        inconsistent_horizon_factors[ALL_HORIZONS[0]] = {
            "F9-governed-signal": 1.0,
            "F9-extra": 1.0,
        }
        with self.assertRaisesRegex(ValueError, "same exact factor set"):
            self.scanner().scan(
                (self.observation(),),
                admission=self.admission,
                scan_at=self.scan_at,
                horizon_weights=inconsistent_horizon_factors,
            )
        extreme_weights = self.weights()
        extreme_weights[ALL_HORIZONS[0]] = {"F9-governed-signal": 1e308}
        extreme_observation = replace(
            self.observation(),
            factors=(replace(self.observation().factors[0], value=1e308),),
        )
        with self.assertRaisesRegex(ValueError, "NON_FINITE_RESEARCH_SCORE"):
            self.scanner().scan(
                (extreme_observation,),
                admission=self.admission,
                scan_at=self.scan_at,
                horizon_weights=extreme_weights,
            )

    def test_cli_consumes_nightly_weight_export_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observations = root / "observations.jsonl"
            observations.write_text(
                json.dumps(self.observation().to_dict(), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            weights = root / "weights.json"
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
            output = root / "post-open-output"
            identity = root / "identity.json"
            identity.write_text(
                json.dumps([identity_payload("2222")], sort_keys=True) + "\n",
                encoding="utf-8",
            )
            calendar = root / "calendar.json"
            calendar.write_text(
                json.dumps(synthetic_calendar_payload(), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            admission_receipt = root / "admission.json"
            write_admission_receipt(
                admission_receipt,
                purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
                artifact_paths={
                    "input": observations,
                    "identity": identity,
                    "calendar": calendar,
                    "weights": weights,
                },
                decision_at=self.scan_at,
            )
            with redirect_stdout(StringIO()):
                code = post_open_main(
                    [
                        "--observations", str(observations),
                        "--weights", str(weights),
                        "--identity-file", str(identity),
                        "--calendar-file", str(calendar),
                        "--admission-receipt", str(admission_receipt),
                        "--scan-at", self.scan_at.isoformat(),
                        "--output-root", str(output),
                    ]
                )
            self.assertEqual(code, 0)
            report = json.loads((output / "post_open_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "SYNTHETIC_RESEARCH_CANDIDATES")
            self.assertFalse(report["report_is_market_evidence"])

    def test_default_calendar_fails_closed_and_reit_is_rejected(self):
        no_calendar = SaudiPostOpenScanner(security_master=self.master).scan(
            (self.observation(),),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(no_calendar["status"], "ABSTAIN")
        self.assertEqual(no_calendar["reason"], "CALENDAR_COVERAGE_MISSING")

        reit_master = SaudiSecurityMaster(
            [
                saudi_security_record_from_mapping(
                    identity_payload("2222", instrument_type="REIT")
                )
            ]
        )
        report = SaudiPostOpenScanner(
            calendar=self.calendar,
            security_master=reit_master,
        ).scan(
            (self.observation(),),
            admission=self.admission,
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["reason"], "EMPTY_OR_UNVERIFIED_UNIVERSE")
        self.assertFalse(report["denominator_complete"])
        self.assertEqual(report["unexpected_official_codes"], ["2222"])


if __name__ == "__main__":
    unittest.main()
