# Saudi AI Research Engine

Saudi-first, auditable research infrastructure for Saudi Exchange Main Market
equities. The runtime keeps KU-BO's evidence, provenance, ledger, and
fail-closed discipline, while porting useful AI-Mincy ideas through reviewed
capability slices rather than duplicating competing engines.

## Current foundation

- Market: Saudi Exchange (`SAUDI_EXCHANGE`)
- Default segment: Main Market equities (`MAIN`)
- Currency and timezone: `SAR`, `Asia/Riyadh`
- Primary benchmark: `TASI`; `MT30` and `NomuC` are explicit named alternatives
- Identity: official Saudi security code plus effective-dated ISIN/listing state
- Evidence: official sources start as `DEFINED_ONLY`; access and rights require admission
- Nomu: separate and disabled by default
- Factor 9: admission requires rights, Point-in-Time testing, freshness, and evidence lineage
- Nightly laboratory: ten-year event study with daily 50-primary/300-probe gates,
  chronological training/validation/final-holdout splits, and sealed predictions
- Post-open scan: runs no earlier than 10:30 Riyadh time and produces five-horizon
  research candidates only from fresh, authorized observations

## Install and run the Saudi smoke tests

```bash
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests/saudi -v
```

The two governed operational entry points are:

```bash
sadi-nightly --help
sadi-post-open --help
```

Their input contracts are
[`saudi-nightly-event.schema.json`](schemas/saudi-nightly-event.schema.json) and
[`saudi-post-open-observation.schema.json`](schemas/saudi-post-open-observation.schema.json).
The repository contains no fabricated historical corpus and no embedded live
market feed. A nightly run stops without changing a model when either daily
cohort is incomplete; a post-open run abstains when fresh authorized data is
not available.

The engine is research infrastructure, not an order-execution system. It does
not claim live access, full-market coverage, forecast accuracy, or a validated
backtest from synthetic fixtures.

See [`DAILY_SAUDI_RESEARCH.md`](docs/operations/DAILY_SAUDI_RESEARCH.md) for the
22:00 laboratory and 10:30 post-open operating contract.

## Sources and merger controls

Read [`CODEX_START_HERE.md`](CODEX_START_HERE.md) and the control documents in
[`docs/codex/`](docs/codex/) before contributing. Source snapshots and
capability provenance are pinned in
[`docs/provenance/SOURCE_LOCK.json`](docs/provenance/SOURCE_LOCK.json).
