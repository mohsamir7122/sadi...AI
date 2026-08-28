from __future__ import annotations

import copy
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import pickle
import tempfile
import unittest
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator, FormatChecker

from kubo.saudi_admission import (
    BUILTIN_ADMISSION_TRUST_STORE,
    SYNTHETIC_ADMISSION_KEY_ID,
    SYNTHETIC_ADMISSION_TRUST_CLASS,
    AdmissionPurpose,
    SaudiAdmissionError,
    VerifiedSaudiAdmission,
    canonical_admission_bytes,
    require_verified_saudi_admission,
    verify_saudi_admission_receipt,
)
import kubo.saudi_admission as admission_module
from tests.saudi.helpers import (
    SYNTHETIC_ADMISSION_PRIVATE_SEED,
    write_admission_receipt,
)


class SaudiAdmissionTests(unittest.TestCase):
    decision_at = datetime(2026, 8, 25, 22, 0, tzinfo=ZoneInfo("Asia/Riyadh"))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.paths = {
            "input": self.root / "events.jsonl",
            "identity": self.root / "identity.json",
            "calendar": self.root / "calendar.json",
            "denominator_report": self.root / "denominator.json",
            "corporate_actions_report": self.root / "corporate-actions.json",
        }
        for role, path in self.paths.items():
            path.write_text(
                json.dumps({"role": role, "synthetic": True}, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        self.execution_contract = {
            "run_id": "synthetic-admission-run",
            "run_at": self.decision_at.isoformat(),
            "lookback_years": 10,
            "minimum_primary": 50,
            "minimum_probe": 300,
            "coverage_tolerance_days": 31,
            "maturity_buffer_days": 370,
            "maximum_coverage_gap_days": 396,
        }
        self.receipt = self.root / "admission.json"
        write_admission_receipt(
            self.receipt,
            purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
            artifact_paths=self.paths,
            decision_at=self.decision_at,
            execution_contract=self.execution_contract,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self, **overrides):
        arguments = {
            "purpose": AdmissionPurpose.NIGHTLY_MODEL_USE,
            "artifact_paths": self.paths,
            "decision_at": self.decision_at,
            "expected_execution_contract": self.execution_contract,
        }
        arguments.update(overrides)
        return verify_saudi_admission_receipt(self.receipt, **arguments)

    def resign(self, payload: dict[str, object]) -> None:
        authentication = payload["authentication"]
        if not isinstance(authentication, dict):
            raise AssertionError("test authentication must be a dictionary")
        authentication["signature"] = "0" * 128
        private_key = Ed25519PrivateKey.from_private_bytes(
            SYNTHETIC_ADMISSION_PRIVATE_SEED
        )
        authentication["signature"] = private_key.sign(
            canonical_admission_bytes(payload)
        ).hex()
        self.receipt.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_valid_receipt_uses_pinned_synthetic_public_trust(self):
        verified = self.verify()
        self.assertEqual(verified.purpose, AdmissionPurpose.NIGHTLY_MODEL_USE)
        self.assertEqual(verified.authenticated_key_id, SYNTHETIC_ADMISSION_KEY_ID)
        self.assertEqual(verified.trust_class, SYNTHETIC_ADMISSION_TRUST_CLASS)
        self.assertEqual(
            set(verified.artifact_sha256),
            {
                "input",
                "identity",
                "calendar",
                "denominator_report",
                "corporate_actions_report",
            },
        )
        self.assertEqual(
            set(BUILTIN_ADMISSION_TRUST_STORE), {SYNTHETIC_ADMISSION_KEY_ID}
        )
        self.assertFalse(verified.to_dict()["receipt_is_market_evidence"])
        self.assertEqual(
            verified.to_dict()["market_evidence_trust_class"],
            SYNTHETIC_ADMISSION_TRUST_CLASS,
        )
        with self.assertRaises(TypeError):
            verified.execution_contract["minimum_primary"] = 1  # type: ignore[index]
        with self.assertRaises(TypeError):
            verified.artifact_sha256["input"] = "0" * 64  # type: ignore[index]
        with self.assertRaises(TypeError):
            verified.assertions["denominator_complete"] = False  # type: ignore[index]

    def test_receipt_matches_json_schema(self):
        schema = json.loads(
            (Path(__file__).parents[2] / "schemas" / "saudi-admission-receipt.schema.json")
            .read_text(encoding="utf-8")
        )
        payload = json.loads(self.receipt.read_text(encoding="utf-8"))
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(payload)

    def test_tampered_artifact_signature_and_expiry_fail_closed(self):
        original = self.paths["input"].read_text(encoding="utf-8")
        self.paths["input"].write_text('{"tampered":true}\n', encoding="utf-8")
        with self.assertRaisesRegex(SaudiAdmissionError, "artifact mismatch"):
            self.verify()
        self.paths["input"].write_text(original, encoding="utf-8")

        payload = json.loads(self.receipt.read_text(encoding="utf-8"))
        signature = payload["authentication"]["signature"]
        payload["authentication"]["signature"] = (
            ("0" if signature[0] != "0" else "1") + signature[1:]
        )
        self.receipt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(SaudiAdmissionError, "authentication failed"):
            self.verify()

        write_admission_receipt(
            self.receipt,
            purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
            artifact_paths=self.paths,
            decision_at=self.decision_at,
            execution_contract=self.execution_contract,
        )
        with self.assertRaisesRegex(SaudiAdmissionError, "not valid"):
            self.verify(decision_at=self.decision_at.replace(day=27))

    def test_caller_cannot_supply_a_verifier_key(self):
        with self.assertRaises(TypeError):
            self.verify(key=b"caller-selected-key-is-forbidden")
        with self.assertRaises(TypeError):
            self.verify(expected_key_id="caller-selected-key")

    def test_verified_capability_boundary_rejects_forged_copy_and_subclass(self):
        verified = self.verify()
        self.assertIs(
            require_verified_saudi_admission(
                verified, purpose=AdmissionPurpose.NIGHTLY_MODEL_USE
            ),
            verified,
        )
        values = {
            field: getattr(verified, field)
            for field in (
                "receipt_id",
                "purpose",
                "trust_class",
                "issued_at",
                "expires_at",
                "authenticated_key_id",
                "content_sha256",
                "execution_contract",
                "artifact_sha256",
                "assertions",
                "artifact_bytes",
            )
        }
        with self.assertRaisesRegex(TypeError, "must come from one receipt verification"):
            VerifiedSaudiAdmission(**values, _construction_marker=object())
        forged = VerifiedSaudiAdmission(
            **values,
            _construction_marker=admission_module._VerifiedConstructionMarker(),
        )
        with self.assertRaisesRegex(SaudiAdmissionError, "exact result"):
            require_verified_saudi_admission(
                forged, purpose=AdmissionPurpose.NIGHTLY_MODEL_USE
            )
        with self.assertRaisesRegex(TypeError, "cannot be subclassed"):
            class ForgedAdmission(VerifiedSaudiAdmission):
                pass
        with self.assertRaisesRegex(TypeError, "cannot be replaced"):
            replace(verified, purpose=AdmissionPurpose.HOLDOUT_SCORE)
        with self.assertRaisesRegex(TypeError, "cannot be replaced"):
            replace(verified, artifact_bytes={})
        with self.assertRaisesRegex(TypeError, "cannot be copied"):
            copy.copy(verified)
        with self.assertRaisesRegex(TypeError, "cannot be copied"):
            copy.deepcopy(verified)
        with self.assertRaisesRegex(TypeError, "cannot be serialized"):
            pickle.dumps(verified)

    def test_unknown_key_id_and_non_string_identifier_fail_closed(self):
        payload = json.loads(self.receipt.read_text(encoding="utf-8"))
        payload["authentication"]["key_id"] = "untrusted-ed25519-key"
        self.resign(payload)
        with self.assertRaisesRegex(SaudiAdmissionError, "not trusted"):
            self.verify()

        payload = json.loads(self.receipt.read_text(encoding="utf-8"))
        payload["authentication"]["key_id"] = SYNTHETIC_ADMISSION_KEY_ID
        payload["receipt_id"] = 123
        self.resign(payload)
        with self.assertRaisesRegex(SaudiAdmissionError, "receipt_id is invalid"):
            self.verify()

    def test_execution_contract_is_exact_and_rejects_boolean_numbers(self):
        changed = dict(self.execution_contract)
        changed["minimum_primary"] = 49
        with self.assertRaisesRegex(SaudiAdmissionError, "execution_contract mismatch"):
            self.verify(expected_execution_contract=changed)

        invalid = dict(self.execution_contract)
        invalid["minimum_primary"] = True
        write_admission_receipt(
            self.receipt,
            purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
            artifact_paths=self.paths,
            decision_at=self.decision_at,
            execution_contract=invalid,
        )
        with self.assertRaisesRegex(SaudiAdmissionError, "positive integer"):
            self.verify(expected_execution_contract=invalid)

        post_paths = {
            role: self.root / f"post-{role}.json"
            for role in ("input", "identity", "calendar", "weights")
        }
        for role, path in post_paths.items():
            path.write_text(json.dumps({"role": role}) + "\n", encoding="utf-8")
        post_contract = {
            "scan_at": self.decision_at.isoformat(),
            "maximum_market_age_minutes": 16,
            "minimum_turnover_sar": 0.0,
            "maximum_candidates_per_horizon": 25,
        }
        write_admission_receipt(
            self.receipt,
            purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
            artifact_paths=post_paths,
            decision_at=self.decision_at,
            execution_contract=post_contract,
        )
        with self.assertRaisesRegex(SaudiAdmissionError, "governed maximum"):
            verify_saudi_admission_receipt(
                self.receipt,
                purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
                artifact_paths=post_paths,
                decision_at=self.decision_at,
                expected_execution_contract=post_contract,
            )

    def test_purpose_and_artifact_role_mismatch_fail_closed(self):
        weights = self.root / "weights.json"
        weights.write_text("{}\n", encoding="utf-8")
        post_open_paths = {
            "input": self.paths["input"],
            "identity": self.paths["identity"],
            "calendar": self.paths["calendar"],
            "weights": weights,
        }
        with self.assertRaisesRegex(SaudiAdmissionError, "purpose mismatch"):
            self.verify(
                purpose=AdmissionPurpose.POST_OPEN_MODEL_USE,
                artifact_paths=post_open_paths,
                expected_execution_contract={
                    "scan_at": self.decision_at.isoformat(),
                    "maximum_market_age_minutes": 15,
                    "minimum_turnover_sar": 0.0,
                    "maximum_candidates_per_horizon": 25,
                },
            )
        incomplete = dict(self.paths)
        incomplete.pop("calendar")
        with self.assertRaisesRegex(SaudiAdmissionError, "artifact paths fields mismatch"):
            self.verify(artifact_paths=incomplete)

    def test_hardlinked_artifacts_and_receipt_are_rejected_by_inode(self):
        self.paths["corporate_actions_report"].unlink()
        os.link(
            self.paths["denominator_report"],
            self.paths["corporate_actions_report"],
        )
        write_admission_receipt(
            self.receipt,
            purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
            artifact_paths=self.paths,
            decision_at=self.decision_at,
            execution_contract=self.execution_contract,
        )
        with self.assertRaisesRegex(SaudiAdmissionError, "inode-distinct"):
            self.verify()

    def test_role_specific_artifact_size_limit_fails_closed(self):
        self.paths["calendar"].write_bytes(b"x" * (8 * 1024 * 1024 + 1))
        write_admission_receipt(
            self.receipt,
            purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
            artifact_paths=self.paths,
            decision_at=self.decision_at,
            execution_contract=self.execution_contract,
        )
        with self.assertRaisesRegex(SaudiAdmissionError, "cannot be read safely"):
            self.verify()

        self.paths["corporate_actions_report"].unlink()
        self.paths["corporate_actions_report"].write_text(
            '{"role":"corporate_actions_report","synthetic":true}\n',
            encoding="utf-8",
        )
        write_admission_receipt(
            self.receipt,
            purpose=AdmissionPurpose.NIGHTLY_MODEL_USE,
            artifact_paths=self.paths,
            decision_at=self.decision_at,
            execution_contract=self.execution_contract,
        )
        self.paths["input"].unlink()
        os.link(self.receipt, self.paths["input"])
        with self.assertRaisesRegex(SaudiAdmissionError, "inode-distinct"):
            self.verify()

    def test_holdout_purpose_binds_three_artifacts_and_run(self):
        holdout_paths = {
            role: self.root / f"{role}.json"
            for role in ("sealed_predictions", "outcome_vault", "run_report")
        }
        for role, path in holdout_paths.items():
            path.write_text(
                json.dumps({"role": role, "synthetic": True}) + "\n",
                encoding="utf-8",
            )
        holdout_contract = {
            "scored_at": self.decision_at.isoformat(),
            "run_id": "synthetic-holdout-run",
        }
        write_admission_receipt(
            self.receipt,
            purpose=AdmissionPurpose.HOLDOUT_SCORE,
            artifact_paths=holdout_paths,
            decision_at=self.decision_at,
            execution_contract=holdout_contract,
        )
        verified = verify_saudi_admission_receipt(
            self.receipt,
            purpose=AdmissionPurpose.HOLDOUT_SCORE,
            artifact_paths=holdout_paths,
            decision_at=self.decision_at,
            expected_execution_contract=holdout_contract,
        )
        self.assertEqual(verified.purpose, AdmissionPurpose.HOLDOUT_SCORE)
        self.assertEqual(set(verified.artifact_sha256), set(holdout_paths))
        self.assertEqual(
            set(verified.assertions),
            {"packet_sealed", "vault_sealed", "run_binding_verified"},
        )


if __name__ == "__main__":
    unittest.main()
