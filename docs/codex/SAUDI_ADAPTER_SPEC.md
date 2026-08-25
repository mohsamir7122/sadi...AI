# Saudi Exchange adapter specification

This is the implementation contract for the Saudi runtime. It is a planning artifact, not evidence that any source is currently accessible, licensed, complete, or live. Codex must re-verify every time-sensitive rule against the official source, record the effective date, and fail closed when evidence is missing.

## Initial product boundary

Until `SAI-DEC-004` is resolved, build and test:

- Main Market ordinary equities only for stock selection;
- `TASI` as the broad-market benchmark and the dated official sector index as the secondary benchmark;
- `SAR` and `Asia/Riyadh`;
- synthetic fixtures plus small recorded fixtures whose storage and redistribution rights are documented.

Keep Nomu, REITs, CEFs, ETFs, debt, derivatives, and tradable rights out of the selectable universe. Still model excluded instruments when they are required to interpret a Corporate Action. Nomu must be a separate, disabled-by-default policy profile.

## Adapter contracts

The market-neutral core must depend on explicit interfaces rather than Saudi- or Kuwait-specific modules:

```text
SecurityMasterProvider
MarketCalendarProvider
UniverseProvider
PriceHistoryProvider
BenchmarkProvider
DisclosureProvider
FinancialFactsProvider
CorporateActionProvider
SourceAuthorityProvider
```

Every historical query accepts `as_of` or `known_at` at the storage/query boundary. Loading today's table and filtering afterward does not satisfy Point-in-Time correctness.

Recommended Saudi modules under the actual KU-BO package root:

```text
markets/saudi/config.py
markets/saudi/security_master.py
markets/saudi/calendar.py
markets/saudi/universe.py
markets/saudi/prices.py
markets/saudi/benchmarks.py
markets/saudi/disclosures.py
markets/saudi/xbrl.py
markets/saudi/corporate_actions.py
markets/saudi/rules.py
markets/saudi/sources.py
```

## Identity and bitemporal model

Do not use the four-digit trading symbol as a permanent primary key. Model issuer, security, and listing separately. Each security/listing record needs:

- stable internal `issuer_id` and `security_id`;
- official Saudi Exchange symbol and ISIN;
- Arabic and English legal/trading names;
- segment and instrument type;
- currency, sector, industry, listing/status intervals, nominal value, shares outstanding, and free float where supported;
- prior names/symbols and provider aliases;
- parent linkage for temporary tradable-right instruments.

Required temporal/provenance fields:

```text
valid_from, valid_to
known_from, known_to
published_at, observed_at, ingested_at
source_id, source_url, content_hash, parser_version
```

An IPO joins no earlier than its first actual trading session. Suspended securities remain members with `tradable=false`. Delisting and Nomu-to-Main transfer are dated state transitions, not deletion or creation of a new issuer. Never backfill today's sector or index membership into history.

