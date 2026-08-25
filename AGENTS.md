# Saudi AI merger instructions

Open this repository as the project root. This repository is the integration target for a Saudi Exchange research engine built from two user-owned source repositories:

- `mohsamir7122/ku-bo` — the canonical runtime, package, schema, test, ledger, and fail-closed research-engine base.
- `mohsamir7122/AI-Mincy` — the capability donor for skills, governed collectors, factor/data-foundation workflows, monitoring, training-data preparation, backtest audits, and market-intelligence workflows.

The target must retain KU-BO's engineering discipline while reaching verified behavioral capability parity with AI-Mincy. Do not create parity by blindly copying duplicate files.

## Mandatory entrypoint

Before changing anything, read in this order:

1. `CODEX_START_HERE.md`
2. `docs/codex/CURRENT_STATUS.md`
3. `docs/codex/USER_DECISIONS.md`
4. `docs/codex/CURRENT_TASK.md`
5. `docs/codex/MERGE_BLUEPRINT.md`
6. `docs/codex/SOURCE_AUDIT.md`
7. `docs/codex/CAPABILITY_MATRIX.md`
8. `docs/codex/SAUDI_ADAPTER_SPEC.md`
9. `docs/codex/ACCEPTANCE_GATES.md`
10. `docs/codex/REVIEW_CHECKLIST.md`

Treat `docs/codex/CURRENT_TASK.md` as the single active task. Historical prompts and source-repository handoffs are context, not authority.

## Git and repository safety

- Verify all remotes, visibility, default branches, exact source SHAs, open PRs, working-tree state, and CI before implementation.
- Run `gh auth status` and prove read access to target, KU-BO, and private AI-Mincy before source inspection. If authentication is missing, stop with the smallest exact login/access fix; never work around it by changing repository visibility.
- Never modify either source repository during this task.
- Treat source checkouts/remotes as read-only. Disable their push URLs after verification so an accidental source push is impossible.
- Never work directly on target `main`. Create or resume the task branch declared in `CURRENT_TASK.md`.
- Never merge, enable auto-merge, force-push, rewrite shared history, delete branches/tags/files, or weaken a gate without an explicit recorded user decision.
- Preserve source provenance. Every imported or reimplemented capability must map to its source path and exact source commit/PR head.
- Stage explicit target paths only; do not use broad `git add -A`. Add `Capability-ID`, `Source-Repo`, `Source-Commit`, and `Source-Paths` trailers to capability-port commits.
- Do not use `git merge --allow-unrelated-histories` as the integration strategy. Import the selected KU-BO snapshot as the structural baseline, then port capabilities in coherent, tested slices.
- Keep every PR Draft until all applicable gates pass. A green implementation branch is not merge authority.

## Privacy, rights, and data safety

- The target and merger output are public. Under `SAI-DEC-003`, selected AI-Mincy implementation may be published into this target after path-level provenance, secret/privacy, license/ownership, and publication review. This is not authority to make the entire donor repository public, bulk-copy it, or publish its data and secrets.
- Never commit credentials, cookies, sessions, browser profiles, API keys, HMAC keys, signed URLs, private Drive identifiers, licensed data, broker exports, raw Investing.com data, Telegram content, portfolio screenshots, or personal financial state.
- Use synthetic or explicitly authorized minimal fixtures in Git. Keep runtime evidence and private datasets outside Git.
- Never bypass login, CAPTCHA, paywalls, WAF, rate limits, robots controls, or protected APIs.

## Financial-research boundaries

- This is a research engine, not a live trading or order-execution system.
- Never call delayed data live; never infer a fill from a recommendation; never call a score a probability.
- Raw capture is not a validated Finding. Search results, social posts, archives, and storage are not official evidence.
- Require Point-in-Time availability, effective-dated security identity, official sessions, Corporate Actions, and a complete denominator before any historical evaluation.
- Missing, ambiguous, unlicensed, or unauthoritative evidence must fail closed to `WATCH`, `ABSTAIN`, `STOP_BACKTEST`, or an equivalent explicit blocked state.
- Synthetic tests prove code behavior only. They do not prove forecast validity, accuracy, full-market coverage, licensing, or `LIVE_OPERATIONAL` status.

## Saudi target invariants

- Active market: Saudi Exchange.
- Initial executable scope: Main Market equities; Nomu is a separate disabled-by-default extension until its own eligibility, liquidity, universe, and evaluation contracts pass.
- Currency: `SAR`; market timezone: `Asia/Riyadh`.
- Primary benchmark: `TASI`; sector benchmark must be explicit. `MT30` and `NomuC` are optional named benchmarks, never silent substitutes.
- Join securities by official Saudi security code plus effective-dated identity and ISIN where available; ticker-only joins are invalid.
- Saudi Exchange, CMA, and issuer disclosures outrank licensed vendors, which outrank reputable secondary sources. Community sources are sentiment/routing only.
- Kuwait-specific logic may remain only under a clearly isolated legacy/archive adapter. It must not affect Saudi defaults, source quorum, confidence, or runtime decisions.

## Work cycle

For each phase: inspect contracts and tests, implement the smallest complete slice, add migration/adversarial tests, run targeted checks, run the full relevant suite, inspect failures, fix root causes, update the capability matrix and status, and write a handoff checkpoint.

Do not claim the task complete until every capability row is classified and every applicable acceptance gate passes or is explicitly recorded as blocked with the smallest recovery action.

## Code review rules

Flag any change that introduces temporal leakage, survivorship bias, denominator omission, ticker-only identity, silent provider substitution, double-counted source independence, unadjusted Corporate Actions, delayed-as-live labeling, unlicensed data persistence, private-source publication, weakened tests, or unsupported financial claims.
