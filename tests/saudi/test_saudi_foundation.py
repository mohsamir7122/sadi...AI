from __future__ import annotations

from datetime import date, datetime, timezone
import unittest

from kubo.saudi_capabilities.factor9 import FactorDefinition, FactorRegistry, FactorStatus
from kubo.saudi_capabilities.audit import Claim, AuditStatus, audit_claims
from kubo.saudi_capabilities.workflows import SaudiObservation, SaudiOpportunityScanner, SaudiResearchRequest
from kubo.markets.saudi import SaudiSecurityMaster, SaudiSecurityRecord, SaudiTradingCalendar
from kubo.markets.saudi.benchmarks import SaudiBenchmarkRegistry
from kubo.markets.saudi.config import MAIN_MARKET, NOMU, SAUDI_MARKET, TASI
from kubo.markets.saudi.engine import SaudiResearchEngine
from kubo.saudi_cli import main as saudi_main
from contextlib import redirect_stdout
from io import StringIO


class SaudiFoundationTests(unittest.TestCase):
    known_at = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)

    def security(self, code="2222"):
        return SaudiSecurityRecord(
            security_id="sec-2222", official_code=code, isin="SA1234567890",
            symbol_en="ACME", symbol_ar="أكمي", issuer_id="issuer-acme",
            segment=MAIN_MARKET, instrument_type="ORDINARY_EQUITY",
            valid_from=date(2026, 1, 1), valid_to=None,
            known_from=datetime(2026, 1, 1, tzinfo=timezone.utc), known_to=None,
            tradable=True,
        )

    def test_calendar_is_riyadh_and_weekend_is_closed(self):
        calendar = SaudiTradingCalendar(holidays={date(2026, 9, 23): "NATIONAL_DAY"})
        session = calendar.session_for(date(2026, 8, 25))
        self.assertTrue(session.is_trading_day)
        self.assertEqual(session.phases[0].start.hour, 9)
        self.assertEqual(session.phases[-1].end.hour, 15)
        self.assertFalse(calendar.session_for(date(2026, 8, 28)).is_trading_day)
        self.assertEqual(calendar.session_for(date(2026, 9, 23)).closed_reason, "NATIONAL_DAY")

    def test_identity_requires_official_code_and_point_in_time(self):
        master = SaudiSecurityMaster([self.security()])
        self.assertEqual(master.resolve("2222", as_of=date(2026, 8, 25), known_at=self.known_at).isin, "SA1234567890")
        self.assertEqual(master.members_on(as_of=date(2025, 12, 31), known_at=self.known_at), ())

    def test_nomu_is_explicit_and_not_default(self):
        self.assertEqual(SAUDI_MARKET.default_segment, MAIN_MARKET)
        self.assertNotEqual(SAUDI_MARKET.default_segment, NOMU)
        self.assertEqual(SaudiBenchmarkRegistry().get(TASI, as_of=date(2026, 8, 25)).currency, "SAR")

    def test_engine_abstains_without_admitted_evidence(self):
        engine = SaudiResearchEngine(security_master=SaudiSecurityMaster([self.security()]))
        snapshot = engine.snapshot(as_of=date(2026, 8, 25), known_at=self.known_at)
        self.assertEqual(snapshot["status"], "READY_FOR_EVIDENCE")
        self.assertEqual(snapshot["currency"], "SAR")
        self.assertEqual(snapshot["timezone"], "Asia/Riyadh")

    def test_factor9_admission_is_fail_closed(self):
        registry = FactorRegistry((FactorDefinition(
            factor_id="F9-earnings-quality", name="Earnings quality", direction="POSITIVE",
            data_role="FEATURE", source_ids=("saudi_exchange_ereference",),
            available_from=datetime(2026, 1, 1, tzinfo=timezone.utc), freshness_hours=24,
            rights_status="PUBLIC_RESEARCH_ALLOWED", point_in_time_tested=False,
        ),))
        with self.assertRaisesRegex(ValueError, "POINT_IN_TIME_UNTESTED"):
            registry.admit("F9-earnings-quality", known_at=self.known_at)

    def test_scanner_rejects_context_sources_and_accepts_official_leads(self):
        master = SaudiSecurityMaster([self.security()])
        request = SaudiResearchRequest(as_of=date(2026, 8, 25), known_at=self.known_at)
        scanner = SaudiOpportunityScanner(master)
        result = scanner.scan([
            SaudiObservation("2222", self.known_at, "saudi_exchange_ereference", "END_OF_DAY", 100.0, 10.0, "OFFICIAL_VERIFICATION"),
            SaudiObservation("2222", self.known_at, "community", "DELAYED", 101.0, 11.0, "SOCIAL_CONTEXT_LEAD_ONLY"),
        ], request=request)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(len(result["leads"]), 1)
        self.assertEqual(len(result["rejected"]), 1)

    def test_audit_stops_when_denominator_or_authority_is_missing(self):
        result = audit_claims([Claim("c1", "BACKTEST", 1, False, True, True, False)])
        self.assertEqual(result["status"], AuditStatus.STOP_BACKTEST.value)
        self.assertIsNone(result["metrics"])
        self.assertFalse(result["accuracy_claim_allowed"])

    def test_cli_is_explicitly_point_in_time_and_fail_closed_without_identity(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(saudi_main(["--as-of", "2026-08-25", "--known-at", "2026-08-25T12:00:00+00:00"]), 0)
        self.assertIn('"status": "ABSTAIN"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
