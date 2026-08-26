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

from kubo.saudi_capabilities.nightly_lab import (
    ALL_HORIZONS,
    Cohort,
    EventType,
    FactorObservation,
    HistoricalEvent,
    OutcomeObservation,
    evaluate_sealed_holdout,
    prepare_nightly_run,
)
from kubo.saudi_nightly_cli import main as nightly_main


class NightlyLabTests(unittest.TestCase):
    timezone = ZoneInfo("Asia/Riyadh")
    run_at = datetime(2026, 8, 25, 22, 0, tzinfo=timezone)
    base = datetime(2016, 9, 1, 10, 0, tzinfo=timezone)

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
        primary = tuple(
            self.event(index, Cohort.PRIMARY, index * 45) for index in range(50)
        )
        probe = tuple(
            self.event(index + 50, Cohort.PROBE, index * 7) for index in range(300)
        )
        return primary + probe

    def test_minimum_gate_stops_without_updating_a_model(self):
        prepared = prepare_nightly_run(
            (self.event(1, Cohort.PRIMARY, 1), self.event(2, Cohort.PROBE, 2)),
            run_id="small",
            run_at=self.run_at,
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

    def test_temporal_fit_is_deterministic_and_holdout_is_blinded(self):
        first = prepare_nightly_run(
            self.corpus(), run_id="nightly-1", run_at=self.run_at
        )
        second = prepare_nightly_run(
            reversed(self.corpus()), run_id="nightly-1", run_at=self.run_at
        )
        self.assertEqual(first.status, "SEALED_AWAITING_FINAL_SCORE")
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

        report = evaluate_sealed_holdout(
            first.sealed_packet,
            first.split.outcome_vault,
            scored_at=self.run_at,
        )
        self.assertEqual(report["status"], "FINAL_HOLDOUT_SCORED")
        self.assertIsNone(report["recommendation"])
        self.assertEqual(set(report["metrics"]), {item.value for item in ALL_HORIZONS})

    def test_tampering_after_seal_is_detected(self):
        prepared = prepare_nightly_run(
            self.corpus(), run_id="nightly-tamper", run_at=self.run_at
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
            with redirect_stdout(StringIO()):
                code = nightly_main(
                    [
                        "--events", str(events_path),
                        "--output-root", str(output),
                        "--run-id", "cli-nightly",
                        "--run-at", self.run_at.isoformat(),
                    ]
                )
            self.assertEqual(code, 0)
            weights = json.loads((output / "horizon_weights.json").read_text(encoding="utf-8"))
            self.assertEqual(set(weights), {horizon.value for horizon in ALL_HORIZONS})
            self.assertTrue((output / "sealed_predictions.json").is_file())
            self.assertTrue((output / "final_holdout_report.json").is_file())


if __name__ == "__main__":
    unittest.main()
