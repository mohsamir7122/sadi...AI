from __future__ import annotations

import argparse
import copy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

import kubo.markets.saudi.calendar as calendar_module
from kubo.saudi_capabilities.factor9 import FactorDefinition, FactorRegistry, FactorStatus
from kubo.saudi_capabilities.audit import Claim, AuditStatus, audit_claims
from kubo.saudi_capabilities.workflows import (
    Checkpoint,
    PortfolioPosition,
    ResumeLedger,
    SaudiObservation,
    SaudiOpportunityScanner,
    SaudiPortfolioValidator,
    SaudiResearchRequest,
)
from kubo.markets.saudi import SaudiSecurityMaster, SaudiSecurityRecord, SaudiTradingCalendar
from kubo.markets.saudi.calendar import (
    CALENDAR_COVERAGE_MISSING,
    CALENDAR_REVISION_NOT_KNOWN,
    calendar_revision_from_mapping,
)
from kubo.markets.saudi.identity import saudi_security_record_from_mapping
from kubo.markets.saudi.benchmarks import SaudiBenchmarkRegistry
from kubo.markets.saudi.config import MAIN_MARKET, NOMU, NOMUC, SAUDI_MARKET, TASI
from kubo.markets.saudi.engine import SaudiResearchEngine
from kubo.saudi_cli import _parse_date, main as saudi_main
from contextlib import redirect_stdout
from io import StringIO
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from tests.saudi.helpers import identity_payload, synthetic_calendar_payload


