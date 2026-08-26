FINAL_STATUS: COMPLETED
REPOSITORY: mohsamir7122/sadi...AI
TARGET_VISIBILITY: public
BASE_BRANCH: main
STARTING_SHA: 36f0317183fcdf8b47149d2cfb4a11640fe0488a
TASK_BRANCH: codex/saudi-engine-merger-v1
FINAL_SHA: 24735a34084dc42f285927560723b36b80818c59
DRAFT_PR: https://github.com/mohsamir7122/sadi...AI/pull/2
CI_RUN: 32989063479; 32990157162 — exact head f1040c55bfe77bb9324cb6ff9cf88c1403dfc309, PASS, Python 3.11–3.14
PHASE: Saudi PR #2 repair and merge
STARTED_AT: 2026-08-26T15:14:21Z
COMPLETED_AT: 2026-08-26T17:00:50Z

## User goal

Repair the Saudi migration boundary, preserve the fail-closed outcome-session assertion, validate the exact head, and merge only under the conditional authority recorded in `SAI-2026-08-26-MERGE-COND-001`.

## Verified starting state

The target was public, `main` was `e7126bf6f0d127790dd58ceb2cfafe7624a16e37`, and the original PR #2 head was `36f0317183fcdf8b47149d2cfb4a11640fe0488a`. The untouched PR baseline reproduced three failures in 2103 tests: control metadata, missing unfrozen-policy blocker, and Kuwait root-marker contamination. The base worktree was clean; the target `main` remained unchanged until merge.

## Changes made

- `src/kubo/outcome_sessions.py`: added Saudi root markers and committed-policy routing while retaining Kuwait validation.
- `config/markets/saudi/outcome_session_policy.json`: added the Saudi fail-closed policy with `OUTCOME_SESSION_POLICY_NOT_FROZEN`.
- `docs/codex/CURRENT_TASK.md`, `docs/codex/USER_DECISIONS.md`, `scripts/codex_control_check.py`, and `tests/test_codex_control.py`: aligned the repair task and conditional authority without authorizing merge during repair or weakening gates.
- `tests/test_outcome_sessions.py`: added a regression assertion that Saudi no longer emits the Kuwait root-marker error.
- `.github/workflows/ci.yml`: added `workflow_dispatch` only; existing CI gates were not weakened.

## Validation

```text
LOCAL BASELINE: FAIL — 3 failures in 2103 tests, reproduced before the fix.
LOCAL POST-FIX SUITE: PASS — 2103 tests, 671.018 seconds.
TARGETED CONTROL/OUTCOME TESTS: PASS — 20 tests.
COMPILE: PASS.
CODEX CONTROL CHECK: PASS.
SECRET GUARD: PASS.
SAUDI CLI SYNTHETIC/NO-LIVE-DATA RUN: PASS — returns ABSTAIN with EMPTY_OR_UNVERIFIED_UNIVERSE.
EXACT-HEAD CI: PASS — runs 32989063479 and 32990157162 on f1040c55..., Python 3.11–3.14.
PR MERGE: PASS — PR #2 merged as 24735a34084dc42f285927560723b36b80818c59.
```

## Capability status

The Saudi migration boundary repair is `PARITY_PROVEN` for the tested root-marker and policy-routing behavior. Live source admission and market-wide research remain `BLOCKED_EXTERNAL`/`DEFINED_ONLY` pending authorized source access and data-quality evidence.

## Evidence and data status

The code and contracts are `PROVEN_CODE`; the CLI run is `SYNTHETIC_ONLY`/no-live-data. No licensed feed, live market data, or recorded authorized source fixture was used to claim coverage.

## Claims allowed and forbidden

Allowed: the repaired code path passes the recorded contract, local suite, exact-head CI, and fail-closed synthetic smoke. Forbidden: real backtest readiness, forecast accuracy, probability quality, recommendations, full-market coverage, live operation, or trade execution.

## Privacy, rights, and safety

The target is public. No credentials, private IDs, private/licensed raw data, personal data, force-push, deletion, paid access, or credential-scope expansion was used. The original repair/source branches remain retained. Rollback is `git revert 24735a34084dc42f285927560723b36b80818c59`.

## Decisions required

`SAI-2026-08-26-MERGE-COND-001` is the applicable approved conditional merge decision. `SAI-DEC-004` remains open; Nomu is not claimed in this release.

## Known limitations and risks

Source authority is still `DEFINED_ONLY`, so the Saudi CLI abstains on an empty/unverified universe. The duplicate pull-request CI run was still in progress at merge time, but two completed exact-head CI runs were green; no required exact-head test was red. A future data phase must independently validate Saudi schemas, calendars, identity, price actions, announcements, and rights.

## Exact next action

Resume with a separately recorded Saudi data-foundation batch: populate the official point-in-time universe and first issuer queue using authorized sources only, then require source coverage, identity, calendar, and corporate-action gates before any training or live research. Entry gate: `main` at `24735a34084dc42f285927560723b36b80818c59`; exit gate: a reproducible source-backed dry-run receipt with no unresolved identity or availability violations.
