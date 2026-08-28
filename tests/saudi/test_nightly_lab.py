from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from contextlib import redirect_stdout
from io import StringIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from kubo.saudi_capabilities.nightly_lab import (
    ALL_HORIZONS,
    BlindHoldoutEvent,
    Cohort,
    EventType,
    FactorObservation,
    HistoricalEvent,
    HoldoutOutcomeVault,
    OutcomeVaultEntry,
    OutcomeObservation,
    build_temporal_split,
    evaluate_sealed_holdout,
    fit_and_calibrate,
    historical_event_from_mapping,
    holdout_outcome_vault_from_mapping,
    prepare_nightly_run,
    seal_holdout_predictions,
    sealed_prediction_packet_from_mapping,
)
from kubo.markets.saudi.identity import (
    SaudiSecurityMaster,
    saudi_security_record_from_mapping,
)
from kubo.markets.saudi.calendar import (
    SaudiTradingCalendar,
    calendar_revision_from_mapping,
)
from kubo.saudi_nightly_cli import main as nightly_main
from kubo.saudi_holdout_cli import main as holdout_main
from kubo.saudi_admission import AdmissionPurpose, verify_saudi_admission_receipt
from kubo.saudi_evidence_reports import (
    CORPORATE_ACTIONS_REPORT_ROLE,
    CORPORATE_ACTION_ADJUSTMENT_BASIS,
    DENOMINATOR_REPORT_ROLE,
)
from tests.saudi.helpers import (
    identity_payload,
    synthetic_calendar_payload,
    write_admission_receipt,
)


