# Saudi AI merger — current status

Status date: 2026-08-25

## Repositories observed

```text
TARGET
  mohsamir7122/sadi...AI
  visibility: public
  main: 96f5c8f247d9d6be0ad9709808c6e822dd68ed28
  content at inspection: README.md only

STRUCTURAL BASE CANDIDATE
  mohsamir7122/ku-bo
  visibility: public
  main: 59833bf73510b3aa3901f628cbf2c13c0d01cf79
  main tree: a4b56728aa4920f5578525f2736f17fbf4616151
  current non-superseded stacked candidate at inspection:
    PR #19 head: 6aa50ac83112d0e3a2e4440e3a6676115b9fbe4a
    PR #20 head: 6e9ab870e727494d5eb9e1ec9fa98829d6391d68

CAPABILITY DONOR
  mohsamir7122/AI-Mincy
  visibility: private
  main: 85044b681b7048ac373e47e31f6c2bfa7a885c9c
  main tree: e4df4a97e96c7833eaa6891f562762f4af8f58ea
  notable open candidate at inspection:
    PR #13 head: 51eb5449da225ef990facc803ce4c3bb7fb5e6b2
```

These are inspection-time values, not permanent truth. Codex must refresh and write a source-lock artifact before importing code.

Neither source default branch was protected when inspected. This increases the need to pin commit and tree SHAs and forbids treating a branch name as an immutable dependency.

## Open-branch warning

Do not assume either `main` contains every desired capability. KU-BO had active PRs #17–#20 and stale/superseded PRs #2–#3. AI-Mincy had a stacked PR #2–#4 lineage and a separate Core v2 PR #13. Audit ancestry, CI, contracts, and capability deltas. Never merge all open PRs wholesale.

## Current proof state

```text
MERGER_CONTROL_PACKAGE: READY_IN_DRAFT_PR_1
CONTROL_PACKAGE_BRANCH: codex/prepare-saudi-merge-control
CONTROL_PACKAGE_COMMIT: e0fae3fc76f885bfd4845bc07b93ea4a9da08654
CONTROL_PACKAGE_PR: https://github.com/mohsamir7122/sadi...AI/pull/1
SOURCE_LOCK: NOT_CREATED
CAPABILITY_PARITY_AUDIT: NOT_RUN_BY_TARGET
PRIVATE_CODE_PUBLICATION: BLOCKED_ON_USER_DECISION
SAUDI_ADAPTER: NOT_IMPLEMENTED
SOURCE_TEST_BASELINES: NOT_RECORDED
TARGET_TEST_SUITE: NOT_PRESENT
LIVE_OPERATIONAL: 0
REAL_BACKTEST_READY: NO
PROSPECTIVE_VALIDATED: NO
```

## Intended architecture decision

KU-BO supplies the package/runtime spine. AI-Mincy supplies capabilities after semantic deduplication. The final codebase is Saudi-first and market-adapter based. Capability parity means equivalent governed behavior and tests, not preservation of every donor filename.
