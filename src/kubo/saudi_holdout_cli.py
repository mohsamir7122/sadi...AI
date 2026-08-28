"""Score a previously sealed Saudi holdout packet in a separate process."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .atomic_output import run_atomic_output
from .foundation_io import strict_json_object
from .saudi_admission import (
    SYNTHETIC_ADMISSION_TRUST_CLASS,
    AdmissionPurpose,
    verify_saudi_admission_receipt,
)
from .saudi_capabilities.nightly_lab import (
    evaluate_sealed_holdout,
    holdout_outcome_vault_from_mapping,
    sealed_prediction_packet_from_mapping,
)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("scored-at must include a timezone offset")
    return parsed


def _utc(value: datetime) -> datetime:
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValueError("holdout timestamp is outside the supported UTC range") from exc


def _load_object(content: bytes, field: str) -> dict[str, Any]:
    return strict_json_object(content, field)


def _validate_run_binding(
    payload: dict[str, Any],
    *,
    run_id: str,
    packet_model_fingerprint: str,
    packet_seal_sha256: str,
    packet_sealed_at: datetime,
    vault_sha256: str,
) -> bool:
    expected = {
        "run_id": run_id,
        "model_fingerprint": packet_model_fingerprint,
        "seal_sha256": packet_seal_sha256,
        "outcome_vault_sha256": vault_sha256,
        "final_holdout_scored": False,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(f"holdout run binding mismatch: {field}")
    if payload.get("run_at") != packet_sealed_at.isoformat():
        raise ValueError("holdout run binding mismatch: run_at")
    governed_policy = payload.get("governed_policy")
    if not isinstance(governed_policy, dict):
        raise ValueError("holdout run binding mismatch: governed_policy")
    if governed_policy.get("run_id") != run_id:
        raise ValueError("holdout run binding mismatch: governed_policy.run_id")
    if governed_policy.get("run_at") != packet_sealed_at.isoformat():
        raise ValueError("holdout run binding mismatch: governed_policy.run_at")
    admission = payload.get("admission")
    if not isinstance(admission, dict) or type(admission.get("trust_class")) is not str:
        raise ValueError("holdout run binding mismatch: admission trust_class")
    if admission.get("purpose") != AdmissionPurpose.NIGHTLY_MODEL_USE.value:
        raise ValueError("holdout run binding mismatch: admission purpose")
    admission_contract = admission.get("execution_contract")
    if admission_contract != governed_policy:
        raise ValueError("holdout run binding mismatch: admission execution_contract")
    synthetic_only = (
        admission["trust_class"] == SYNTHETIC_ADMISSION_TRUST_CLASS
        or payload.get("evidence_class") == "SYNTHETIC_ONLY"
    )
    expected_status = (
        "SYNTHETIC_SEALED_AWAITING_FINAL_SCORE"
        if synthetic_only
        else "SEALED_AWAITING_FINAL_SCORE"
    )
    if payload.get("status") != expected_status:
        raise ValueError("holdout run binding mismatch: status")
    if payload.get("input_admission_authenticated") is not True:
        raise ValueError(
            "holdout run binding mismatch: input_admission_authenticated"
        )
    if payload.get("report_authenticated") is not False:
        raise ValueError("holdout run binding mismatch: report_authenticated")
    return synthetic_only


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score a sealed Saudi final holdout in a separate process"
    )
    parser.add_argument("--sealed-predictions", type=Path, required=True)
    parser.add_argument("--outcome-vault", type=Path, required=True)
    parser.add_argument("--run-report", type=Path, required=True)
    parser.add_argument("--admission-receipt", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scored-at", type=_timestamp, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    admission = verify_saudi_admission_receipt(
        args.admission_receipt,
        purpose=AdmissionPurpose.HOLDOUT_SCORE,
        artifact_paths={
            "sealed_predictions": args.sealed_predictions,
            "outcome_vault": args.outcome_vault,
            "run_report": args.run_report,
        },
        decision_at=args.scored_at,
        expected_execution_contract={
            "scored_at": args.scored_at.isoformat(),
            "run_id": args.run_id,
        },
    )
    packet = sealed_prediction_packet_from_mapping(
        _load_object(admission.artifact_bytes["sealed_predictions"], "sealed predictions")
    )
    if _utc(admission.issued_at) < _utc(packet.sealed_at):
        raise ValueError("holdout admission cannot predate the sealed packet")
    vault = holdout_outcome_vault_from_mapping(
        _load_object(admission.artifact_bytes["outcome_vault"], "outcome vault")
    )
    run_report = _load_object(
        admission.artifact_bytes["run_report"],
        "nightly run report",
    )
    if packet.run_id != args.run_id:
        raise ValueError("holdout packet run_id mismatch")
    nightly_synthetic_only = _validate_run_binding(
        run_report,
        run_id=args.run_id,
        packet_model_fingerprint=packet.model_fingerprint,
        packet_seal_sha256=packet.seal_sha256,
        packet_sealed_at=packet.sealed_at,
        vault_sha256=vault.vault_sha256,
    )
    report = evaluate_sealed_holdout(packet, vault, scored_at=args.scored_at)
    report["status"] = (
        "SYNTHETIC_HOLDOUT_METRICS"
        if (
            admission.trust_class == SYNTHETIC_ADMISSION_TRUST_CLASS
            or nightly_synthetic_only
        )
        else "ADMISSION_VERIFIED_HOLDOUT_METRICS"
    )
    report["input_admission_authenticated"] = True
    report["admission"] = admission.to_dict()
    report["report_authenticated"] = False
    report["report_is_market_evidence"] = False

    def write(staging: Path) -> None:
        (staging / "final_holdout_report.json").write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    run_atomic_output(args.output_root, write)
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
