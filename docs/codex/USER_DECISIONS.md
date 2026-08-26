# Saudi AI — user decisions

## Approved decisions

```text
DECISION_ID: SAI-DEC-001
STATUS: APPROVED
DATE: 2026-08-25
TARGET: mohsamir7122/sadi...AI
CATEGORY: SCOPE; ARCHITECTURE
USER_DECISION: Prepare a complete merger plan for AI-Mincy and KU-BO in the named target repository. The resulting system should use KU-BO as the operating structure and be able to perform all useful AI-Mincy tasks. The active market is Saudi Exchange.
IMPLEMENTATION_GUARD: Capability parity must be proven; blind file overlay is not acceptable. Source repositories must remain unchanged.
```

```text
DECISION_ID: SAI-DEC-002
STATUS: APPROVED
DATE: 2026-08-25
TARGET: merger control package
CATEGORY: WORKFLOW
USER_DECISION: Prepare the plan and Codex instructions in ChatGPT Work now; execute the actual merger later with Codex CLI on the user's computer.
IMPLEMENTATION_GUARD: This approval authorizes preparation and later task-branch implementation, not merging into main, force-pushing, deleting, publishing private data, or spending money.
```

```text
DECISION_ID: SAI-DEC-003
STATUS: APPROVED
DATE: 2026-08-25
TARGET: public target and selected AI-Mincy implementation
CATEGORY: VISIBILITY; PUBLICATION
USER_DECISION: Keep the Saudi target and merger output public. Authorize publication of selected AI-Mincy implementation into the target as part of the governed capability migration.
SELECTED_OPTION: 2
IMPLEMENTATION_GUARD: AI-Mincy itself remains private. This does not authorize bulk publication, raw/private/licensed data, credentials, sessions, personal financial information, or paths that fail provenance, ownership/license, secret/privacy, and publication review.
```

```text
DECISION_ID: SAI-DEC-005
STATUS: APPROVED
DATE: 2026-08-25
TARGET: merger control package
CATEGORY: WORKFLOW; DEFAULT_BRANCH
USER_DECISION: Put the control package on target main so Codex can start from the repository name and a short instruction at home.
IMPLEMENTATION_GUARD: Only the planning/control package may be merged now. The application merger must remain on its dedicated task branch and end in a Draft PR without merge.
```

```text
DECISION_ID: SAI-DEC-006
STATUS: APPROVED
DATE: 2026-08-25
TARGET: mohsamir7122/sadi...AI
CATEGORY: WORKFLOW; PUBLICATION; DEFAULT_BRANCH
USER_DECISION: Test and finish the new repository, perform the necessary merger, push the completed work, and merge it into the repository default branch.
IMPLEMENTATION_GUARD: Merge only after applicable tests and publication checks pass. No force push, credential publication, private/licensed data publication, or live order execution is authorized.
```

```text
DECISION_ID: SAI-DEC-007
STATUS: APPROVED
DATE: 2026-08-25
TARGET: recurring Saudi research workflows
CATEGORY: AUTOMATION; RESEARCH
USER_DECISION: Run a daily ten-year event training/validation/final-holdout laboratory at 22:00 with at least 50 primary and 300 probe events, and run a multi-horizon Saudi stock research scan thirty minutes after market open.
IMPLEMENTATION_GUARD: Use Point-in-Time source-backed data and fail closed when data, rights, identity, or freshness are incomplete. Outputs are research candidates, not personalized recommendations or execution instructions.
```

## Open decisions

```text
DECISION_ID: SAI-DEC-004
STATUS: OPEN
DATE_RAISED: 2026-08-25
TARGET: version-one Saudi market universe
CATEGORY: PRODUCT_SCOPE
CURRENT_STATE: The project goal names Saudi Exchange generally.
OPTIONS:
1. Main Market equities first, with Nomu implemented later behind a separate disabled-by-default adapter. (Recommended.)
2. Main Market and Nomu in the first executable release.
3. Main Market, Nomu, REITs, ETFs, and debt instruments in the first release.
CODEX_RECOMMENDATION: Option 1 to avoid mixing eligibility, liquidity, benchmark, and outcome policies.
DEFAULT_UNTIL_DECIDED: Implement shared contracts and Main Market synthetic fixtures only; do not claim Nomu coverage.
USER_DECISION:
DECIDED_AT:
```

## Decision rules

- Silence is not approval.
- Codex may continue through analysis and reversible scaffolding while a decision is open, but must stop before crossing that decision boundary.
- No merge, permanent deletion, public release, credentials use, paid data purchase, or gate weakening without a specific approved record.

```text
DECISION_ID: SAI-2026-08-26-MERGE-COND-001
STATUS: APPROVED
DATE_RAISED: 2026-08-26
TARGET: Saudi PR #2 and subsequent engineering merges after the Kuwait gates complete
CATEGORY: MERGE
CURRENT_STATE: The owner has authorized Codex to merge engineering changes without asking again, but only after every merge gate in the master Kuwait/Saudi execution contract passes on the exact head SHA.
WHY_A_DECISION_IS_REQUIRED: Repository-local controls require the merge authority and its limits to be recorded before the first merge.
OPTIONS:
1. Permit conditional merge after all section-8 gates pass on the exact head SHA.
2. Require a new owner confirmation for every otherwise-gated engineering merge.
3. Permit unconditional merge.
CODEX_RECOMMENDATION: Option 1.
CONSEQUENCE_OF_APPROVAL: Codex may merge only the validated exact head after provenance, diff, tests, dry-run, privacy/licensing, rollback, changelog, decision, and status gates pass.
CONSEQUENCE_OF_REJECTION: Validated work remains in a branch/Draft PR until a later decision.
SAFER_REVERSIBLE_ALTERNATIVE: Keep PR #2 Draft and unmerged while fixing the root-marker/policy migration failure.
USER_DECISION: APPROVED by the active master execution contract.
DECIDED_AT: 2026-08-26
DECIDED_BY: Mohamed Samir Rashed Shaheen
IMPLEMENTATION_GUARD: This authority is conditional, not absolute. It excludes force-push, protected-history rewrite, deletion, secret disclosure, paid access, private/licensed publication, trading or money movement, credential-scope expansion, and gate weakening. PR #2 is not merge-ready while CI is failing.
IMPLEMENTED_IN_BRANCH_OR_PR: codex/saudi-engine-merger-v1-repair; future validated PR exact head only
```
