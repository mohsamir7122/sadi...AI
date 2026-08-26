# Daily Saudi research operations

The active market is Saudi Exchange Main Market, with `SAR` and
`Asia/Riyadh`. Nomu remains a separate disabled adapter. These workflows
produce source-backed research candidates; they do not place orders or produce
personalized buy instructions.

## 22:00 — ten-year event laboratory

Each run builds or resumes an authorized Point-in-Time corpus from the latest
ten years. The daily denominator must include at least 50 `PRIMARY` events and
300 `PROBE` events. Eligible events include large price dislocations,
earnings/guidance, Corporate Actions, suspensions, governance, M&A, and legal
or regulatory developments.

The order is fixed:

1. Verify official Saudi identity, source authority/rights, timestamp lineage,
   complete price denominator, and Corporate Action adjustments.
2. Reject any factor whose `known_at` is later than its prediction cutoff.
3. Split each cohort chronologically into 60% training, 20% validation, and 20%
   final holdout. Shuffling is forbidden.
4. Fit weights on training rows and calibrate them on validation rows.
5. Strip outcomes from final-holdout rows, generate predictions, and seal the
   packet and model fingerprints.
6. Open the separate outcome vault only after the seal verifies, then report
   final-holdout metrics for intraday, next session, week, month, and year.

If either cohort minimum or any evidence gate fails, status is
`STOP_TRAINING`; the current model is not updated. Historical returns are
research measurements, not a promise of future performance.

## 10:30 — post-open research scan

The scan is permitted only on an official Saudi trading session and no earlier
than thirty minutes after continuous trading begins. Every row needs an
effective-dated four-digit Saudi code, a configured research-use entitlement,
explicit latency, positive price/liquidity values, and Point-in-Time factors.
The default maximum market-observation age is 15 minutes.

Results are ranked separately for intraday, next session, week, month, and
year. Each result keeps its source and latency and sets `probability`,
`recommendation`, and `order` to null. Missing or stale authorized market data
causes `ABSTAIN`.

## Data sources and storage

The official discovery registry is
[`research_sources.json`](../../config/markets/saudi/research_sources.json).
It includes Saudi Exchange historical reports, issuer announcements, market
data services, and Saudi CMA regulatory material. A URL is not an entitlement:
historical files and live/delayed feeds must pass access and rights review.

Raw authorized inputs and generated receipts belong under ignored runtime
storage, not Git. No credentials, licensed market rows, private portfolio data,
or outcome vaults are committed.

## Commands

```bash
sadi-nightly \
  --events runtime/authorized/saudi-events.jsonl \
  --run-id 2026-08-25-nightly \
  --run-at 2026-08-25T22:00:00+03:00 \
  --output-root runtime/runs/2026-08-25-nightly

sadi-post-open \
  --observations runtime/authorized/saudi-open.jsonl \
  --weights runtime/runs/latest-nightly/horizon_weights.json \
  --scan-at 2026-08-25T10:30:00+03:00 \
  --output-root runtime/runs/2026-08-25-open-plus-30
```

Output directories are created atomically and never overwritten.
