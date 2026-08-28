# Saudi AI Research Engine

Saudi-first, auditable research infrastructure for Saudi Exchange Main Market
equities. The runtime keeps KU-BO's evidence, provenance, ledger, and
fail-closed discipline, while porting useful AI-Mincy ideas through reviewed
capability slices rather than duplicating competing engines.

## Current foundation

- Market: Saudi Exchange (`SAUDI_EXCHANGE`)
- Default segment: Main Market equities (`MAIN`)
- Currency and timezone: `SAR`, `Asia/Riyadh`
- Primary benchmark: `TASI`; `MT30` is an explicit Main Market alternative,
  while `NomuC` is Nomu-scoped and is rejected for a Main Market snapshot
- Identity: official Saudi security code plus effective-dated listing state and
  checksum-valid Saudi ISIN where supplied
- Evidence: official sources start as `DEFINED_ONLY`; an admission receipt binds
  configured artifacts and assertions but is not itself market evidence
- Nomu: separate and disabled by default
- Factor 9: definitions carry rights, Point-in-Time, freshness, and source
  metadata. `FactorRegistry.admit` currently enforces model-use rights,
  Point-in-Time-tested state, and `available_from` only; it does not enforce
  observation freshness or evidence lineage, and nightly/post-open do not use it
- Nightly laboratory: each daily run requires a ten-year-window corpus with at
  least 50 primary/300 probe events, explicit coverage gates, one global causal
  training/validation/final-holdout split, label-and-event-evidence purging, and
  sealed predictions
- Post-open scan: its earliest governed start is thirty minutes after the
  admitted calendar revision's continuous phase begins, plus boundary
  uncertainty, and it produces five-horizon research candidates only from
  a fresh receipt-bound observation for every selectable security in the
  supplied identity master

## Install and run the Saudi smoke tests

```bash
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests/saudi -v
```

The three governed operational entry points are:

```bash
sadi-nightly --help
sadi-holdout-score --help
sadi-post-open --help
```

Their row contracts are
[`saudi-nightly-event.schema.json`](schemas/saudi-nightly-event.schema.json) and
[`saudi-post-open-observation.schema.json`](schemas/saudi-post-open-observation.schema.json).
Runtime admission and calendar inputs are described by
[`saudi-admission-receipt.schema.json`](schemas/saudi-admission-receipt.schema.json)
and
[`saudi-calendar-revision.schema.json`](schemas/saudi-calendar-revision.schema.json).
Nightly denominator and Corporate Action evidence reports use
[`saudi-denominator-report.schema.json`](schemas/saudi-denominator-report.schema.json)
and
[`saudi-corporate-actions-report.schema.json`](schemas/saudi-corporate-actions-report.schema.json).
Post-open output envelopes use the closed
[`saudi-post-open-report.schema.json`](schemas/saudi-post-open-report.schema.json)
contract; candidate rows are not valid standalone reports because their trust
and claim boundary lives in the envelope.
The repository verifies admission receipts but contains no production issuer or
production private signing key. A publicly available deterministic synthetic
test seed exists under `tests/` and provides no hostile-caller authenticity.
Admission v2 uses Ed25519 signatures
verified against a pinned public-key trust store; no shared HMAC secret or
runtime key environment variable is used. The only key currently pinned in the
repository is explicitly `SYNTHETIC_ONLY`, so even a successfully verified
receipt remains synthetic and cannot support a production-evidence claim. Anyone
with the source test seed can issue another `SYNTHETIC_ONLY` receipt.
Production operation requires a separately governed issuer plus reviewed code,
schema, and trust-store extensions for a production key/trust class; the
packaged runtime has no configuration hook that can accept one today.

Every receipt binds exact artifact bytes and the purpose-specific execution
contract. Nightly admission covers events, identity, calendar, denominator,
and Corporate Action reports; post-open admission covers observations,
identity, calendar, and weights. Holdout scoring also requires a dedicated
`HOLDOUT_SCORE` receipt binding the sealed predictions, restricted outcome
vault, and nightly run report. Signature verification detects changes to those
bound inputs, but does not by itself prove source authority, rights,
completeness, market facts, or an independent timestamp. Generated reports are
not themselves signed. The scorer does not replay the original
`NIGHTLY_MODEL_USE` signature or its five original artifacts, so the bound
nightly report is not independently reauthenticated by the holdout step.

