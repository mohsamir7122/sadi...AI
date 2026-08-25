# Capability matrix

This is the minimum donor inventory. Codex must expand it after inspecting exact locked source snapshots and open PRs. Every row requires a source path/SHA, target path, implementation decision, tests, and final evidence status.

Allowed final statuses:

```text
PARITY_PROVEN
SUPERSEDED_WITH_EQUIVALENCE
PARTIAL
BLOCKED_EXTERNAL
ARCHIVE_CONTEXT_ONLY
```

`NOT_REVIEWED`, `COPIED_ONLY`, and `TESTS_SKIPPED` are not successful final statuses.

## KU-BO foundation capabilities to preserve

- `KUBO-001 — Package and CLI foundation`: `src/kubo`, `pyproject.toml`, installed CLI behavior, build and isolated-install checks.
- `KUBO-002 — Strict Schemas and JSON contracts`: analysis requests, universe, Findings, source attempts, evidence manifests, runs, calendars, status, Corporate Actions, factors, outcomes, benchmarks, and reconciliation reports.
- `KUBO-003 — Evidence and provenance`: immutable hashes, manifests, raw/normalized separation, parser materialization, strict input validation, and atomic outputs.
- `KUBO-004 — Source network`: source catalog, capability inventory, access policy, orchestrator, bounded capture plan, attempts, retries, and fail-closed access states.
- `KUBO-005 — Effective-dated identity`: security master, provider mappings, official identity receipts, and date-valid joins.
- `KUBO-006 — Market calendar and status`: official sessions, holidays, trading/non-trading state, suspensions, halts, listings, and delistings.
- `KUBO-007 — Prices and benchmarks`: price-history workspace/import, official EOD contracts, benchmark registry/history, units, raw/adjusted basis, and reconciliation.
- `KUBO-008 — Corporate Actions`: schedule, enrichment, factor ledger, status integration, and incomplete-action stop gates.
- `KUBO-009 — Research workflow`: research request, source packet, parsed inputs, Findings, factor snapshot, ranking, decision, and report separation.
- `KUBO-010 — Forecast and outcome ledgers`: append-only issued decisions, realized outcomes, immutable evidence resolution, and no forecast rewriting.
- `KUBO-011 — Evaluation and replay`: causal evaluation, complete denominator, official sessions, costs/fills, `STOP_BACKTEST`, and withheld metrics on insufficient evidence.
- `KUBO-012 — Runtime trust`: external authorization registry, signed receipts, HMAC runtime keys, and caller-claim rejection.
- `KUBO-013 — Data foundation`: admission, lineage, reconciliation, tri-security pilot contracts, and installed adapter checks.
- `KUBO-014 — Historical context planning`: source registry, annual tasks, company lifecycle/history, legal procedural state, and context-only claim limits.
- `KUBO-015 — Packaging, CI, and adversarial tests`: compile, smoke, full suite, secret guard, wheel build/install, and exact-head CI.
- `KUBO-016 — Active PR capabilities`: inspect KU-BO PRs #17–#20, especially source-access recipes, capability-probe planning, Codex bootstrap, previous-session freeze, Factor 9 admission gates, and horizon contracts. Include only verified non-superseded behavior.

## AI-Mincy donor capabilities

### AIM-001 — Market-regime analysis

Source candidate: `skills/analyze-kuwait-market-regime`.

Saudi target: regime state using Saudi benchmarks, breadth, liquidity, volatility, sector leadership, macro/commodity context, and explicit as-of evidence. Must not copy Kuwait thresholds without Saudi calibration and Point-in-Time tests.

### AIM-002 — Press intelligence and catalyst radar

Source candidate: `skills/analyze-kuwait-press-intelligence`.

Saudi target: bounded Saudi press/issuer catalyst intake, independent-origin grouping, duplicate and correction lineage, official confirmation matching, source health, and context-only restrictions until admitted as evidence.

### AIM-003 — Telegram/community market intelligence

Source candidate: `skills/analyze-telegram-market-intelligence`.

Saudi target: consent-bound authorized import, pseudonymization, retention/revocation, structured-call diagnostics, ambiguous path handling, and sentiment/routing-only classification. No automatic retrieval or model feature use by default.

### AIM-004 — Backtest and missed-opportunity audit

Source candidate: `skills/audit-backtest-borsa-jadid`.

Saudi target: Point-in-Time audit, claim ledger, excluded-data recheck, root-cause analysis, missed-opportunity review, prospective ledger, and strict distinction between data failure, model failure, and execution failure.

### AIM-005 — Factor 9 data foundation

Source candidate: `skills/build-factor9-data-foundation` plus relevant active KU-BO PR controls.

