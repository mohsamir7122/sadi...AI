# Saudi PR #2 repair status — 2026-08-26

The repair branch starts from the exact failing PR #2 head
`36f0317183fcdf8b47149d2cfb4a11640fe0488a`.

The failure was a migrated KU-BO project-root resolver that accepted only the
KU-BO package/repository markers. On the Saudi target it stopped before policy
resolution and emitted `OUTCOME_SESSION_PROJECT_ROOT_KU_BO_MARKERS_INVALID`.

The resolver now recognizes the Saudi package/repository markers and resolves
the Saudi policy profile at `config/markets/saudi/outcome_session_policy.json`.
That policy is intentionally `UNFROZEN`, so the expected
`OUTCOME_SESSION_POLICY_NOT_FROZEN` blocker remains intact. No assertion was
weakened and no global Kuwait policy was changed.

Validation on the repair worktree:

- prior PR #2 baseline: 2,103 tests with 3 failures;
- targeted control/outcome tests: 20/20 passed after the repair;
- complete suite: 2,103/2,103 passed in 671.018 seconds;
- Saudi CLI: `ABSTAIN` with an empty/unverified universe and all sources
  `DEFINED_ONLY`;
- no live collection, training, real backtest, recommendation, or execution.
