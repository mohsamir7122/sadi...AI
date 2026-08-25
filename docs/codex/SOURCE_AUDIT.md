# Source repository audit

This audit records the inspection-time architecture and merge risks. It does not replace the live Phase 0 refresh or `SOURCE_LOCK.json`.

## Structural conclusion

Use KU-BO as `KEEP_AND_BUILD`. Treat AI-Mincy as a selective capability donor. Do not use `git merge --allow-unrelated-histories`, copy either repository wholesale over the other, or preserve two competing engines.

### KU-BO

Observed main snapshot: `59833bf73510b3aa3901f628cbf2c13c0d01cf79`, tree `a4b56728aa4920f5578525f2736f17fbf4616151`.

Inspection found a conventional installable Python package, centralized `src/kubo`, CLI entrypoints, JSON Schemas, configs, CI, and a large central test suite. Its major systems cover source orchestration, runtime trust, request/report contracts, atomic outputs and reconciliation, effective-dated identity/calendar/prices, Corporate Actions/status, Point-in-Time factors, full-denominator decisions, forecast/outcome ledgers, replay, and data-foundation admission.

This makes KU-BO the single authority for core schemas, evidence, trust, ledgers, runtime, and packaging. Active PRs remain candidates, not accepted baseline, until Phase 0 classifies their ancestry, CI, and capability deltas.

### AI-Mincy

Observed main snapshot: `85044b681b7048ac373e47e31f6c2bfa7a885c9c`, tree `e4df4a97e96c7833eaa6891f562762f4af8f58ea`.

Inspection found a Skill-first repository with many independent scripts/tools, distributed tests, and no single central `src` package or `pyproject.toml`. Its distinctive donors include press/catalyst intelligence, Telegram authorization and structured-call diagnostics, authorized Investing.com export ingestion, resumable collection/publication, SQLite market storage, portfolio validation, monitoring, forecast/claim audit, training/walk-forward controls, market regime, momentum study, and cross-source detection queues.

AI-Mincy has a separate Core v2 PR lineage and a stacked PR lineage. Each must be audited per capability; no Draft PR or newest head is presumed accepted or complete.

## Overlap and root-of-trust risks

Both repositories implement evidence/provenance, source registries, receipts/signatures/hashes, Point-in-Time identity, Corporate Actions, historical prices, forecast/claim ledgers, backtest gates, scanning/ranking, research workflows, stop gates, secret scans, and synthetic fixtures.

Blind copying would create:

- two trust registries and receipt contracts;
- two evidence stores and competing roots of truth;
- incompatible schemas, success/failure states, and package/import conventions;
- a bypass where a weaker donor path can avoid a stricter KU-BO gate;
- deep Kuwait constants inside a supposedly Saudi runtime;
- optional Telegram/auth dependencies in the core security surface.

## Preliminary disposition rules

| Donor area | Preliminary disposition |
|---|---|
| KU-BO package, schemas, trust, evidence, ledgers, tests | `KEEP_AND_BUILD` |
| AI-Mincy Skill instructions | `REFERENCE_THEN_REWRITE` as thin Saudi wrappers after runtime parity |
| AI-Mincy source governance and receipts | `MAP_TO_EXISTING_KUBO_CONTRACTS`; retain the stricter behavior |
| AI-Mincy SQLite market store | `MIGRATE_OR_ADAPT`; never retain a second root of truth |
| Press, Telegram, Investing, and challenger providers | `PORT_AS_OPTIONAL_PROVIDER_ADAPTERS` |
| Resumability and inventory utilities | `PORT_GENERIC_CORE` where unique |
| Portfolio and monitoring | `PORT_AS_APPLICATION_WORKFLOWS` |
| Training and walk-forward | `QUARANTINE_UNTIL_DATA_FOUNDATION_PASSES` |
| Kuwait collectors, hosts, and allowlists | `KUWAIT_LEGACY_OR_ARCHIVE` |
| Historical scores/probabilities/backtest claims | `REJECT_AS_EVIDENCE`; behavior may be re-tested under current gates |
| AI-Mincy Core v2 and stacked open PRs | `AUDIT_SEPARATELY_BEFORE_SALVAGE` |

These are starting hypotheses. Phase 0/1 must replace them with exact source paths, tests, decisions, and evidence in the capability/provenance tables.
