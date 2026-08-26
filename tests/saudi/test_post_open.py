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
from kubo.saudi_capabilities.post_open import PostOpenObservation, SaudiPostOpenScanner
from kubo.saudi_post_open_cli import main as post_open_main


class PostOpenScannerTests(unittest.TestCase):
    timezone = ZoneInfo("Asia/Riyadh")
    scan_at = datetime(2026, 8, 25, 10, 30, tzinfo=timezone)

    def weights(self):
        return {horizon: {"F9-governed-signal": 1.0} for horizon in ALL_HORIZONS}

    def observation(self, code="2222"):
        known_at = self.scan_at - timedelta(minutes=5)
        return PostOpenObservation(
            official_code=code,
            observed_at=known_at,
            source_id="licensed-saudi-market-feed",
            source_role="LICENSED_MARKET_DATA",
            rights_status="LICENSED_RESEARCH_ALLOWED",
            latency_class="DELAYED",
            last_price_sar=123.4,
            average_daily_turnover_sar=5_000_000.0,
            identity_verified=True,
            factors=(
                FactorObservation(
                    factor_id="F9-governed-signal",
                    value=0.75,
                    known_at=known_at,
                    source_id="licensed-saudi-market-feed",
                    rights_status="LICENSED_RESEARCH_ALLOWED",
                ),
            ),
        )

    def test_scan_abstains_before_open_plus_thirty_minutes(self):
        report = SaudiPostOpenScanner().scan(
            (self.observation(),),
            scan_at=self.scan_at - timedelta(minutes=1),
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["reason"], "SCAN_BEFORE_OPEN_PLUS_30_MINUTES")

    def test_scan_emits_five_research_horizons_without_trade_advice(self):
        report = SaudiPostOpenScanner().scan(
            (self.observation("2222"), self.observation("1111")),
            scan_at=self.scan_at,
            horizon_weights=self.weights(),
        )
        self.assertEqual(report["status"], "RESEARCH_CANDIDATES_READY")
        self.assertEqual(
            set(report["candidates_by_horizon"]),
            {horizon.value for horizon in ALL_HORIZONS},
        )
        for rows in report["candidates_by_horizon"].values():
            self.assertEqual(rows[0]["research_status"], "RESEARCH_CANDIDATE")
            self.assertIsNone(rows[0]["recommendation"])
            self.assertIsNone(rows[0]["order"])
            self.assertIsNone(rows[0]["probability"])

    def test_stale_or_end_of_day_market_rows_are_rejected(self):
        stale = replace(
            self.observation(),
            observed_at=self.scan_at - timedelta(minutes=16),
        )
        report = SaudiPostOpenScanner().scan(
            (stale,), scan_at=self.scan_at, horizon_weights=self.weights()
        )
        self.assertEqual(report["status"], "ABSTAIN")
        self.assertEqual(report["rejected"][0]["reason"], "STALE_MARKET_OBSERVATION")

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
            with redirect_stdout(StringIO()):
                code = post_open_main(
                    [
                        "--observations", str(observations),
                        "--weights", str(weights),
                        "--scan-at", self.scan_at.isoformat(),
                        "--output-root", str(output),
                    ]
                )
            self.assertEqual(code, 0)
            report = json.loads((output / "post_open_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "RESEARCH_CANDIDATES_READY")


if __name__ == "__main__":
    unittest.main()
