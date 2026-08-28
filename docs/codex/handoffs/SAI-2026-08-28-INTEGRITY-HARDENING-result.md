FINAL_STATUS: BLOCKED
REPOSITORY: mohsamir7122/sadi...AI
TARGET_VISIBILITY: public
BASE_BRANCH: main
STARTING_SHA: fcb8f482990d410b6916f60a368d8ba059e1588c
TASK_BRANCH: codex/saudi-integrity-hardening-v1
IMPLEMENTATION_SHA: bcac0faddd92ecf8cc7b3a170b7336919c74a513
FINAL_SHA: bcac0faddd92ecf8cc7b3a170b7336919c74a513 — implementation; this handoff metadata follows it and the PR API is authoritative for the candidate head
DRAFT_PR: https://github.com/mohsamir7122/sadi...AI/pull/5
CI_RUN: PENDING — exact final Draft PR head has not completed the Python 3.11–3.14 matrix
PHASE: Synthetic Saudi integrity hardening and Draft PR handoff
STARTED_AT: 2026-08-28T22:43:28Z — first committed checkpoint
COMPLETED_AT: N/A — task remains BLOCKED

## User goal

Professionally assess the repository, identify its real tasks, capabilities,
results, and weaknesses, then implement the justified improvements without
claiming real-data or production readiness.

## Verified starting state

The public target `main` was
`fcb8f482990d410b6916f60a368d8ba059e1588c` and the worktree started from the
recorded Saudi engineering spine. The starting implementation exposed useful
synthetic research contracts but had confirmed rights-vocabulary divergence,
temporal leakage risks, insufficient holdout separation, incomplete calendar
and identity boundaries, and stale capability/status evidence. No official
Saudi dataset, production admission issuer, real trained model, or authorized
live workflow was present.

## Changes made

- `KUBO-002`, `KUBO-012`, `KUBO-015`: added closed Saudi schemas, exact
  purpose-scoped Ed25519 receipt and artifact verification, registered
  exact-class admission results, adversarial tests, distribution builds, and
  installed-CLI checks. The bundled trust class remains `SYNTHETIC_ONLY`.
- `KUBO-005`: added bitemporal Main Market identity, checksum-valid ISIN
  validation, membership/selectability separation, and complete denominator
  serialization including suspended/non-ordinary members.
- `KUBO-006`: added bounded effective-dated Riyadh schedules, explicit closures,
  fail-closed coverage, calendar-derived maturity, strict timestamp/URI
  contracts, and registered deep-snapshot verification of parsed revisions.
- `AIM-005`: unified exact rights semantics and prohibited implicit aliases,
  rights promotion, and missing-factor zero-imputation.
- `AIM-004`: added strict denominator and Corporate Actions evidence reports
  and fail-closed claim audit boundaries.
- `AIM-011`: implemented one global chronological split, causal purge using
  label and `evidence_known_at` availability, coverage/gap/minimum gates,
  calendar-aware five-horizon maturity, model fingerprinting, and a separately
  sealed holdout scoring process.
- `AIM-013`: implemented strict post-open admission, Point-in-Time denominator,
  scan-time integrity before liquidity, empty-universe abstention, and a closed
  five-horizon candidate-research output envelope.
- `AIM-008`, `AIM-010`: retained bounded structural snapshot and monotonic
  checkpoint behavior only; broker execution, persistence, and collectors were
  not added.
- Updated v0.3 packaging, migration/operations/capability documentation,
  provenance, and the Draft-only control surface.

## Validation

```text
FINAL LOCAL FULL SUITE:
RESULT: PASS
DETAIL: 2177 tests in 169.360 seconds.

FINAL SAUDI SUITE:
RESULT: PASS
DETAIL: 89 tests in 23.307 seconds.

TARGETED CALENDAR/SCHEMA/RELEASE SUITE:
RESULT: PASS
DETAIL: 28 tests; marker-assisted replace, copy, post-registration mutation,
malformed timestamps, malformed URI forms, and dependency metadata covered.

INTERMEDIATE FULL SUITE:
RESULT: FAIL, THEN RESOLVED
DETAIL: One stale release-metadata expectation after enabling
jsonschema[format]; corrected before the final passing suite.

COMPILE AND DIFF:
RESULT: PASS
DETAIL: python -m compileall -q src tests scripts; git diff --check.

DETERMINISTIC CORPUS:
RESULT: PASS
DETAIL: 1280 cases; SHA-256 e7e84f75feae5ea72a5d4f67af50da24f5d46e5a9cba49030ff8547a41b50288.

SMOKE AND SECRET GUARDS:
RESULT: PASS
DETAIL: Synthetic smoke and repository secret-pattern guard passed.

SOURCE/WHEEL BUILD AND INSTALLED CLI:
RESULT: PASS
DETAIL: Clean wheel install, pip check, four Saudi CLI help surfaces, installed
API imports, and required sdist paths passed. Artifact hashes are kept outside
the source package to avoid a self-referential handoff hash.

EXACT-HEAD CI:
RESULT: BLOCKED
DETAIL: No completed exact-final-head Python 3.11–3.14 run yet.
```

## Capability status

All affected rows remain `PARTIAL`. None is promoted to `PARITY_PROVEN` or
production-ready because official source, entitlement, prospective, and
exact-head CI evidence is absent. Production admission, official calendar
history, source-backed factor lineage, authenticated end-to-end holdout replay,
and real excess-return recomputation are `BLOCKED_EXTERNAL` or unimplemented.

## Evidence and data status

The code, schemas, tests, and built artifacts are `PROVEN_CODE`; all Saudi
execution fixtures and fitted examples are `SYNTHETIC_ONLY`. No
`RECORDED_AUTHORIZED_FIXTURE`, live source, licensed feed, real full-market
corpus, or production model result is included.

## Claims allowed and forbidden

Allowed: the bounded synthetic integrity contracts pass the recorded local
tests and fail closed on missing/invalid authority. Forbidden: real backtest
readiness, forecast accuracy, probability calibration, recommendation,
full-market coverage, prospective validation, `LIVE_OPERATIONAL`, order
routing, or trade execution.

## Privacy, rights, and safety

The target is public. No credentials, private IDs, private conversation data,
licensed/raw market data, personal data, paid access, force-push, deletion, or
credential-scope expansion was used. The public deterministic Ed25519 seed is
explicitly test-only and is not a production credential. Same-process hostile
Python reflection is not treated as a production authentication boundary.

## Decisions required

No new decision is required to keep PR #5 Draft. Any merge requires a separate
task transition and all conditions in `SAI-2026-08-26-MERGE-COND-001`; this
handoff does not authorize merge.

## Known limitations and risks

1. No production admission issuer/key or hostile-process trust boundary exists.
2. Calendar knowledge is revision-level, not a complete official historical
   ledger with per-session/per-closure availability timestamps.
3. Operational flows do not resolve FactorRegistry membership, factor-specific
   freshness, or registry lineage.
4. Holdout scoring binds its own receipt, packet, vault, and report but does not
   replay the original nightly receipt/signature and five artifacts.
5. Supplied excess returns are not recomputed from raw price, benchmark, and
   Corporate Actions legs.
6. No official real Saudi universe, real training, real backtest, prospective
   validation, recommendation, or live-trading evidence exists.

## Exact next action

Build and validate the final handoff tree, update Draft PR #5, then query the CI
run for that exact PR head. Keep `MERGE_ALLOWED: NO`; if the matrix is absent or
not fully green, preserve `FINAL_STATUS: BLOCKED` and do not merge.
