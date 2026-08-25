# Prompt for Codex CLI at home

## First run

Before starting Codex, the repository must be on `codex/prepare-saudi-merge-control` (or on a later branch that contains it). Draft PR #1 is not merged into `main`; cloning and remaining on the default branch will not expose these instructions.

Paste this after opening Codex from the target repository root:

```text
Read AGENTS.md and CODEX_START_HERE.md completely, then read every control file in the required order. Summarize the exact target, both source repositories, open user decisions, active task, current phase, and stop boundaries. Verify live GitHub state because recorded SHAs are inspection-time values. Resolve the target visibility decision with me before publishing any private AI-Mincy implementation. Then execute SAI-MERGE-001 from the first incomplete phase: create or resume the dedicated task branch, treat both sources as read-only, pin exact source snapshots, run honest untouched baselines, preserve provenance, implement in gated capability slices, run all applicable tests and reviews, push only the task branch, open or update a Draft PR, write the handoff, and do not merge.
```

## Resume run

```text
Read the repository control files and latest handoff. Verify HEAD, working tree, source lock, Draft PR, and CI against recorded state. Preserve valid completed work, resume the first incomplete gate, and continue through test/fix/review cycles. Do not restart blindly, cross an open decision boundary, merge, force-push, delete, or weaken a gate.
```

## Minimal start command

If you want the shortest possible prompt:

```text
Read CODEX_START_HERE.md and execute CURRENT_TASK safely to its gates. Do not merge.
```
