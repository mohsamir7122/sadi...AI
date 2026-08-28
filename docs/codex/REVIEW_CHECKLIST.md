# Merger review checklist

Use this checklist for each capability-slice commit and again on the exact Draft PR head. Record evidence; do not mark an item from expectation.

`Exact Draft PR head` means the checked-out commit SHA equals the PR's
candidate-head SHA. A merge ref or an earlier branch commit is insufficient.

## Repository and source lock

- [ ] Target remote, visibility, default branch, task branch, and clean/dirty state are verified.
- [ ] Source repositories are detached/read-only with disabled push URLs.
- [ ] Exact source commit, tree, PR lineage, license/rights, and selection reason are locked.
- [ ] Untouched source baselines and pre-existing failures are recorded.
- [ ] No unrelated-history merge, force push, destructive clean/reset, or source-repo write occurred.

## Capability and provenance

- [ ] Every affected `KUBO-*`/`AIM-*` row has a disposition, owner, target path, and acceptance test.
- [ ] Imported behavior maps to exact repository/SHA/paths and preserves notices.
- [ ] Existing KU-BO equivalence is demonstrated by contracts and adversarial tests.
- [ ] Duplicate entrypoints use a tested compatibility/deprecation path.
- [ ] No private implementation crosses the public-target boundary without `SAI-DEC-003`.

## Architecture and Saudi isolation

- [ ] The core uses explicit market-provider contracts and `as_of`/`known_at` boundaries.
- [ ] Saudi is the active adapter; Kuwait is legacy/isolated and inactive by default.
- [ ] Active Saudi paths contain no `KWD`, `Asia/Kuwait`, Boursa Kuwait, iFSAH, Kuwait calendar, or Kuwait product-ID dependency.
- [ ] `SAR`, `Asia/Riyadh`, official Saudi identity, TASI, and segment boundaries are explicit.
- [ ] Main Market and Nomu policies, memberships, benchmarks, and claims cannot mix silently.

## Causality and denominators

- [ ] Identity, universe, classifications, sessions, statuses, rules, and Corporate Actions are effective-dated.
- [ ] Publication/availability cutoff is applied before feature generation and decision issuance.
- [ ] Future revisions, current membership, and current sectors are rejected in historical runs.
- [ ] Suspended, non-traded, and delisted expected rows remain in the denominator with explicit states.
- [ ] Raw, adjusted, price-return, and total-return series remain distinct.
- [ ] Unresolved material action or incomplete no-action coverage blocks affected returns.

## Sources, privacy, and claims

- [ ] Each source declares authority, independence, access, freshness, delay class, rights, and failure policy.
- [ ] Raw/private/vendor datasets, sessions, credentials, personal IDs, and user financial state are outside Git.
- [ ] Search/social/archive content cannot create an official fact.
- [ ] Delayed, synthetic, recorded, and live evidence are labeled correctly.
- [ ] Scores are not called probabilities; synthetic runs are not called real backtests.
- [ ] No recommendation, execution, full-market, accuracy, or live-operational claim exceeds proven gates.

## Build, tests, and handoff

- [ ] Focused unit/contract/migration/parity/adversarial tests pass.
- [ ] Full configured compile/lint/type/schema/test suite passes or exact pre-existing failures are documented.
- [ ] Deterministic Saudi synthetic replay and clean installed-package/CLI smoke pass.
- [ ] Secret, privacy, prohibited-artifact, license, and publication scans pass.
- [ ] `git diff --check`, dedicated diff review, and exact-head CI pass.
- [ ] Capability/provenance/status files and the latest handoff are updated.
- [ ] Draft PR body lists tests, claims, non-claims, blockers, decisions, and source lock.
- [ ] PR remains Draft and unmerged.
