# Saudi AI — Codex CLI start here

This is the repository-native entrypoint for the multi-repository merger.

## One-sentence mission

Build a Saudi Exchange research engine in `mohsamir7122/sadi...AI` by using the latest verified KU-BO lineage as the engineering baseline and porting every non-duplicate AI-Mincy capability with provenance and parity tests, while preserving fail-closed evidence rules and never merging or publishing private-source code without recorded authority.

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
git fetch origin --prune
git switch --track origin/codex/prepare-saudi-merge-control
git remote add kubo https://github.com/mohsamir7122/ku-bo.git
git remote add ai-mincy https://github.com/mohsamir7122/AI-Mincy.git
git remote set-url --push kubo DISABLED
git remote set-url --push ai-mincy DISABLED
git fetch --all --prune
git status --short --branch
codex
```

If the target is already cloned, do not clone again. Fetch and switch to the existing local control branch, or create its tracking branch as shown above. Stop rather than overwrite a dirty worktree. The control package is intentionally in Draft PR #1 and is not on target `main` yet.

Inside Codex, use this short instruction:

```text
Read CODEX_START_HERE.md and all required control files. Execute docs/codex/CURRENT_TASK.md from its verified checkpoint. Plan first, preserve source provenance, run every applicable gate, push only the task branch, open or update a Draft PR, and do not merge.
```

## Important start condition

The target was public and AI-Mincy was private when this control package was created. Planning, inventory, source-lock generation, and clean-room interface design may proceed. Copying private AI-Mincy implementation into the public target must wait for `SAI-DEC-003`.

## Completion behavior

Continue through inspect, implement, test, review, fix, and rerun cycles. Stop only for a genuine credentials/licensing/visibility/destructive-action/user-decision blocker. Record the blocker precisely; never fabricate evidence or weaken a gate.