Official reference: [Saudi Exchange eReference Data](https://www.saudiexchange.sa/wps/portal/saudiexchange/trading/market-services/market-information-services/ereference-data?locale=en).

## Calendar, sessions, and information cutoffs

- Use `Asia/Riyadh`; do not apply daylight-saving adjustments.
- The normal trading week is Sunday through Thursday. Friday and Saturday are closed.
- Import dated official holiday schedules; never infer Eid closures algorithmically.
- Version all session schedules by effective date.
- Preserve exact Gregorian publication timestamps in Riyadh time. A Hijri date is display metadata only.
- An item is usable only when `published_at` is before the run's configured information cutoff plus any modeled operational latency.
- After-close information becomes usable only at the next modeled execution opportunity. Date-only evidence must never be assumed known before the open.

At package creation, the published equity sequence was opening auction 09:30–10:00, continuous trading 10:00–15:00, closing auction 15:00–15:10, and trade-at-last 15:10–15:20. This is a dated observation, not a timeless constant; Codex must verify it before implementation. Official reference: [Trading cycle and times](https://www.saudiexchange.sa/wps/portal/saudiexchange/rules-guidance/capital-market-overview/trading-cycle-and-times).

## Prices, benchmarks, and trading rules

Store immutable raw OHLC, official close, volume, value, and trade count separately from adjusted-price and total-return series. Preserve source latency class (`REAL_TIME`, `DELAYED`, or `END_OF_DAY`) and keep negotiated deals separate.

Model and effective-date:

- the official close and no-auction/no-trade fallback;
- session and settlement rules;
- tick sizes and valid price grids;
- normal, IPO, segment-specific, and static/dynamic price limits;
- suspensions, limit locks, queues, liquidity, costs, fees, and slippage.

At package creation, Saudi equities used `T+2`; Main Market IPOs had a special first-three-trading-day price-limit regime; and a new tick-size schedule had taken effect on 29 June 2025. These facts must be re-verified and stored as effective-dated rules rather than literals spread through the code. Official references: [Equity services](https://www.saudiexchange.sa/wps/portal/saudiexchange/trading/market-services/equities?locale=en), [Closing auction and trade-at-last](https://www.saudiexchange.sa/wps/portal/saudiexchange/rules-guidance/capital-market-overview/closing-auction-and-trade-at-last?locale=en), and [tick-size amendment](https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/issuer-news/news-detail-wcm/?locale=en&newsId=8897).

## Corporate Actions

Normalize cash/special dividends, bonus shares, rights issues and tradable rights, splits/consolidations, nominal-value changes, capital increases/reductions, repurchases/treasury shares, mergers/share swaps, listings/transfers, suspensions/resumptions, and delistings.

Keep each lifecycle date independently: recommendation, CMA approval, assembly approval, eligibility/record date, ex/reference-price date, subscription/trading period, deposit, payment, and effective listing date. Corrections and addenda create revisions; they do not overwrite the historical record.

Raw prices are never overwritten. Price-return and total-return adjustments remain separate. Unknown or conflicting material action terms set `adjustment_pending` and block affected returns/backtests. Reconcile calculated adjusted reference prices to official values within one valid effective-dated tick. Official reference: [Saudi Exchange Corporate Actions](https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/issuer-financial-calendars/corporate-actions).

## Disclosures, financial facts, and corrections

The normalized disclosure record needs official announcement ID/URL, symbol and ISIN, exact publication time, bilingual headline/body, category/event taxonomy, attachments and SHA-256 hashes, fiscal period, event-effective date, audit/review state, revision relationship, and parser version.

Deduplicate by official ID, language relationship, and attachment hashes—not headline similarity. Link originals, addenda, corrections, and cancellations. Version financial-reporting deadline rules; Main Market and Nomu requirements are not interchangeable and can change. The CMA continuing-obligations page recorded a modification on 19 January 2026 when this plan was written, so it must not be encoded as timeless policy.

Official references: [Issuer announcements](https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/issuer-news/issuer-announcements), [historical reports](https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/reports-publications/historical-reports), [market reports](https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/reports-publications/market-reports), [financial deadlines](https://www.saudiexchange.sa/wps/portal/saudiexchange/rules-guidance/capital-market-overview/Restrictions-Periods-and-Financials-Deadline), and [CMA continuing obligations](https://cma.gov.sa/en/RulesRegulations/Regulations/Pages/details.aspx?code=111).

## Source authority and rights

Default every source capability to `DEFINED_ONLY`. Admission requires documented authority tier, fields/roles, access method, latency, timezone, license/redistribution limits, independence group, parser version, freshness, and failure policy.

Evidence priority:

1. licensed Saudi Exchange feeds/eReference and official Exchange reports;
2. Saudi Exchange announcements, XBRL, Corporate Actions, and company profiles;
3. CMA rules, approvals, sanctions, and notices;
4. Edaa and Muqassa official records where applicable;
5. issuer annual reports and official Investor Relations releases;
6. SAMA, GASTAT, Ministry of Finance, and other official macro sources;
7. authorized vendor/user exports as corroboration or gap fillers;
8. reputable news;
9. forums, Telegram, and social media for routing/sentiment only.

A secondary source cannot silently override an official filing, price, status, or Corporate Action. Delayed website data is never labeled live. Official reference: [Saudi Exchange market data services](https://www.saudiexchange.sa/wps/portal/saudiexchange/trading/market-services/market-information-services/market-data).

## Mandatory fixtures

Create immutable raw snapshots plus expected normalized outputs for:

- stable and changed symbol/ISIN/bilingual identities;
- Nomu-to-Main transfer, IPO, suspension, resumption, and delisting;
- a tradable right linked to its parent;
- a normal session, weekend, Founding Day, National Day, and an officially published Eid closure;
- announcements immediately before open, intraday, in the closing auction, and after close;
- tick boundaries before and after a schedule change;
- Main IPO days one through four and separate Nomu price-limit behavior;
- closing-auction trade, no-auction fallback, no-trade fallback, and negotiated-deal exclusion;
- cash dividend, bonus, rights, split, capital reduction, and merger;
- original/addendum/correction, bilingual duplicates, and XBRL facts;
- late reporting followed by suspension;
- schema drift, empty/throttled responses, malformed PDF/XBRL, and source outage;
- replay of an old `as_of` after a later correction.

## Mandatory bias and adversarial controls

Tests must detect look-ahead, announcement-timestamp leakage, survivorship, current-universe/current-sector leakage, revised-XBRL/restatement leakage, Corporate Action and total-return errors, stale/non-trading prices, unachievable closing fills, limit locks/queues/liquidity/costs, IPO special limits, Main/Nomu mixing, symbol/name mapping errors, duplicate disclosure inflation, fiscal-calendar differences, macro revisions, multiple testing/overfitting, and missing suspended/delisted securities.

The decision layer returns `ABSTAIN` when coverage, authority, causality, identity, Corporate Action, or denominator integrity fails.

## Saudi definition of done

The adapter passes only when:

- active Saudi paths contain no Kuwait currency, timezone, endpoint, identity, calendar, or provider assumption;
- a dated official Main Market snapshot reconciles one unique symbol–ISIN mapping per active ordinary equity;
- identity, membership, session, rule, and source changes are effective-dated;
- raw price and announcement coverage reconcile to sampled official totals;
- adjustment outputs reconcile to official reference prices within one valid tick;
- deliberately injected future data is rejected;
- frozen evidence and configuration hashes reproduce historical runs;
- delayed data is labeled, Main/Nomu is isolated, and undocumented scraping/redistribution is absent;
- tests cover multiple size/sector profiles, an IPO, suspension, and complex Corporate Action;
- failed evidence gates yield `ABSTAIN`/blocked outputs, never fabricated confidence;
- no result is called a validated forecast before prospective paper forecasting and walk-forward evaluation pass.
