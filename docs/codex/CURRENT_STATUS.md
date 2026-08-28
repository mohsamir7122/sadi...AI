# Saudi AI integrity hardening — current status

Status date: 2026-08-28

## Active engineering state

```text
REPOSITORY: mohsamir7122/sadi...AI (public)
BASE_BRANCH: main
CURRENT_MAIN_SHA: fcb8f482990d410b6916f60a368d8ba059e1588c
LATEST_MERGED_PR: #3 — https://github.com/mohsamir7122/sadi...AI/pull/3
ACTIVE_TASK: SAI-2026-08-28-INTEGRITY-HARDENING
TASK_STATUS: BLOCKED
ACTIVE_BRANCH: codex/saudi-integrity-hardening-v1
DRAFT_PR: #5 — https://github.com/mohsamir7122/sadi...AI/pull/5
IMPLEMENTATION_COMMIT: dc66ff5ca47014494e828aed09ffa85becdfa6d4
IMPLEMENTATION_TREE: 556079fbdcc7c8c7737f073dab9666fb2f123870
DRAFT_PR_HEAD: PENDING_HANDOFF_METADATA_COMMIT
LOCAL_FULL_SUITE: PASS — 2177 tests
LOCAL_SAUDI_SUITE: PASS — 89 tests
COMPILE_AND_DIFF_CHECK: PASS
CONTROL_CHECK: PASS — merge authorization false
CORPUS_AUDIT: PASS — 1280 deterministic cases
SMOKE_AND_SECRET_GUARDS: PASS
SOURCE_AND_WHEEL_BUILD: PASS — installed CLIs/API verified
EXACT_DRAFT_PR_HEAD_CI: PENDING
MERGE_ALLOWED: NO
LIVE_OPERATIONAL: 0
REAL_BACKTEST_READY: NO
PROSPECTIVE_VALIDATED: NO
REAL_OR_OPERATIONAL_MODEL_TRAINING_COMPLETED: NO
SYNTHETIC_FIXTURE_FITTING_TESTED: YES
```

## Implemented scope

Draft PR #5 hardens the bounded synthetic Saudi research slice: purpose-scoped
Ed25519 admission, unified rights, strict evidence reports, global causal
splits, calendar-derived horizon maturity, separated holdout scoring,
Point-in-Time Main Market identity and denominator semantics, post-open
abstention contracts, effective-dated calendar coverage, and packaged v0.3
CLIs/schemas. Calendar objects are accepted only as registered parser results
and are rechecked against a deep structural snapshot on use.

## Evidence and data boundary

All Saudi execution evidence in this batch is `SYNTHETIC_ONLY`. No official
full-market security master, historical calendar revision ledger, raw price or
benchmark legs, Corporate Actions corpus, production admission issuer, or
legally approved production factor dataset was collected or committed. The
queued Saudi data-foundation task remains blocked until its separate entry
gates are satisfied.

## Remaining blockers

- The exact final Draft PR head has not passed the Python 3.11–3.14 CI matrix.
- The bundled admission issuer and deterministic signing material are test-only;
  no production issuer or production key is configured.
- The calendar is a revision-level bounded schedule plus explicit closures, not
  a complete official per-session history with individual availability times.
- Operational paths do not yet resolve FactorRegistry membership, per-factor
  freshness, or registry lineage.
- Holdout scoring authenticates its own packet and vault but does not replay the
  original nightly receipt/signature and five admitted artifacts.
- Excess returns are supplied governed values; they are not recomputed from
  admitted raw price, benchmark, and Corporate Actions legs.
- No real training, real backtest, prospective validation, recommendation,
  order routing, or live trading has been performed or authorized.

## Safety and rollback

The PR remains Draft and `MERGE_ALLOWED: NO`. No force-push, deletion, secret
publication, paid access, credential expansion, private/licensed raw data, or
real market data was used. If a later authorized merge occurs, rollback must be
performed with a normal revert of that merge commit; this task does not merge.
