# Prompt for Codex CLI at home

## First run

After cloning/opening the target repository root and running `codex`, say only:

```text
اضبط مستودع السعودية AI بالكامل وفق التعليمات، وأكمل حتى Draft PR، ولا تدمج.
```

Because Codex reads root `AGENTS.md` before work, that short prompt activates the full repository-native plan.

If Codex is opened outside the repository and the target is not cloned, use this single sentence instead:

```text
افتح أو استنسخ GitHub repo mohsamir7122/sadi...AI، ثم اقرأ AGENTS.md وCODEX_START_HERE.md ونفّذ المهمة كاملة حتى Draft PR، ولا تدمج.
```

## Resume run

```text
Read the repository control files and latest handoff. Verify HEAD, working tree, source lock, Draft PR, and CI against recorded state. Preserve valid completed work, resume the first incomplete gate, and continue through test/fix/review cycles. Do not restart blindly, cross an open decision boundary, merge, force-push, delete, or weaken a gate.
```

## Minimal start command

If you want the shortest possible prompt:

```text
اضبط مستودع السعودية AI بالكامل وفق التعليمات، ولا تدمج.
```
