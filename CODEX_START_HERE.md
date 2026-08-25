# Saudi AI — Codex CLI start here

This is the repository-native entrypoint for the multi-repository merger.

## One-sentence mission

Build a Saudi Exchange research engine in `mohsamir7122/sadi...AI` by using the latest verified KU-BO lineage as the engineering baseline and porting every non-duplicate AI-Mincy capability with provenance and parity tests, while preserving fail-closed evidence and publication rules.

## Required read order

1. `AGENTS.md`
2. `docs/codex/CURRENT_STATUS.md`
3. `docs/codex/USER_DECISIONS.md`
4. `docs/codex/CURRENT_TASK.md`
5. `docs/codex/MERGE_BLUEPRINT.md`
6. `docs/codex/SOURCE_AUDIT.md`
7. `docs/codex/CAPABILITY_MATRIX.md`
8. `docs/codex/SAUDI_ADAPTER_SPEC.md`
9. `docs/codex/ACCEPTANCE_GATES.md`
10. `docs/codex/REVIEW_CHECKLIST.md`

Do not edit before verifying target visibility, remotes, default branches, source heads, open PR topology, CI, and the working tree.

## First local commands

Run from the directory where the repositories should live:

```bash
git clone https://github.com/mohsamir7122/sadi...AI.git
cd sadi...AI
codex
```

If the target is already cloned, do not clone again. Open its root and run `codex`. Codex must run `gh auth status`, verify access to all three repositories, verify/fetch `main`, preserve a dirty worktree, create the task branch, add the two source remotes as read-only, disable their push URLs, and perform the Phase 0 source lock itself.

Inside Codex, use this short instruction:

```text
اضبط مستودع السعودية AI بالكامل وفق التعليمات، وأكمل حتى Draft PR، ولا تدمج.
```

## Important start condition

The target and merger output are public. `SAI-DEC-003` authorizes publication of selected AI-Mincy implementation into this target only after path-level provenance, secret/privacy, ownership/license, and publication gates pass. AI-Mincy itself remains private; bulk publication and private/raw data remain forbidden.

## Completion behavior

Continue through inspect, implement, test, review, fix, and rerun cycles. Stop only for a genuine credentials/licensing/visibility/destructive-action/user-decision blocker. Record the blocker precisely; never fabricate evidence or weaken a gate.