class SaudiFoundationTests(unittest.TestCase):
    known_at = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)

    def calendar(self, **overrides):
        payload = synthetic_calendar_payload(**overrides)
        return SaudiTradingCalendar(
            revision=calendar_revision_from_mapping(payload, known_at=self.known_at)
        )

    def security(self, code="2222", **overrides):
        values = dict(
            security_id=f"sec-{code}", official_code=code, isin="SA0007879162",
            symbol_en="ACME", symbol_ar="أكمي", issuer_id="issuer-acme",
            segment=MAIN_MARKET, instrument_type="ORDINARY_EQUITY",
            valid_from=date(2026, 1, 1), valid_to=None,
            known_from=datetime(2026, 1, 1, tzinfo=timezone.utc), known_to=None,
            tradable=True,
        )
        values.update(overrides)
        return SaudiSecurityRecord(**values)

    def test_calendar_is_riyadh_and_weekend_is_closed(self):
        calendar = self.calendar(
            closed_from=date(2026, 9, 23),
            resume_on=date(2026, 9, 24),
        )
        session = calendar.session_for(date(2026, 8, 25), known_at=self.known_at)
        self.assertTrue(session.is_trading_day)
        self.assertEqual(session.phases[0].start.hour, 9)
        self.assertEqual(session.phases[-1].end.hour, 15)
        self.assertFalse(
            calendar.session_for(date(2026, 8, 28), known_at=self.known_at).is_trading_day
        )
        holiday = calendar.session_for(
            date(2026, 9, 23), known_at=self.known_at
        )
        self.assertEqual(holiday.closed_reason, "SYNTHETIC_CLOSURE")
        self.assertEqual(holiday.resume_on, date(2026, 9, 24))
        self.assertEqual(
            calendar.next_session(date(2026, 9, 22), known_at=self.known_at).session_date,
            date(2026, 9, 24),
        )
        unknown = SaudiTradingCalendar().session_for(
            date(2026, 8, 25), known_at=self.known_at
        )
        self.assertFalse(unknown.is_trading_day)
        self.assertEqual(unknown.closed_reason, CALENDAR_COVERAGE_MISSING)
        with self.assertRaisesRegex(RuntimeError, "no representable"):
            calendar.next_session(date.max, known_at=self.known_at)

    def test_calendar_fixture_and_schema_share_the_runtime_contract(self):
        schema = json.loads(
            (
                Path(__file__).parents[2]
                / "schemas"
                / "saudi-calendar-revision.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        checker = FormatChecker()
        self.assertIn("date-time", checker.checkers)
        self.assertIn("uri", checker.checkers)
        validator = Draft202012Validator(schema, format_checker=checker)
        validator.validate(synthetic_calendar_payload())

        for field, invalid in (
            ("known_from", "not-a-timestamp"),
            ("known_from", "2026-02-30T00:00:00+03:00"),
            ("source_url", "https:// bad-host.example/path"),
            ("source_url", "https://example.com/%zz"),
            ("source_url", "https://example.com/has|pipe"),
            ("source_url", "https://user@example.com/path"),
            ("source_url", "https://مثال.إختبار/path"),
            ("source_url", "HTTPS://example.com/path"),
        ):
            with self.subTest(field=field, invalid=invalid):
                payload = synthetic_calendar_payload()
                payload[field] = invalid
                with self.assertRaises(ValidationError):
                    validator.validate(payload)

    def test_calendar_schedule_is_revision_bound_immutable_and_point_in_time(self):
        payload = synthetic_calendar_payload()
        payload["schedule"]["phases"][0]["start"] = "09:31:00"
        payload["known_to"] = "2026-08-26T00:00:00+00:00"
        revision = calendar_revision_from_mapping(payload, known_at=self.known_at)
        calendar = SaudiTradingCalendar(revision=revision)

        session = calendar.session_for(date(2026, 8, 25), known_at=self.known_at)
        self.assertEqual(session.phases[0].start.minute, 31)
        with self.assertRaises(TypeError):
            revision.holidays[date(2026, 8, 25)] = "MUTATED"
        with self.assertRaisesRegex(TypeError, "governed parser"):
            replace(revision, holiday_closures=())
        forged = replace(
            revision,
            holiday_closures=(),
            _construction_marker=calendar_module._CALENDAR_REVISION_CONSTRUCTION_MARKER,
        )
        with self.assertRaisesRegex(TypeError, "registered parser result"):
            SaudiTradingCalendar(revision=forged)
        with self.assertRaisesRegex(TypeError, "registered parser result"):
            SaudiTradingCalendar(revision=copy.copy(revision))

        tampered = calendar_revision_from_mapping(
            synthetic_calendar_payload(
                closed_from=date(2026, 9, 23),
                resume_on=date(2026, 9, 24),
            ),
            known_at=self.known_at,
        )
        tampered_calendar = SaudiTradingCalendar(revision=tampered)
        object.__setattr__(tampered, "holiday_closures", ())
        with self.assertRaisesRegex(TypeError, "structure changed"):
            tampered_calendar.session_for(
                date(2026, 8, 25), known_at=self.known_at
            )

        after_expiry = calendar.session_for(
            date(2026, 8, 26),
            known_at=datetime(2026, 8, 26, 1, tzinfo=timezone.utc),
        )
        self.assertFalse(after_expiry.is_trading_day)
        self.assertEqual(after_expiry.closed_reason, CALENDAR_REVISION_NOT_KNOWN)
        self.assertIsNone(after_expiry.calendar_revision_id)
        self.assertEqual(after_expiry.source_id, "UNAVAILABLE_AT_CUTOFF")

        outside_weekend = calendar.session_for(
            date(2027, 1, 1), known_at=self.known_at
        )
        self.assertEqual(outside_weekend.closed_reason, CALENDAR_COVERAGE_MISSING)
        self.assertFalse(outside_weekend.coverage_known)

    def test_calendar_rejects_inconsistent_resume_and_phase_templates(self):
        payload = synthetic_calendar_payload(
            closed_from=date(2026, 9, 23),
            resume_on=date(2026, 9, 25),
        )
        with self.assertRaisesRegex(ValueError, "resume_on"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

        payload = synthetic_calendar_payload()
        payload["schedule"]["phases"][1]["name"] = "UNVERSIONED_PHASE"
        with self.assertRaisesRegex(ValueError, "template mismatch"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

        payload = synthetic_calendar_payload()
        payload["coverage_from"] = "2026-W01-1"
        with self.assertRaisesRegex(ValueError, "ISO date"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

        for invalid_url in (
            "https:// bad host",
            "https:///missing-host",
            "https://x y/z",
            "https://example.com/%zz",
            "https://example.com\\evil",
            "https://example.com/has|pipe",
            "https://user@example.com/path",
            "https://مثال.إختبار/path",
            "HTTPS://example.com/path",
        ):
            with self.subTest(invalid_url=invalid_url):
                payload = synthetic_calendar_payload()
                payload["source_url"] = invalid_url
                with self.assertRaisesRegex(ValueError, "valid HTTPS URL"):
                    calendar_revision_from_mapping(payload, known_at=self.known_at)

        payload = synthetic_calendar_payload()
        payload["boundary_uncertainty_seconds"] = 301
        with self.assertRaisesRegex(ValueError, "between 0 and 300"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

        for invalid_time in ("09300000", "09:30,00", "09:30.00"):
            with self.subTest(invalid_time=invalid_time):
                payload = synthetic_calendar_payload()
                payload["schedule"]["phases"][0]["start"] = invalid_time
                with self.assertRaisesRegex(ValueError, "HH:MM:SS"):
                    calendar_revision_from_mapping(payload, known_at=self.known_at)

        payload = synthetic_calendar_payload()
        payload["coverage_from"] = "2013-06-29"
        payload["coverage_through"] = "9999-12-31"
        with self.assertRaisesRegex(ValueError, "maximum span"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

        payload = synthetic_calendar_payload()
        payload["coverage_from"] = "2013-06-28"
        with self.assertRaisesRegex(ValueError, "supported Friday/Saturday"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

        payload = synthetic_calendar_payload()
        payload["known_from"] = "0001-01-01T00:00:00+14:00"
        with self.assertRaisesRegex(ValueError, "supported UTC range"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

        payload = synthetic_calendar_payload()
        payload["holidays"] = [
            {
                "closed_from": "2026-01-01",
                "closed_through": "2026-03-05",
                "resume_on": "2026-03-08",
                "reason": "OVERSIZED_SYNTHETIC_CLOSURE",
            }
        ]
        with self.assertRaisesRegex(ValueError, "closure exceeds"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

        payload = synthetic_calendar_payload()
        payload["holidays"] = [
            {
                "closed_from": "2026-08-25",
                "closed_through": "2026-08-25",
                "resume_on": "2026-08-26",
                "reason": "SYNTHETIC_CLOSURE",
            }
        ] * 513
        with self.assertRaisesRegex(ValueError, "maximum count"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

        payload = synthetic_calendar_payload()
        payload["coverage_from"] = "9999-12-01"
        payload["coverage_through"] = "9999-12-31"
        payload["schedule"]["effective_from"] = "9999-12-01"
        payload["schedule"]["effective_through"] = "9999-12-31"
        payload["holidays"] = [
            {
                "closed_from": "9999-12-31",
                "closed_through": "9999-12-31",
                "resume_on": "9999-12-31",
                "reason": "DATE_MAX",
            }
        ]
        with self.assertRaisesRegex(ValueError, "no representable resume"):
            calendar_revision_from_mapping(payload, known_at=self.known_at)

    def test_identity_requires_official_code_and_point_in_time(self):
        master = SaudiSecurityMaster([self.security()])
        self.assertEqual(master.resolve("2222", as_of=date(2026, 8, 25), known_at=self.known_at).isin, "SA0007879162")
        self.assertEqual(master.members_on(as_of=date(2025, 12, 31), known_at=self.known_at), ())
        with self.assertRaisesRegex(ValueError, "checksum-valid"):
            SaudiSecurityRecord(
                **{**self.security().__dict__, "isin": "SA1234567890"}
            )
        extreme = self.security(
            known_from=datetime.min.replace(tzinfo=timezone(timedelta(hours=14)))
        )
        with self.assertRaisesRegex(ValueError, "supported UTC range"):
            extreme.is_valid(as_of=date(2026, 8, 25), known_at=self.known_at)

    def test_identity_knowledge_compares_absolute_instants_across_dst_fold(self):
        new_york = ZoneInfo("America/New_York")
        known_from = datetime(2026, 11, 1, 1, 30, tzinfo=new_york, fold=1)
        earlier_absolute_cutoff = datetime(
            2026, 11, 1, 1, 45, tzinfo=new_york, fold=0
        )
        record = self.security(known_from=known_from)
        self.assertFalse(
            record.is_valid(
                as_of=date(2026, 11, 1),
                known_at=earlier_absolute_cutoff,
            )
        )

    def test_membership_keeps_suspended_rows_but_selectability_does_not(self):
        suspended = self.security()
        suspended = SaudiSecurityRecord(**{**suspended.__dict__, "tradable": False})
        master = SaudiSecurityMaster([suspended])
        self.assertEqual(len(master.membership_on(as_of=date(2026, 8, 25), known_at=self.known_at)), 1)
        self.assertEqual(master.selectable_on(as_of=date(2026, 8, 25), known_at=self.known_at), ())
        self.assertEqual(master.members_on(as_of=date(2026, 8, 25), known_at=self.known_at), ())
        self.assertEqual(
            len(master.as_rows(as_of=date(2026, 8, 25), known_at=self.known_at)),
            1,
        )

    def test_reit_is_not_in_the_selectable_main_market_universe(self):
        reit = SaudiSecurityRecord(**{**self.security().__dict__, "instrument_type": "REIT"})
        master = SaudiSecurityMaster([reit])
        self.assertEqual(len(master.membership_on(as_of=date(2026, 8, 25), known_at=self.known_at)), 1)
        self.assertEqual(master.selectable_on(as_of=date(2026, 8, 25), known_at=self.known_at), ())

    def test_identity_corrections_use_half_open_knowledge_and_unique_pit_keys(self):
        cutoff = datetime(2026, 8, 25, 9, tzinfo=timezone.utc)
        old = self.security(known_to=cutoff, symbol_en="OLD")
        corrected = self.security(known_from=cutoff, symbol_en="CORRECTED")
        master = SaudiSecurityMaster([old, corrected])
        self.assertEqual(
            master.resolve_member(
                "2222", as_of=date(2026, 8, 25), known_at=cutoff
            ).symbol_en,
            "CORRECTED",
        )

        duplicate_isin = self.security(
            "3333",
            security_id="sec-3333",
            isin=corrected.isin,
        )
        with self.assertRaisesRegex(ValueError, "ISIN"):
            SaudiSecurityMaster([corrected, duplicate_isin])

    def test_identity_mapping_rejects_schema_type_coercion(self):
        payload = identity_payload("2222")
        payload["official_code"] = 2222
        with self.assertRaisesRegex(ValueError, "official_code"):
            saudi_security_record_from_mapping(payload)

        payload = identity_payload("2222")
        payload["valid_from"] = "2016-W01-1"
        with self.assertRaisesRegex(ValueError, "ISO date"):
            saudi_security_record_from_mapping(payload)

        with self.assertRaisesRegex(ValueError, "known_from"):
            self.security(known_from=None)

    def test_nomu_is_explicit_and_not_default(self):
        self.assertEqual(SAUDI_MARKET.default_segment, MAIN_MARKET)
        self.assertNotEqual(SAUDI_MARKET.default_segment, NOMU)
        self.assertEqual(SaudiBenchmarkRegistry().get(TASI, as_of=date(2026, 8, 25)).currency, "SAR")

    def test_engine_abstains_without_admitted_evidence(self):
        engine = SaudiResearchEngine(
            security_master=SaudiSecurityMaster([self.security()]),
            calendar=self.calendar(),
        )
        snapshot = engine.snapshot(as_of=date(2026, 8, 25), known_at=self.known_at)
        self.assertEqual(snapshot["status"], "READY_FOR_EVIDENCE")
        self.assertEqual(snapshot["currency"], "SAR")
        self.assertEqual(snapshot["timezone"], "Asia/Riyadh")
        wrong_benchmark = engine.snapshot(
            as_of=date(2026, 8, 25),
            known_at=self.known_at,
            benchmark_code=NOMUC,
        )
        self.assertEqual(wrong_benchmark["status"], "ABSTAIN")
        self.assertIn("BENCHMARK_SCOPE_MISMATCH", wrong_benchmark["blocked_reasons"])

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

    def test_structural_portfolio_and_resume_contracts_are_bounded(self):
        validator = SaudiPortfolioValidator()
        valid = validator.validate(
            currency="SAR",
            positions=(PortfolioPosition("2222", 10.0, 25.0),),
            as_of=date(2026, 8, 25),
            known_at=self.known_at,
        )
        self.assertEqual(valid["status"], "READY")
        self.assertIn("no execution", valid["claim_boundary"].lower())
        blocked = validator.validate(
            currency="KWD",
            positions=(PortfolioPosition("2222", -1.0, 25.0),),
            as_of=date(2026, 8, 25),
            known_at=self.known_at,
        )
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertEqual(
            blocked["errors"],
            ["CURRENCY_MUST_BE_SAR", "NEGATIVE_POSITION_VALUE"],
        )

        ledger = ResumeLedger()
        first = Checkpoint(
            run_id="synthetic-resume",
            step="DISCOVERY",
            state="DONE",
            updated_at=self.known_at,
        )
        ledger.append(first)
        self.assertIs(ledger.latest("synthetic-resume"), first)
        with self.assertRaisesRegex(ValueError, "already exists"):
            ledger.append(first)
        with self.assertRaisesRegex(ValueError, "monotonic"):
            ledger.append(
                Checkpoint(
                    run_id="synthetic-resume",
                    step="NORMALIZE",
                    state="DONE",
                    updated_at=self.known_at - timedelta(seconds=1),
                )
            )
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
        with self.assertRaisesRegex(argparse.ArgumentTypeError, "canonical YYYY-MM-DD"):
            _parse_date("2026-W35-2")


if __name__ == "__main__":
    unittest.main()
