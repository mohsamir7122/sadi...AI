# Saudi AI merger acceptance gates

## Gate 0 — orientation and source freeze

Pass only when target/source remotes, visibility, default branches, exact commits/trees, open PR topology, CI, and working-tree state are recorded. A machine-readable source lock must pin every imported capability.

## Gate 1 — untouched source baselines

Pass only when the selected KU-BO and AI-Mincy snapshots are tested without target modifications. Record exact commands, environment, counts, pre-existing failures, and unavailable tests. Never claim a target regression when the same failure existed in the source baseline.

## Gate 2 — provenance and rights

Pass only when every imported/reimplemented capability maps to exact source paths and SHAs, license/attribution is preserved, prohibited artifacts are excluded, and the public/private decision is respected. Hash equality alone is not sufficient lineage.

## Gate 3 — KU-BO foundation preservation

Pass only when the target builds, installs, exposes the expected CLI/library paths, and passes the applicable KU-BO baseline plus target migration tests. Evidence, normalized observations, features, forecasts, decisions, outcomes, and process assessments must remain distinct.

## Gate 4 — market abstraction

Pass only when Saudi behavior is implemented through explicit market interfaces and active defaults do not require Kuwait sources, `KWD`, `Asia/Kuwait`, Kuwait calendars, Kuwait security identities, Boursa Kuwait, iFSAH, IndexSignal, or Kuwait-only product IDs.

Allowed occurrences are limited to clearly marked legacy adapters, archive/migration documentation, donor provenance, and tests proving isolation.

## Gate 5 — Saudi identity, time, and universe

Pass only when:

- currency is `SAR` and market time is `Asia/Riyadh`;
- each security has effective-dated official identity and official code, with ISIN where available;
- provider symbols are aliases, never canonical joins;
- Main Market membership reconciles to a dated official universe for any real run;
- listings, transitions, suspensions, resumptions, and delistings are explicit;
- Nomu cannot be silently included in Main Market claims.

## Gate 6 — Saudi calendar, prices, benchmarks, and Corporate Actions

Pass only when official sessions determine horizons, non-traded rows are not synthesized, raw and adjusted bases remain distinct, units/currency are explicit, `TASI` and sector benchmarks are named, and affected returns stop when Corporate Action/no-action coverage is incomplete.

## Gate 7 — source authority, access, and rights

Pass only when each source declares authority tier, independence group, evidence roles, access mode, rights constraints, freshness, and capability state. `DEFINED_ONLY` is the default. Search/social/archive/storage cannot create official facts. Delayed data is labeled delayed.

## Gate 8 — temporal and denominator integrity

Pass only when availability times are causal, current snapshots are not copied backward, every expected security-session has an explicit state, no member disappears through survivorship or non-trading omission, and evaluation uses complete Point-in-Time evidence.

## Gate 9 — AI-Mincy capability parity

Pass only when every `AIM-*` row has a final disposition, target path, tests, and evidence. Copied files without reachable behavior do not pass. Existing KU-BO behavior may satisfy parity only through contract and adversarial tests.

## Gate 10 — financial claim boundaries

Do not claim `REAL_BACKTEST_READY`, `PROSPECTIVE_VALIDATED`, `LIVE_OPERATIONAL`, forecast probability, recommendation, accuracy, full-market coverage, or execution readiness unless their real-evidence gates explicitly pass. Synthetic and recorded fixtures prove code behavior only.

## Gate 11 — privacy and repository safety

Pass only when secret/privacy scans find no credentials, sessions, private IDs, raw private conversations, personal financial state, licensed datasets, raw provider exports, or unauthorized AI-Mincy publication. No destructive cleanup may occur.

## Gate 12 — test and package integrity

Before publication, run and record:

```text
compileall
configured lint/format/type checks
strict JSON and Schema validation
targeted migration and parity tests
full unit/integration/adversarial suite
synthetic Saudi end-to-end smoke
determinism replay
secret/privacy/publication scan
wheel/sdist build
isolated install
installed CLI exercise
dedicated diff review
exact-head CI
```

A skipped test requires an exact reason, impact, and recovery action.

## Gate 13 — Draft PR and handoff

Pass only when the task branch is pushed without force, a Draft PR targets the correct branch, the PR body lists dependencies/tests/claims/non-claims, the capability matrix and status are updated, and the handoff is complete. No merge or auto-merge occurs.

## Final status

Use `COMPLETED` only if every applicable gate passes. Use `PARTIAL` for valid work with noncritical gaps. Use `BLOCKED` when a critical evidence, rights, privacy, temporal, denominator, test, visibility, or user-decision gate fails.