Saudi target: governed Factor 9 admission, source/feature/label lineage, signed foundation, temporal availability, rights, deterministic validation, and no model use until every admission gate passes.

### AIM-006 — Official exchange collection

Source candidate: `skills/collect-boursa-kuwait-official`.

Saudi target: do not port Kuwait endpoints. Reuse only bounded collector architecture, manifests, checkpointing, publication/readback semantics, and tests. Implement Saudi Exchange/CMA/issuer adapters under reviewed access and rights rules.

### AIM-007 — Investing.com historical user-export workflow

Source candidate: `skills/collect-investing-com-history`.

Saudi target: authorized manual user-export ingestion, exact file/column/unit/time validation, provider-symbol mapping, Corporate Action reconciliation, and secondary-provider role. No automated extraction or raw provider data in Git.

### AIM-008 — Portfolio state validation

Source candidate: `skills/manage-kuwait-portfolio`.

Saudi target: SAR portfolio snapshots, holdings/cash/orders/fills/fees/Corporate Actions reconciliation, freshness and broker-evidence gates, structural-validation-only claim, and no automatic order execution.

### AIM-009 — Intraday/delayed monitoring

Source candidate: `skills/monitor-kuwait-market`.

Saudi target: Saudi session-aware monitoring, delayed/live distinction, status and catalyst refresh, legacy-horizon mapping, bounded periodic report, and stale-source warnings. No scheduler activation in the merger task.

### AIM-010 — Resumable market pipelines

Source candidate: `skills/operate-resumable-market-pipeline`.

Saudi target: checkpointed company research, idempotent resume, no-overwrite artifacts, run-state contracts, knowledge refresh, partial-failure reporting, and publication receipts.

### AIM-011 — Training dataset and walk-forward laboratory

Source candidate: `skills/prepare-kuwait-training-dataset`.

Saudi target: feature/label provenance, strict CSV parsing, causal label recomputation, official calendar, Corporate Actions, point-in-time universe, walk-forward splits, leakage controls, and final audit. No training on ineligible sources.

### AIM-012 — Research and forecast orchestration

Source candidate: `skills/research-and-forecast-boursa-kuwait` and AI-Mincy PR #13 Core v2.

Saudi target: orchestrated Saudi research with evidence gathering, factor snapshot, scenario analysis, rank/abstain decision, forecast ledger, prospective validation gates, and no single-provider dependency. Existing KU-BO behavior may supersede portions if parity is proven.

### AIM-013 — Full-market opportunity scan

Source candidate: `skills/scan-kuwait-stock-opportunities`.

Saudi target: official Main Market universe reconciliation, detection lead queue, breadth/liquidity/catalyst screening, source quorum per security, and explicit named-pilot versus full-market distinction.

### AIM-014 — Momentum-pattern study

Source candidate: `skills/study-kuwait-momentum-patterns`.

Saudi target: Saudi event labeling, session-aware horizons, adjusted/raw distinction, sector/market excess outcomes, liquidity/cost constraints, and no historical leakage.

### AIM-015 — Shared source governance and validators

Source candidates: `tools/canonical_source_contracts.py`, `tools/market_data_store.py`, `tools/reconcile_source_evidence.py`, `tools/source_access_policy.py`, model/source governance validators, repository validator, test runner, and secret scanner.

Saudi target: reconcile with KU-BO equivalents. Keep the stricter behavior, preserve adversarial tests, and expose one canonical implementation.

### AIM-016 — Skills catalog and agent routing

Source candidates: `catalog/skill-catalog.yaml`, donor `SKILL.md` files, and agent metadata.

Saudi target: publish narrow Saudi skills only after runtime parity passes. Skills route to canonical code; they must not duplicate business logic or overstate data access.

### AIM-017 — Active AI-Mincy PR lineages

Source candidates at inspection: stacked PRs #2–#4 and Core v2 PR #13.

Saudi target: inspect exact deltas and tests. Port resumability, daily research, controlled ingestion, adaptive no-single-provider orchestration, and quarantine behavior where unique and valid. Do not import stale Kuwait endpoints or assume Draft PR equals accepted behavior.

## Cross-cutting parity requirements

For each `AIM-*` item, record:

```text
SOURCE_REPOSITORY
SOURCE_SHA
SOURCE_PATHS
SOURCE_TESTS
TARGET_PATHS
IMPLEMENTATION_DECISION
SAUDI_ADAPTATION
TARGET_TESTS
FINAL_STATUS
ALLOWED_CLAIMS
BLOCKERS
```

No capability is lost merely because KU-BO already has a differently named implementation. In that case, prove equivalence and mark `SUPERSEDED_WITH_EQUIVALENCE`.
