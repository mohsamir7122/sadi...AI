# CURRENT TASK — SAI-2026-08-28-INTEGRITY-HARDENING

```text
TASK_ID: SAI-2026-08-28-INTEGRITY-HARDENING
STATUS: BLOCKED
REPOSITORY: mohsamir7122/sadi...AI
STARTING_MAIN_SHA: fcb8f482990d410b6916f60a368d8ba059e1588c
EXPECTED_TASK_BRANCH: codex/saudi-integrity-hardening-v1
EXPECTED_PR_MODE: DRAFT
MERGE_ALLOWED: NO
FORCE_PUSH_ALLOWED: NO
PERMANENT_DELETE_ALLOWED: NO
SOURCE_REPOSITORY_WRITE_ALLOWED: NO
REAL_MARKET_DATA_COMMIT_ALLOWED: NO
PRIVATE_SOURCE_PUBLICATION_ALLOWED: SELECTED_IMPLEMENTATION_ONLY_PER_SAI-DEC-003
MODEL_TRAINING_ALLOWED: SYNTHETIC_FIXTURE_FITTING_ONLY; REAL_OR_PRODUCTION_NO
REAL_BACKTEST_ALLOWED: NO
LIVE_TRADING_ALLOWED: NO
BLOCKED_ON: EXACT_DRAFT_PR_HEAD_CI_PENDING; OFFICIAL_SOURCE_DATA_AND_PRODUCTION_TRUST_NOT_AVAILABLE; SAI-HYBRID-001_REMAINS_BLOCKED_UNTIL_POST_MERGE_MAIN_CI_PASSES
MERGE_DECISION_REFERENCE: SAI-2026-08-26-MERGE-COND-001
```

## Mission

Harden the existing synthetic Saudi research paths without claiming data or
model readiness. Fix the confirmed rights-vocabulary mismatch, eliminate
global and label-availability temporal leakage, separate final-holdout scoring,
make the default Saudi calendar effective-dated and fail closed, and enforce
Main Market ordinary-equity identity at selectable-universe boundaries.

Recorded authority remains in `docs/codex/USER_DECISIONS.md`; publication must
follow `docs/codex/HANDOFF_TEMPLATE.md` and the conditional merge reference
`SAI-2026-08-26-MERGE-COND-001`.

## In scope

1. Central, exact-match rights grants with distinct research and model-use
   policies; no silent aliasing or promotion of review states.
2. One global chronological split with Point-in-Time label purging, deterministic
   cohort coverage checks, and explicit history-coverage gates.
3. Preparation and final-holdout scoring as separate commands and artifacts.
4. A strict, effective-dated Saudi calendar schema/loader whose covered
   interval is explicit and whose uncovered dates fail closed. Only synthetic
   fixtures are permitted in this batch; an official recorded schedule remains
   an external data gate.
5. Separate membership from selectability so suspended securities remain in
   the denominator while only `MAIN` `ORDINARY_EQUITY` records with
   `tradable=true` are selectable.
6. Strict contracts, regression tests, local acceptance gates, and a Draft PR.

## Out of scope and claim boundaries

- Do not collect, commit, publish, train on, or backtest real Saudi market data.
- Do not enable Nomu, REITs, ETFs, CEFs, debt, derivatives, or tradable rights.
- Do not emit recommendations, probabilities, orders, or live-trading claims.
- Do not write to KU-BO or AI-Mincy, weaken tests, force push, or delete history.
- Do not start `SAI-HYBRID-001` until post-merge `main` CI is green.
- Keep all affected capabilities at `PARTIAL` or `BLOCKED` until source,
  entitlement, full-market, prospective, and exact-head CI gates pass.

## Exit gates

1. Targeted and full local suites, compile, control, corpus, secret, build, and
   installed CLI checks pass on the exact local head.
2. The checked-out commit SHA must equal the Draft PR candidate-head SHA, and
   that exact SHA must pass the configured Python 3.11–3.14 CI matrix. A
   synthetic merge ref or a run on an earlier commit is not exact-head proof.
3. Review finds no temporal, survivorship, product-scope, rights, or holdout
   regression and no unsupported readiness claim.
4. Merge requires a separate task-status transition after all gates pass; this
   task currently keeps `MERGE_ALLOWED: NO`.