The nightly process publishes the sealed prediction/model root before the
restricted outcome-vault root, and a separate process performs scoring. This is
process and storage-root separation, not an independent label custodian: the
nightly process still creates the vault, and all required outcome labels are
already mature and known by `run_at`. “Holdout” here means outcomes are excluded
from model fitting; it is retrospective out-of-sample evaluation, not a
prospective blind test or proof that labels were unavailable when predictions
were sealed. Operators must enforce vault access controls. Publication across
the two roots is not transactional, so a vault
publication failure can leave a recoverable packet-only run that must not be
treated as complete.

The command-line entry points are the admission boundary because they parse
the exact bytes verified by each receipt. Lower-level Python objects are
structural research APIs and do not independently prove that arbitrary
in-memory values match receipt-bound artifacts; their direct nightly
preparation, candidate, and holdout results remain explicitly unauthenticated.

The repository contains no fabricated historical corpus and no embedded live
market feed. A nightly run stops without changing a model when either per-run
cohort, history coverage, or causal post-purge split is incomplete. Malformed,
rights-invalid, nonpositive-price, or malformed-weight post-open inputs fail
before publication; structurally valid rows that fail scan-time freshness,
factor-set, or identity checks produce `ABSTAIN` with an incomplete denominator.
Liquidity-only exclusions preserve completeness. Synthetic inputs and
synthetic calendar revisions exercise code behavior only: their statuses and
reports are not production research claims, verified market evidence, or proof
of forecast validity.

The rights vocabulary deliberately treats `PUBLIC_RESEARCH_ALLOWED` as usable
only for fitting inside this non-production research workflow; it is not a
production-deployment or commercial-use grant. Licensed material requires the
stronger `LICENSED_MODEL_USE` value—`LICENSED_RESEARCH_ALLOWED` is rejected by
model-use paths—and every run still requires the receipt's explicit model-use
assertion. A production legal/entitlement decision remains external.

Revision-level calendar knowledge and coverage boundaries are checked at each
historical prediction time, but the current revision format is a weekday template plus
listed closures, not a reconciled authoritative session inventory. A missing
holiday row cannot be detected from that file alone. One loaded revision also
contains only one schedule template for its covered interval, not a historical
ledger of rule/schedule or per-session publication history. A single backdated
revision therefore cannot prove ten-year historical Point-in-Time correctness.
Dates before the supported 2013-06-29
Friday/Saturday weekend regime fail closed. Likewise, supplied excess returns receive
elapsed-time floors and a calendar-aware next-session end gate, but are not
independently recomputed from start/end session IDs, raw security and benchmark
price legs, or Corporate Action records. Those completeness and recomputation gaps are why
the repository does not claim an official calendar, a real backtest, or
validated horizon performance.

The nightly and post-open paths require an exact, uniform factor set for every
row, so a missing factor is never silently scored as zero. They still do not
resolve factor IDs against `FactorRegistry`. Post-open applies its conservative
15-minute rule, while nightly applies a loose 370-day structural ceiling and
requires the factor to be known by its prediction cutoff. An arbitrary `F9-*`
identifier can therefore pass structural
parsing; registry membership, factor-specific nightly freshness, and registry
evidence-lineage resolution remain production blockers.

The engine is research infrastructure, not an order-execution system. It does
not claim live access, full-market coverage, forecast accuracy, or a validated
backtest from synthetic fixtures.

See [`DAILY_SAUDI_RESEARCH.md`](docs/operations/DAILY_SAUDI_RESEARCH.md) for the
externally scheduled laboratory and continuous-open-plus-thirty operating
contract.

## Sources and merger controls

Read [`CODEX_START_HERE.md`](CODEX_START_HERE.md) and the control documents in
[`docs/codex/`](docs/codex/) before contributing. Source snapshots and
capability provenance are pinned in
[`docs/provenance/SOURCE_LOCK.json`](docs/provenance/SOURCE_LOCK.json).
