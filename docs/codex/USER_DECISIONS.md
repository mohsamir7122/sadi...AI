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

## Open decisions

```text
DECISION_ID: SAI-DEC-003
STATUS: OPEN
DATE_RAISED: 2026-08-25
TARGET: target visibility and AI-Mincy import rights
CATEGORY: VISIBILITY; PUBLICATION
CURRENT_STATE: The target is public, while AI-Mincy is private and has no declared license in repository metadata.
WHY_REQUIRED: Copying private-source implementation into a public repository is an irreversible publication step even when both repositories are user-owned.
OPTIONS:
1. Make the target private before importing AI-Mincy code. (Recommended during development.)
2. Keep the target public and explicitly authorize publication of selected AI-Mincy implementation.
3. Keep the target public and clean-room reimplement behavior from capability specifications without copying private implementation.
CODEX_RECOMMENDATION: Option 1 for the merger and validation period; decide later whether to publish a reviewed release.
USER_DECISION:
DECIDED_AT:
```

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
