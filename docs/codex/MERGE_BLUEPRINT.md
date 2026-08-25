# Saudi AI merger blueprint

## Architectural decision

The merger is asymmetric:

- KU-BO is the structural base because it already has a conventional Python package, schemas, configuration, tests, CLI, evidence/ledger separation, temporal checks, Corporate Action/status handling, packaging, and strict fail-closed behavior.
- AI-Mincy is a capability donor because it contains a broader catalog of task-oriented Skills and specialized workflows.
- The target is not a folder union. It is a KU-BO successor with verified AI-Mincy behavioral parity and Saudi market adapters.

## Why a direct Git merge is rejected

The repositories have unrelated histories, duplicate concepts, different layouts, incompatible market assumptions, and different instruction/control layers. A direct overlay would create duplicate CLIs, conflicting schemas, silent policy regressions, and untraceable provenance. Use a source lock plus staged import commits.

## Proposed target layout

```text
AGENTS.md
CODEX_START_HERE.md
README.md
pyproject.toml
.github/workflows/
config/
  markets/
    saudi/
    kuwait_legacy/
  sources/
  products/
docs/
  architecture/
  codex/
  provenance/
  source-policy/
schemas/
src/kubo/
  markets/
    base.py
    saudi/
    kuwait_legacy/
  capabilities/
  ...existing generalized KU-BO modules...
tests/
  fixtures/synthetic/
  migration/
  parity/
  saudi/
```

Keep the `kubo` Python namespace in v1 to preserve compatibility and reduce migration risk. Product branding and repository naming may be Saudi AI without forcing an immediate import-path rename.

## Import mechanics

1. Create clean temporary checkouts for exact locked SHAs.
2. Run untouched baselines.
3. Export selected source trees from exact commits, excluding `.git` and prohibited artifacts.
4. Import KU-BO first in one provenance-bound commit.
5. Port AI-Mincy capability slices one at a time after semantic comparison.
6. Put source repository, source SHA, source paths, transformation class, and target paths in machine-readable provenance records.
7. Preserve donor copyright/license notices. Stop on unclear publication rights.

Do not copy build artifacts, runtime outputs, caches, sessions, secrets, licensed data, or private evidence.

## Conflict-resolution rules

Use this priority when implementations conflict:

1. stricter evidence, temporal, privacy, and rights gate;
2. tested KU-BO contract and runtime behavior;
3. AI-Mincy unique capability behavior;
4. simpler maintainable implementation when behavior is equivalent;
5. compatibility wrapper for old entrypoints;
6. archive/deprecate rather than delete.

Never choose an implementation because it yields more recommendations, higher backtest results, or fewer blocked states.

## Saudi market architecture

`SAUDI_ADAPTER_SPEC.md` is the detailed implementation contract. The rules below are the architectural summary; any time-sensitive market value must be re-verified and effective-dated.

### Identity

Use effective-dated identities. Canonical joins require official security code and date-valid identity, with ISIN where available. Preserve symbol aliases only as provider mappings. Model Main Market/Nomu transitions, listing, suspension, resumption, and delisting explicitly.

### Time and calendar

Use `Asia/Riyadh`. All decision, availability, retrieval, session, and event timestamps must be timezone-aware. Session horizons use the official trading calendar, never civil-day shortcuts.

### Prices and benchmarks

Keep raw and adjusted prices separate. Record currency and units. Use `TASI` as the initial broad-market benchmark and an explicit Saudi sector benchmark where required. Never silently substitute `MT30`, `NomuC`, an ETF, or a vendor proxy.

### Corporate Actions

Model cash dividends, bonus shares, splits/consolidations, capital increases/reductions, rights issues, mergers, tender events, and complex actions with explicit terms and disposition. Absence of an observed action is not verified no-action coverage.

### Disclosures and financial events

Normalize issuer announcements, results, board/assembly events, dividends, capital actions, regulatory actions, status changes, and corrections. Preserve original, corrective, supplementary, and republished relationships. Use the actual availability time, not only the event date.

### Source hierarchy

1. Saudi Exchange and CMA official evidence.
2. Issuer filings and official investor-relations publications.
3. Licensed market-data or broker/vendor evidence within explicit rights.
4. Reputable secondary financial/news sources for corroboration.
5. Search, archives, forums, Telegram, and social content for routing/sentiment only.

One publisher group counts once even when exposed through multiple URLs or products.

## Capability-parity method

Parity is behavioral. For every donor capability, define representative inputs, expected governed outputs, blocked/error states, provenance requirements, and allowed claims. Run the donor test or a frozen behavioral fixture where legally and technically possible, then run the target implementation against the same contract.

Equivalence may be proven by an existing KU-BO capability. Duplicate code is not required. A filename copied without reachable, tested behavior does not count as parity.

## Model and factor governance

Create a canonical Factor Registry. Each factor needs definition, data role, authority, availability rule, freshness, transformation, missing-data behavior, direction, leakage tests, and version. A factor score is not a probability. Factor 9 remains a research asset until admission, lineage, rights, Point-in-Time, and validation gates pass.

## Release path

- v0.1: source lock, baseline, KU-BO import, control layer.
- v0.2: market abstraction and Saudi Main Market foundation.
- v0.3: AI-Mincy capability slices and parity suite.
- v0.4: unified CLI/skills and full synthetic end-to-end validation.
- v1.0 research release: only after exact-head CI, publication review, resolved visibility/rights, and explicit merge authority.

No version label implies real forecast accuracy, live operation, or suitability for real-money execution.