class NightlyLabTests(unittest.TestCase):
    timezone = ZoneInfo("Asia/Riyadh")
    run_at = datetime(2026, 8, 25, 22, 0, tzinfo=timezone)
    base = datetime(2016, 9, 1, 10, 0, tzinfo=timezone)

    def setUp(self):
        payload = synthetic_calendar_payload()
        payload["coverage_from"] = "2016-08-25"
        payload["schedule"]["effective_from"] = "2016-08-25"
        payload["known_from"] = "2016-08-25T00:00:00+03:00"
        self.calendar = SaudiTradingCalendar(
            revision=calendar_revision_from_mapping(payload, known_at=self.run_at)
        )

    def event(self, number: int, cohort: Cohort, timeline_index: int) -> HistoricalEvent:
        prediction_at = self.base + timedelta(days=timeline_index)
        event_at = prediction_at + timedelta(hours=4)
        signal = ((number % 9) - 4) / 4 or 0.25
        factors = (
            FactorObservation(
                factor_id="F9-governed-signal",
                value=signal,
                known_at=prediction_at - timedelta(minutes=5),
                source_id="saudi-exchange-history",
                rights_status="PUBLIC_RESEARCH_ALLOWED",
            ),
        )
        outcomes = tuple(
            OutcomeObservation(
                horizon=horizon,
                excess_return=signal * (index + 1) * 0.01,
                known_at=event_at + timedelta(days=370),
            )
            for index, horizon in enumerate(ALL_HORIZONS)
        )
        prefix = "primary" if cohort is Cohort.PRIMARY else "probe"
        return HistoricalEvent(
            event_id=f"{prefix}-{number:04d}",
            official_code=f"{1000 + number:04d}",
            prediction_at=prediction_at,
            event_at=event_at,
            evidence_known_at=event_at,
            cohort=cohort,
            event_type=EventType.EARNINGS,
            source_id="saudi-exchange-announcements",
            source_role="OFFICIAL_VERIFICATION",
            rights_status="PUBLIC_RESEARCH_ALLOWED",
            factors=factors,
            outcomes=outcomes,
            denominator_complete=True,
            corporate_actions_reconciled=True,
            identity_verified=True,
        )

    def corpus(self) -> tuple[HistoricalEvent, ...]:
        # Cover the governed ten-year window while leaving one year for the
        # longest outcome to mature before run_at.  Extra rows are required
        # because causal boundary-crossing labels are purged.
        final_prediction = self.run_at - timedelta(days=370)
        span_days = (final_prediction - self.base).days
        primary = tuple(
            self.event(index, Cohort.PRIMARY, round(index * span_days / 79))
            for index in range(80)
        )
        probe = tuple(
            self.event(index + 80, Cohort.PROBE, round(index * span_days / 479))
            for index in range(480)
        )
        return primary + probe

    def verified_nightly_admission(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        artifact_paths = {
            role: root / f"{role}.json"
            for role in (
                "input",
                "identity",
                "calendar",
                "denominator_report",
                "corporate_actions_report",
            )
        }
        for role, path in artifact_paths.items():
            path.write_text(
                json.dumps({"role": role, "synthetic": True}, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        execution_contract = {
            "run_id": "synthetic-nightly-run",
            "run_at": self.run_at.isoformat(),
            "lookback_years": 10,
            "minimum_primary": 50,
            "minimum_probe": 300,
            "coverage_tolerance_days": 31,
            "maturity_buffer_days": 370,
            "maximum_coverage_gap_days": 396,
        }
        receipt = root / "admission.json"
        write_admission_receipt(
            receipt,
            purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
            artifact_paths=artifact_paths,
            decision_at=self.run_at,
            execution_contract=execution_contract,
        )
        return verify_saudi_admission_receipt(
            receipt,
            purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
            artifact_paths=artifact_paths,
            decision_at=self.run_at,
            expected_execution_contract=execution_contract,
        )

    def test_minimum_gate_stops_without_updating_a_model(self):
        prepared = prepare_nightly_run(
            (self.event(1, Cohort.PRIMARY, 1), self.event(2, Cohort.PROBE, 2)),
            run_id="small",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        self.assertEqual(prepared.status, "STOP_TRAINING")
        self.assertIsNone(prepared.model)
        self.assertIn("PRIMARY_EVENT_MINIMUM_NOT_MET", prepared.reasons)
        self.assertIn("PROBE_EVENT_MINIMUM_NOT_MET", prepared.reasons)

    def test_future_factor_is_rejected_as_leakage(self):
        event = self.event(1, Cohort.PRIMARY, 1)
        leaked_factor = replace(
            event.factors[0], known_at=event.prediction_at + timedelta(seconds=1)
        )
        with self.assertRaisesRegex(ValueError, "FEATURE_LEAKAGE"):
            replace(event, factors=(leaked_factor,))
        stale_factor = replace(
            event.factors[0],
            known_at=event.prediction_at - timedelta(days=371),
        )
        with self.assertRaisesRegex(ValueError, "STALE_FACTOR"):
            replace(event, factors=(stale_factor,))

    def test_future_factor_is_rejected_across_dst_fold(self):
        new_york = ZoneInfo("America/New_York")
        prediction_at = datetime(
            2026, 11, 1, 1, 45, tzinfo=new_york, fold=0
        )
        event_at = datetime(2026, 11, 1, 2, 0, tzinfo=new_york, fold=1)
        future_factor = FactorObservation(
            factor_id="F9-governed-signal",
            value=1.0,
            known_at=datetime(2026, 11, 1, 1, 30, tzinfo=new_york, fold=1),
            source_id="synthetic-dst-probe",
            rights_status="PUBLIC_RESEARCH_ALLOWED",
        )
        original = self.event(1, Cohort.PRIMARY, 1)
        outcomes = tuple(
            replace(outcome, known_at=event_at + timedelta(days=370))
            for outcome in original.outcomes
        )
        with self.assertRaisesRegex(ValueError, "FEATURE_LEAKAGE"):
            replace(
                original,
                prediction_at=prediction_at,
                event_at=event_at,
                evidence_known_at=event_at,
                factors=(future_factor,),
                outcomes=outcomes,
            )

    def test_blind_holdout_rechecks_feature_cutoff(self):
        event = self.event(1, Cohort.PRIMARY, 1)
        leaked = replace(
            event.factors[0],
            known_at=event.prediction_at + timedelta(seconds=1),
        )
        with self.assertRaisesRegex(ValueError, "BLIND_HOLDOUT_FEATURE_LEAKAGE"):
            BlindHoldoutEvent(
                event_id=event.event_id,
                official_code=event.official_code,
                prediction_at=event.prediction_at,
                event_at=event.event_at,
                cohort=event.cohort,
                factors=(leaked,),
                outcome_not_before=tuple(
                    (outcome.horizon, outcome.known_at)
                    for outcome in event.outcomes
                ),
            )

    def test_horizon_maturity_floor_rejects_mislabeled_year_outcome(self):
        event = self.event(1, Cohort.PRIMARY, 1)
        outcomes = tuple(
            replace(outcome, known_at=event.event_at + timedelta(seconds=1))
            if outcome.horizon.value == "YEAR"
            else outcome
            for outcome in event.outcomes
        )
        with self.assertRaisesRegex(ValueError, "HORIZON_MINIMUM_MATURITY"):
            replace(event, outcomes=outcomes)

    def test_next_session_outcome_uses_calendar_session_end_not_elapsed_day(self):
        prediction_at = datetime(2026, 8, 27, 10, 0, tzinfo=self.timezone)
        event_at = datetime(2026, 8, 27, 14, 0, tzinfo=self.timezone)
        original = self.event(1, Cohort.PRIMARY, 1)

        def outcomes(next_session_known_at):
            maturity = {
                "INTRADAY": event_at + timedelta(hours=1),
                "NEXT_SESSION": next_session_known_at,
                "WEEK": event_at + timedelta(days=7),
                "MONTH": event_at + timedelta(days=28),
                "YEAR": event_at + timedelta(days=365),
            }
            return tuple(
                replace(outcome, known_at=maturity[outcome.horizon.value])
                for outcome in original.outcomes
            )

        friday_label = replace(
            original,
            prediction_at=prediction_at,
            event_at=event_at,
            evidence_known_at=event_at,
            factors=(replace(original.factors[0], known_at=prediction_at),),
            outcomes=outcomes(
                datetime(2026, 8, 28, 15, 20, 30, tzinfo=self.timezone)
            ),
        )
        with self.assertRaisesRegex(
            ValueError, "NEXT_SESSION_OUTCOME_AVAILABLE_BEFORE_SESSION_END"
        ):
            build_temporal_split(
                (friday_label,),
                calendar=self.calendar,
                cohort_minimums={Cohort.PRIMARY: 3, Cohort.PROBE: 3},
            )
        with self.assertRaisesRegex(
            ValueError, "NEXT_SESSION_OUTCOME_AVAILABLE_BEFORE_SESSION_END"
        ):
            prepare_nightly_run(
                (friday_label,),
                run_id="thursday-friday-label",
                run_at=datetime(2027, 9, 1, 22, 0, tzinfo=self.timezone),
                calendar=self.calendar,
                lookback_years=2,
            )

        sunday_close_label = replace(
            friday_label,
            outcomes=outcomes(
                datetime(2026, 8, 30, 15, 20, 30, tzinfo=self.timezone)
            ),
        )
        stopped = prepare_nightly_run(
            (sunday_close_label,),
            run_id="thursday-sunday-label",
            run_at=datetime(2027, 9, 1, 22, 0, tzinfo=self.timezone),
            calendar=self.calendar,
            lookback_years=2,
        )
        self.assertEqual(stopped.status, "STOP_TRAINING")

    def test_evidence_known_after_boundaries_cannot_enter_causal_fit(self):
        rows = tuple(
            replace(event, evidence_known_at=self.run_at)
            for event in self.corpus()
        )
        prepared = prepare_nightly_run(
            rows,
            run_id="post-boundary-evidence",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        self.assertEqual(prepared.status, "STOP_TRAINING")
        self.assertEqual(
            prepared.reasons,
            ("CAUSAL_TEMPORAL_SPLIT_MINIMUMS_NOT_MET",),
        )

    def test_extreme_finite_inputs_fail_before_nonfinite_model_output(self):
        training = self.event(1, Cohort.PRIMARY, 1)
        validation = self.event(2, Cohort.PROBE, 2)

        def extreme(event):
            return replace(
                event,
                factors=(replace(event.factors[0], value=1e308),),
                outcomes=tuple(
                    replace(outcome, excess_return=1e308)
                    for outcome in event.outcomes
                ),
            )

        with self.assertRaisesRegex(ValueError, "training arithmetic"):
            fit_and_calibrate((extreme(training),), (extreme(validation),))

    def test_direction_uses_the_stored_rounded_score(self):
        prepared = prepare_nightly_run(
            self.corpus(),
            run_id="rounding-boundary",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        model = prepared.model.with_horizon_weights(
            tuple(
                replace(item, weights=(("F9-governed-signal", 1.4e-12),))
                for item in prepared.model.horizon_weights
            ),
        )
        packet = seal_holdout_predictions(
            run_id="rounding-boundary",
            sealed_at=self.run_at,
            model=model,
            blind_events=(prepared.split.blind_holdout[0],),
            calendar=self.calendar,
        )
        packet.verify()
        self.assertTrue(all(item.direction == "FLAT" for item in packet.predictions))

    def test_event_mapping_rejects_json_type_coercion(self):
        event = self.event(1, Cohort.PRIMARY, 1)
        master = SaudiSecurityMaster(
            [saudi_security_record_from_mapping(identity_payload(event.official_code))]
        )
        admission = self.verified_nightly_admission()

        cases = (
            ("factor bool", ("factors", 0, "value"), True, "JSON number"),
            ("outcome bool", ("outcomes", 0, "excess_return"), False, "JSON number"),
            ("numeric official code", ("official_code",), 1001, "must be a string"),
        )
        for name, path, replacement, message in cases:
            with self.subTest(name=name):
                payload = json.loads(json.dumps(event.to_dict()))
                target = payload
                for component in path[:-1]:
                    target = target[component]
                target[path[-1]] = replacement
                with self.assertRaisesRegex(ValueError, message):
                    historical_event_from_mapping(
                        payload,
                        security_master=master,
                        admission=admission,
                    )

    def test_direct_records_reject_python_type_coercion(self):
        event = self.event(1, Cohort.PRIMARY, 1)
        with self.assertRaisesRegex(ValueError, "factor value must be finite"):
            replace(event.factors[0], value="0.5")
        with self.assertRaisesRegex(ValueError, "outcome excess_return must be finite"):
            replace(event.outcomes[0], excess_return="0.1")
        with self.assertRaisesRegex(ValueError, "denominator_complete must be a boolean"):
            replace(event, denominator_complete="true")

    def test_missing_factor_cannot_be_silently_imputed_to_zero(self):
        rows = list(self.corpus())
        event = rows[0]
        rows[0] = replace(
            event,
            factors=event.factors
            + (
                FactorObservation(
                    factor_id="F9-extra",
                    value=0.5,
                    known_at=event.prediction_at - timedelta(minutes=5),
                    source_id="saudi-exchange-history",
                    rights_status="PUBLIC_RESEARCH_ALLOWED",
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "NO_MISSINGNESS_POLICY"):
            prepare_nightly_run(
                rows,
                run_id="nightly-inconsistent-factor-set",
                run_at=self.run_at,
                calendar=self.calendar,
            )

    def test_historical_identity_date_uses_riyadh_timezone(self):
        admission = self.verified_nightly_admission()
        identity = identity_payload("1001")
        identity["valid_from"] = "2016-09-02"
        identity["valid_to"] = "2016-09-02"
        master = SaudiSecurityMaster([saudi_security_record_from_mapping(identity)])
        payload = self.event(1, Cohort.PRIMARY, 1).to_dict()
        payload["prediction_at"] = "2016-09-01T21:30:00+00:00"
        payload["event_at"] = "2016-09-02T01:00:00+00:00"
        payload["evidence_known_at"] = "2016-09-02T01:00:00+00:00"
        payload["factors"][0]["known_at"] = "2016-09-01T21:25:00+00:00"
        for outcome in payload["outcomes"]:
            outcome["known_at"] = "2017-09-02T01:00:00+00:00"
        parsed = historical_event_from_mapping(
            payload,
            security_master=master,
            admission=admission,
        )
        self.assertEqual(parsed.official_code, "1001")

    def test_temporal_fit_is_deterministic_and_holdout_is_withheld_from_fit(self):
        first = prepare_nightly_run(
            self.corpus(),
            run_id="nightly-1",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        second = prepare_nightly_run(
            reversed(self.corpus()),
            run_id="nightly-1",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        self.assertEqual(
            first.status,
            "UNAUTHENTICATED_SEALED_AWAITING_FINAL_SCORE",
        )
        self.assertIsNotNone(first.model)
        self.assertIsNotNone(first.split)
        self.assertIsNotNone(first.sealed_packet)
        self.assertEqual(first.model.fingerprint, second.model.fingerprint)
        self.assertEqual(first.sealed_packet.seal_sha256, second.sealed_packet.seal_sha256)
        training_ids = set(first.model.training_event_ids)
        validation_ids = set(first.model.validation_event_ids)
        holdout_ids = {event.event_id for event in first.split.blind_holdout}
        self.assertFalse(training_ids & holdout_ids)
        self.assertFalse(validation_ids & holdout_ids)
        self.assertTrue(all(not hasattr(event, "outcomes") for event in first.split.blind_holdout))
        self.assertLess(
            max(event.prediction_at for event in first.split.training),
            min(event.prediction_at for event in first.split.validation),
        )
        self.assertLess(
            first.split.max_training_label_end,
            min(event.prediction_at for event in first.split.validation),
        )
        self.assertLess(
            first.split.max_validation_label_end,
            min(event.prediction_at for event in first.split.blind_holdout),
        )
        self.assertLess(
            first.split.max_training_information_end,
            min(event.prediction_at for event in first.split.validation),
        )
        self.assertLess(
            first.split.max_validation_information_end,
            min(event.prediction_at for event in first.split.blind_holdout),
        )
        training_times = {event.prediction_at for event in first.split.training}
        validation_times = {event.prediction_at for event in first.split.validation}
        holdout_times = {event.prediction_at for event in first.split.blind_holdout}
        self.assertFalse(training_times & validation_times)
        self.assertFalse(training_times & holdout_times)
        self.assertFalse(validation_times & holdout_times)
        for cohort, minimums in {
            "PRIMARY": (30, 10, 10),
            "PROBE": (180, 60, 60),
        }.items():
            counts = first.split.cohort_counts[cohort]
            self.assertGreaterEqual(counts["training"], minimums[0])
            self.assertGreaterEqual(counts["validation"], minimums[1])
            self.assertGreaterEqual(counts["final_holdout"], minimums[2])
        self.assertTrue(first.split.purged_event_ids)
        self.assertEqual(first.split.source_event_count, len(self.corpus()))
        self.assertEqual(
            first.split.retained_event_count,
            len(first.split.training)
            + len(first.split.validation)
            + len(first.split.blind_holdout),
        )
        self.assertAlmostEqual(sum(first.split.retained_ratios.values()), 1.0)
        self.assertLess(abs(first.split.retained_ratios["training"] - 0.60), 0.01)
        self.assertLess(abs(first.split.retained_ratios["validation"] - 0.20), 0.01)
        self.assertLess(abs(first.split.retained_ratios["final_holdout"] - 0.20), 0.01)
        self.assertAlmostEqual(
            first.split.purge_rate,
            len(first.split.purged_event_ids) / len(self.corpus()),
        )
        self.assertFalse(
            first.coverage_audit["cohorts"]["PRIMARY"]["missing_annual_buckets"]
        )
        self.assertFalse(
            first.coverage_audit["cohorts"]["PROBE"]["missing_annual_buckets"]
        )

        report = evaluate_sealed_holdout(
            first.sealed_packet,
            first.split.outcome_vault,
            scored_at=self.run_at,
        )
        self.assertEqual(report["status"], "UNAUTHENTICATED_HOLDOUT_METRICS_COMPUTED")
        self.assertFalse(report["authenticated"])
        self.assertIsNone(report["recommendation"])
        self.assertEqual(set(report["metrics"]), {item.value for item in ALL_HORIZONS})

    def test_model_fingerprint_and_holdout_fit_disjointness_are_reverified(self):
        repeated = self.event(1, Cohort.PRIMARY, 1)
        with self.assertRaisesRegex(ValueError, "must be disjoint"):
            fit_and_calibrate((repeated,), (repeated,))

        prepared = prepare_nightly_run(
            self.corpus(),
            run_id="model-integrity",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        model = prepared.model
        blind = prepared.split.blind_holdout[0]
        with self.assertRaisesRegex(ValueError, "exactly the governed horizons"):
            model.build(
                horizon_weights=model.horizon_weights[:-1],
                training_event_ids=model.training_event_ids,
                validation_event_ids=model.validation_event_ids,
            )
        overlapping = replace(blind, event_id=model.training_event_ids[0])
        with self.assertRaisesRegex(ValueError, "OVERLAPS_MODEL_FIT"):
            seal_holdout_predictions(
                run_id="overlapping-holdout",
                sealed_at=self.run_at,
                model=model,
                blind_events=(overlapping,),
                calendar=self.calendar,
            )

        changed_blind = replace(
            blind,
            factors=(replace(blind.factors[0], value=0.99),),
        )

        class SwitchingEvents:
            def __init__(self):
                self.iterations = 0

            def __iter__(self):
                self.iterations += 1
                yield blind if self.iterations == 1 else changed_blind

        switching = SwitchingEvents()
        snapshotted = seal_holdout_predictions(
            run_id="snapshotted-holdout",
            sealed_at=self.run_at,
            model=model,
            blind_events=switching,
            calendar=self.calendar,
        )
        expected = seal_holdout_predictions(
            run_id="snapshotted-holdout",
            sealed_at=self.run_at,
            model=model,
            blind_events=(blind,),
            calendar=self.calendar,
        )
        self.assertEqual(switching.iterations, 1)
        self.assertEqual(snapshotted.blind_event_sha256, expected.blind_event_sha256)
        self.assertEqual(snapshotted.predictions, expected.predictions)

        changed_cutoffs = (
            (
                blind.outcome_not_before[0][0],
                blind.outcome_not_before[0][1] + timedelta(seconds=1),
            ),
        ) + blind.outcome_not_before[1:]
        with self.assertRaisesRegex(
            ValueError, "BLIND_HOLDOUT_MATURITY_CUTOFF_MISMATCH"
        ):
            seal_holdout_predictions(
                run_id="tampered-maturity-cutoff",
                sealed_at=self.run_at,
                model=model,
                blind_events=(replace(blind, outcome_not_before=changed_cutoffs),),
                calendar=self.calendar,
            )

        changed_weights = tuple(
            replace(
                item,
                weights=((item.weights[0][0], item.weights[0][1] + 0.25),),
            )
            for item in model.horizon_weights
        )
        with self.assertRaisesRegex(ValueError, "FITTED_MODEL_FINGERPRINT_MISMATCH"):
            replace(model, horizon_weights=changed_weights)

        object.__setattr__(model, "fingerprint", "0" * 64)
        with self.assertRaisesRegex(ValueError, "FITTED_MODEL_FINGERPRINT_MISMATCH"):
            seal_holdout_predictions(
                run_id="tampered-model",
                sealed_at=self.run_at,
                model=model,
                blind_events=(blind,),
                calendar=self.calendar,
            )

    def test_holdout_outcomes_must_be_available_when_predictions_are_sealed(self):
        prepared = prepare_nightly_run(
            self.corpus(),
            run_id="nightly-late-label",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        packet = prepared.sealed_packet
        split = prepared.split
        self.assertIsNotNone(packet)
        self.assertIsNotNone(split)
        first_entry = split.outcome_vault.entries[0]
        late_year = replace(
            first_entry.outcomes[-1],
            known_at=self.run_at + timedelta(days=1),
        )
        late_entry = replace(
            first_entry,
            outcomes=first_entry.outcomes[:-1] + (late_year,),
        )
        late_vault = HoldoutOutcomeVault.build(
            (late_entry,) + split.outcome_vault.entries[1:]
        )
        with self.assertRaisesRegex(ValueError, "NOT_AVAILABLE_AT_SEAL"):
            evaluate_sealed_holdout(
                packet,
                late_vault,
                scored_at=self.run_at + timedelta(days=2),
            )

    def test_holdout_maturity_remains_anchored_to_event_and_calendar(self):
        prepared = prepare_nightly_run(
            self.corpus(),
            run_id="holdout-maturity-anchor",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        packet = prepared.sealed_packet
        vault = prepared.split.outcome_vault
        entry = vault.entries[0]
        cutoffs = {
            prediction.horizon: prediction.outcome_not_before
            for prediction in packet.predictions
            if prediction.event_id == entry.event_id
        }
        anchored_outcomes = tuple(
            replace(
                outcome,
                known_at=(
                    cutoffs[outcome.horizon] - timedelta(seconds=1)
                    if outcome.horizon.value == "YEAR"
                    else cutoffs[outcome.horizon]
                ),
            )
            for outcome in entry.outcomes
        )
        anchored_entry = OutcomeVaultEntry(
            event_id=entry.event_id,
            outcomes=anchored_outcomes,
        )
        altered_vault = HoldoutOutcomeVault.build(
            (anchored_entry,) + vault.entries[1:]
        )
        with self.assertRaisesRegex(ValueError, "HORIZON_MINIMUM_MATURITY"):
            evaluate_sealed_holdout(
                packet,
                altered_vault,
                scored_at=self.run_at,
            )

    def test_tampering_after_seal_is_detected(self):
        prepared = prepare_nightly_run(
            self.corpus(),
            run_id="nightly-tamper",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        packet = prepared.sealed_packet
        self.assertIsNotNone(packet)
        changed = replace(packet.predictions[0], score=packet.predictions[0].score + 1.0)
        tampered = replace(packet, predictions=(changed,) + packet.predictions[1:])
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
            evaluate_sealed_holdout(
                tampered,
                prepared.split.outcome_vault,
                scored_at=self.run_at,
            )

    def test_sealed_packet_rejects_structural_prediction_tampering(self):
        prepared = prepare_nightly_run(
            self.corpus(),
            run_id="nightly-structure",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        packet = prepared.sealed_packet
        self.assertIsNotNone(packet)
        first = packet.predictions[0]

        opposite = "DOWN" if first.direction == "UP" else "UP"
        with self.assertRaisesRegex(ValueError, "direction does not match"):
            replace(
                packet,
                predictions=(replace(first, direction=opposite),)
                + packet.predictions[1:],
            )

        same_event = tuple(
            item for item in packet.predictions if item.event_id == first.event_id
        )
        removed_horizon = tuple(
            item
            for item in packet.predictions
            if item is not same_event[-1]
        )
        with self.assertRaisesRegex(ValueError, "five governed horizons"):
            replace(packet, predictions=removed_horizon)

        with self.assertRaisesRegex(ValueError, "metadata is inconsistent"):
            replace(
                packet,
                predictions=(replace(first, official_code="9999"),)
                + packet.predictions[1:],
            )

        with self.assertRaisesRegex(ValueError, "cannot follow sealed_at"):
            replace(
                packet,
                predictions=(
                    replace(
                        first,
                        prediction_at=packet.sealed_at + timedelta(seconds=1),
                        event_at=packet.sealed_at + timedelta(seconds=2),
                        outcome_not_before=packet.sealed_at
                        + timedelta(seconds=3),
                    ),
                )
                + packet.predictions[1:],
            )

        uppercase_hash = packet.to_dict()
        uppercase_hash["seal_sha256"] = packet.seal_sha256.upper()
        with self.assertRaisesRegex(ValueError, "seal_sha256 is invalid"):
            sealed_prediction_packet_from_mapping(uppercase_hash)

        bool_score = packet.to_dict()
        bool_score["predictions"][0]["score"] = True
        with self.assertRaisesRegex(ValueError, "JSON number"):
            sealed_prediction_packet_from_mapping(bool_score)

    def test_vault_rejects_invalid_structure_and_temporal_pairing(self):
        event = self.event(1, Cohort.PRIMARY, 1)
        delayed_intraday = replace(
            event.outcomes[0],
            known_at=event.outcomes[1].known_at + timedelta(seconds=1),
        )
        with self.assertRaisesRegex(ValueError, "nondecreasing by horizon"):
            OutcomeVaultEntry(
                event_id=event.event_id,
                outcomes=(delayed_intraday,) + event.outcomes[1:],
            )

        prepared = prepare_nightly_run(
            self.corpus(),
            run_id="nightly-vault",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        vault = prepared.split.outcome_vault
        with self.assertRaisesRegex(ValueError, "event_id values must be unique"):
            replace(vault, entries=(vault.entries[0], vault.entries[0]))

        entry = vault.entries[0]
        prediction = next(
            item
            for item in prepared.sealed_packet.predictions
            if item.event_id == entry.event_id
            and item.horizon is entry.outcomes[0].horizon
        )
        leaked_outcome = replace(
            entry.outcomes[0],
            known_at=prediction.prediction_at,
        )
        leaked_entry = OutcomeVaultEntry(
            event_id=entry.event_id,
            outcomes=(leaked_outcome,) + entry.outcomes[1:],
        )
        leaked_vault = HoldoutOutcomeVault.build(
            (leaked_entry,) + vault.entries[1:]
        )
        with self.assertRaisesRegex(ValueError, "OUTCOME_LEAKAGE"):
            evaluate_sealed_holdout(
                prepared.sealed_packet,
                leaked_vault,
                scored_at=self.run_at,
            )

    def test_prediction_time_must_be_inside_the_governed_lookback(self):
        event = self.event(1, Cohort.PRIMARY, 0)
        old_prediction = self.base - timedelta(days=365 * 11)
        outside = replace(
            event,
            prediction_at=old_prediction,
            factors=(
                replace(
                    event.factors[0],
                    known_at=old_prediction - timedelta(minutes=1),
                ),
            ),
        )
        with self.assertRaisesRegex(
            ValueError, "PREDICTION_OUTSIDE_GOVERNED_LOOKBACK_WINDOW"
        ):
            prepare_nightly_run(
                (outside,),
                run_id="outside-window",
                run_at=self.run_at,
                calendar=self.calendar,
            )

    def test_ten_year_label_coverage_is_a_gate_not_only_a_maximum(self):
        short = tuple(
            self.event(index, Cohort.PRIMARY, 2000 + index)
            for index in range(50)
        ) + tuple(
            self.event(index + 50, Cohort.PROBE, 2000 + index)
            for index in range(300)
        )
        prepared = prepare_nightly_run(
            short,
            run_id="short-history",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        self.assertEqual(prepared.status, "STOP_TRAINING")
        self.assertIn("HISTORY_START_COVERAGE_NOT_MET", prepared.reasons)
        self.assertIn("LATEST_OUTCOME_COVERAGE_NOT_MET", prepared.reasons)

    def test_endpoint_only_history_fails_annual_and_max_gap_coverage(self):
        final_prediction = self.run_at - timedelta(days=370)
        final_index = (final_prediction - self.base).days
        events = []
        number = 0
        for cohort, counts in (
            (Cohort.PRIMARY, (30, 10, 10)),
            (Cohort.PROBE, (180, 60, 60)),
        ):
            for timeline_index, count in zip((0, 730, final_index), counts):
                for _ in range(count):
                    events.append(self.event(number, cohort, timeline_index))
                    number += 1
        prepared = prepare_nightly_run(
            events,
            run_id="endpoint-only-history",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        self.assertEqual(prepared.status, "STOP_TRAINING")
        self.assertIn("ANNUAL_BUCKET_COVERAGE_NOT_MET", prepared.reasons)
        self.assertIn("MAXIMUM_GAP_COVERAGE_NOT_MET", prepared.reasons)
        for cohort in ("PRIMARY", "PROBE"):
            audit = prepared.coverage_audit["cohorts"][cohort]
            self.assertTrue(audit["missing_annual_buckets"])
            self.assertGreater(audit["maximum_gap_days"], 396)

    def test_raw_minimums_do_not_override_post_purge_split_minimums(self):
        final_prediction = self.run_at - timedelta(days=370)
        span_days = (final_prediction - self.base).days
        exact_minimum = tuple(
            self.event(index, Cohort.PRIMARY, round(index * span_days / 49))
            for index in range(50)
        ) + tuple(
            self.event(index + 50, Cohort.PROBE, round(index * span_days / 299))
            for index in range(300)
        )
        prepared = prepare_nightly_run(
            exact_minimum,
            run_id="purge-minimum",
            run_at=self.run_at,
            calendar=self.calendar,
        )
        self.assertEqual(prepared.status, "STOP_TRAINING")
        self.assertEqual(
            prepared.reasons,
            ("CAUSAL_TEMPORAL_SPLIT_MINIMUMS_NOT_MET",),
        )

    def test_cli_publishes_atomic_weights_for_post_open_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events_path = root / "events.jsonl"
            events_path.write_text(
                "\n".join(
                    json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)
                    for event in self.corpus()
                )
                + "\n",
                encoding="utf-8",
            )
            output = root / "nightly-output"
            vault_output = root / "restricted-vault"
            identity = root / "identity.json"
            identity.write_text(
                json.dumps(
                    [identity_payload(event.official_code) for event in self.corpus()],
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            calendar = root / "calendar.json"
            calendar_payload = synthetic_calendar_payload()
            calendar_payload["coverage_from"] = "2016-08-25"
            calendar_payload["schedule"]["effective_from"] = "2016-08-25"
            calendar_payload["known_from"] = "2016-08-25T00:00:00+03:00"
            calendar.write_text(
                json.dumps(calendar_payload, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            common_evidence = {
                "schema_version": "1.0",
                "status": "PASS",
                "run_id": "cli-nightly",
                "input_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
                "coverage_from": "2016-08-25",
                "coverage_through": "2026-08-25",
                "event_count": len(self.corpus()),
                "security_set_sha256": hashlib.sha256(identity.read_bytes()).hexdigest(),
            }
            denominator = root / "denominator-report.json"
            denominator.write_text(
                json.dumps(
                    {**common_evidence, "role": DENOMINATOR_REPORT_ROLE},
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            corporate_actions = root / "corporate-actions-report.json"
            corporate_actions.write_text(
                json.dumps(
                    {
                        **common_evidence,
                        "role": CORPORATE_ACTIONS_REPORT_ROLE,
                        "unresolved_material_actions": 0,
                        "adjustment_basis": CORPORATE_ACTION_ADJUSTMENT_BASIS,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            admission_receipt = root / "admission.json"
            write_admission_receipt(
                admission_receipt,
                purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
                artifact_paths={
                    "input": events_path,
                    "identity": identity,
                    "calendar": calendar,
                    "denominator_report": denominator,
                    "corporate_actions_report": corporate_actions,
                },
                decision_at=self.run_at,
                execution_contract={
                    "run_id": "cli-nightly",
                    "run_at": self.run_at.isoformat(),
                    "lookback_years": 10,
                    "minimum_primary": 50,
                    "minimum_probe": 300,
                    "coverage_tolerance_days": 31,
                    "maturity_buffer_days": 370,
                    "maximum_coverage_gap_days": 396,
                },
            )
            with redirect_stdout(StringIO()):
                code = nightly_main(
                    [
                        "--events", str(events_path),
                        "--identity-file", str(identity),
                        "--calendar-file", str(calendar),
                        "--denominator-report", str(denominator),
                        "--corporate-actions-report", str(corporate_actions),
                        "--admission-receipt", str(admission_receipt),
                        "--output-root", str(output),
                        "--outcome-vault-output-root", str(vault_output),
                        "--run-id", "cli-nightly",
                        "--run-at", self.run_at.isoformat(),
                    ]
                )
            self.assertEqual(code, 0)
            weights = json.loads((output / "horizon_weights.json").read_text(encoding="utf-8"))
            self.assertEqual(set(weights), {horizon.value for horizon in ALL_HORIZONS})
            self.assertTrue((output / "sealed_predictions.json").is_file())
            self.assertFalse((output / "final_holdout_report.json").exists())
            self.assertTrue((vault_output / "outcome_vault.json").is_file())
            receipt = json.loads((output / "run_report.json").read_text(encoding="utf-8"))
            self.assertEqual(
                receipt["status"],
                "SYNTHETIC_SEALED_AWAITING_FINAL_SCORE",
            )
            self.assertEqual(receipt["evidence_class"], "SYNTHETIC_ONLY")
            self.assertFalse(receipt["final_holdout_scored"])
            self.assertTrue(receipt["input_admission_authenticated"])
            self.assertFalse(receipt["report_authenticated"])
            audit = receipt["temporal_audit"]
            self.assertLess(audit["max_training_label_end"], audit["validation_start"])
            self.assertLess(audit["max_validation_label_end"], audit["holdout_start"])
            self.assertLess(
                audit["max_training_information_end"], audit["validation_start"]
            )
            self.assertLess(
                audit["max_validation_information_end"], audit["holdout_start"]
            )
            self.assertGreater(audit["purged_event_count"], 0)

            score_output = root / "holdout-score"
            holdout_admission = root / "holdout-admission.json"
            write_admission_receipt(
                holdout_admission,
                purpose=AdmissionPurpose.HOLDOUT_SCORE,
                artifact_paths={
                    "sealed_predictions": output / "sealed_predictions.json",
                    "outcome_vault": vault_output / "outcome_vault.json",
                    "run_report": output / "run_report.json",
                },
                decision_at=self.run_at,
                execution_contract={
                    "scored_at": self.run_at.isoformat(),
                    "run_id": "cli-nightly",
                },
            )
            with redirect_stdout(StringIO()):
                score_code = holdout_main(
                    [
                        "--sealed-predictions", str(output / "sealed_predictions.json"),
                        "--outcome-vault", str(vault_output / "outcome_vault.json"),
                        "--run-report", str(output / "run_report.json"),
                        "--admission-receipt", str(holdout_admission),
                        "--run-id", "cli-nightly",
                        "--scored-at", self.run_at.isoformat(),
                        "--output-root", str(score_output),
                    ]
                )
            self.assertEqual(score_code, 0)
            final_report = json.loads(
                (score_output / "final_holdout_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(final_report["status"], "SYNTHETIC_HOLDOUT_METRICS")
            self.assertTrue(final_report["input_admission_authenticated"])
            self.assertFalse(final_report["report_authenticated"])

            predating_admission = root / "predating-holdout-admission.json"
            write_admission_receipt(
                predating_admission,
                purpose=AdmissionPurpose.HOLDOUT_SCORE,
                artifact_paths={
                    "sealed_predictions": output / "sealed_predictions.json",
                    "outcome_vault": vault_output / "outcome_vault.json",
                    "run_report": output / "run_report.json",
                },
                decision_at=self.run_at,
                issued_at=self.run_at - timedelta(minutes=1),
                execution_contract={
                    "scored_at": self.run_at.isoformat(),
                    "run_id": "cli-nightly",
                },
            )
            with self.assertRaisesRegex(ValueError, "cannot predate"):
                holdout_main(
                    [
                        "--sealed-predictions", str(output / "sealed_predictions.json"),
                        "--outcome-vault", str(vault_output / "outcome_vault.json"),
                        "--run-report", str(output / "run_report.json"),
                        "--admission-receipt", str(predating_admission),
                        "--run-id", "cli-nightly",
                        "--scored-at", self.run_at.isoformat(),
                        "--output-root", str(root / "predating-holdout-score"),
                    ]
                )

            inconsistent_report = root / "inconsistent-run-report.json"
            inconsistent_payload = dict(receipt)
            inconsistent_payload["run_at"] = "1999-01-01T00:00:00+03:00"
            inconsistent_payload["governed_policy"] = {
                **receipt["governed_policy"],
                "run_id": "different-run",
                "run_at": "2099-01-01T00:00:00+03:00",
            }
            inconsistent_payload["admission"] = {
                **receipt["admission"],
                "execution_contract": inconsistent_payload["governed_policy"],
            }
            inconsistent_report.write_text(
                json.dumps(inconsistent_payload, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            inconsistent_admission = root / "inconsistent-holdout-admission.json"
            write_admission_receipt(
                inconsistent_admission,
                purpose=AdmissionPurpose.HOLDOUT_SCORE,
                artifact_paths={
                    "sealed_predictions": output / "sealed_predictions.json",
                    "outcome_vault": vault_output / "outcome_vault.json",
                    "run_report": inconsistent_report,
                },
                decision_at=self.run_at,
                execution_contract={
                    "scored_at": self.run_at.isoformat(),
                    "run_id": "cli-nightly",
                },
            )
            with self.assertRaisesRegex(ValueError, "run binding mismatch: run_at"):
                holdout_main(
                    [
                        "--sealed-predictions", str(output / "sealed_predictions.json"),
                        "--outcome-vault", str(vault_output / "outcome_vault.json"),
                        "--run-report", str(inconsistent_report),
                        "--admission-receipt", str(inconsistent_admission),
                        "--run-id", "cli-nightly",
                        "--scored-at", self.run_at.isoformat(),
                        "--output-root", str(root / "inconsistent-holdout-score"),
                    ]
                )

            packet_path = output / "sealed_predictions.json"
            original_packet_bytes = packet_path.read_bytes()
            tampered_packet = json.loads(packet_path.read_text(encoding="utf-8"))
            changed_prediction = tampered_packet["predictions"][0]
            changed_prediction["score"] += 10.0
            changed_prediction["direction"] = (
                "UP" if changed_prediction["score"] > 0 else "DOWN"
            )
            unsigned = {
                key: value
                for key, value in tampered_packet.items()
                if key != "seal_sha256"
            }
            tampered_packet["seal_sha256"] = hashlib.sha256(
                json.dumps(
                    unsigned,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            sealed_prediction_packet_from_mapping(tampered_packet)
            packet_path.write_text(
                json.dumps(tampered_packet, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "admission artifact mismatch"):
                holdout_main(
                    [
                        "--sealed-predictions", str(packet_path),
                        "--outcome-vault", str(vault_output / "outcome_vault.json"),
                        "--run-report", str(output / "run_report.json"),
                        "--admission-receipt", str(holdout_admission),
                        "--run-id", "cli-nightly",
                        "--scored-at", self.run_at.isoformat(),
                        "--output-root", str(root / "tampered-holdout-score"),
                    ]
                )

            # A self-consistent vault hash is not an admission signature.  Restore
            # the admitted packet so this case isolates the vault artifact binding.
            packet_path.write_bytes(original_packet_bytes)
            vault_path = vault_output / "outcome_vault.json"
            tampered_vault = json.loads(vault_path.read_text(encoding="utf-8"))
            tampered_vault["entries"][0]["outcomes"][0]["excess_return"] += 0.5
            tampered_vault["vault_sha256"] = hashlib.sha256(
                json.dumps(
                    tampered_vault["entries"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            holdout_outcome_vault_from_mapping(tampered_vault)
            vault_path.write_text(
                json.dumps(tampered_vault, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "admission artifact mismatch"):
                holdout_main(
                    [
                        "--sealed-predictions", str(packet_path),
                        "--outcome-vault", str(vault_path),
                        "--run-report", str(output / "run_report.json"),
                        "--admission-receipt", str(holdout_admission),
                        "--run-id", "cli-nightly",
                        "--scored-at", self.run_at.isoformat(),
                        "--output-root", str(root / "tampered-vault-score"),
                    ]
                )

    def test_nightly_preflights_both_roots_without_orphaning_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            placeholder = root / "placeholder.json"
            placeholder.write_text("{}\n", encoding="utf-8")
            for existing_role in ("model", "vault"):
                with self.subTest(existing_role=existing_role):
                    case_root = root / existing_role
                    case_root.mkdir()
                    model_output = case_root / "model-output"
                    vault_output = case_root / "vault-output"
                    existing = model_output if existing_role == "model" else vault_output
                    absent = vault_output if existing_role == "model" else model_output
                    existing.mkdir()
                    with self.assertRaisesRegex(ValueError, "output root must be absent"):
                        nightly_main(
                            [
                                "--events", str(placeholder),
                                "--identity-file", str(placeholder),
                                "--calendar-file", str(placeholder),
                                "--denominator-report", str(placeholder),
                                "--corporate-actions-report", str(placeholder),
                                "--admission-receipt", str(placeholder),
                                "--output-root", str(model_output),
                                "--outcome-vault-output-root", str(vault_output),
                                "--run-id", "preflight-only",
                                "--run-at", self.run_at.isoformat(),
                            ]
                        )
                    self.assertFalse(absent.exists())

    def test_nightly_rejects_vault_inside_model_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events_path = root / "events.jsonl"
            events_path.write_text(
                "\n".join(json.dumps(event.to_dict()) for event in self.corpus()) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "disjoint roots"):
                nightly_main(
                    [
                        "--events", str(events_path),
                        "--identity-file", str(events_path),
                        "--calendar-file", str(events_path),
                        "--denominator-report", str(events_path),
                        "--corporate-actions-report", str(events_path),
                        "--admission-receipt", str(events_path),
                        "--output-root", str(root / "run"),
                        "--outcome-vault-output-root", str(root / "run" / "vault"),
                        "--run-id", "nested-vault",
                        "--run-at", self.run_at.isoformat(),
                    ]
                )


if __name__ == "__main__":
    unittest.main()
