# SAI task handoff template

Save each checkpoint as `docs/codex/handoffs/<TASK_OR_PHASE>-result.md`.

```text
FINAL_STATUS: COMPLETED | PARTIAL | BLOCKED
REPOSITORY:
TARGET_VISIBILITY:
BASE_BRANCH:
STARTING_SHA:
TASK_BRANCH:
FINAL_SHA:
DRAFT_PR:
CI_RUN:
PHASE:
STARTED_AT:
COMPLETED_AT:
```

## User goal

State the requested outcome precisely.

## Verified starting state

Record remotes, exact source/target SHAs, source-lock digest, open PR topology, baseline tests, target worktree state, and any drift from the prior checkpoint.

## Changes made

Group by capability ID. List source paths/SHA, target paths, transformation decision, and important contracts.

## Validation

For every command or CI job record:

```text
COMMAND_OR_JOB:
RESULT: PASS | FAIL | SKIPPED
DETAIL:
```

## Capability status

List newly `PARITY_PROVEN`, `SUPERSEDED_WITH_EQUIVALENCE`, `PARTIAL`, `BLOCKED_EXTERNAL`, or `ARCHIVE_CONTEXT_ONLY` rows.

## Evidence and data status

Distinguish `PROVEN_CODE`, `SYNTHETIC_ONLY`, `RECORDED_AUTHORIZED_FIXTURE`, `LIVE_DEPENDENT`, `LICENSED_FEED_DEPENDENT`, and `BLOCKED`.

## Claims allowed and forbidden

Explicitly address real backtest readiness, forecast accuracy, probability, recommendation, full-market coverage, and `LIVE_OPERATIONAL` status.

## Privacy, rights, and safety

Confirm target visibility and whether the change contains private-source code, credentials, private IDs, licensed data, raw market data, personal data, or destructive cleanup.

## Decisions required

Reference exact `SAI-DEC-*` entries or write `None`.

## Known limitations and risks

State concrete failure modes and affected scope.

## Exact next action

Provide one resumable command/task with its entry and exit gate. Never describe future work as completed.
