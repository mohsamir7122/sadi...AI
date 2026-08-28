# Daily Saudi research operations

The active market is Saudi Exchange Main Market, with `SAR` and
`Asia/Riyadh`. Nomu remains a separate disabled adapter. The packaged workflows
cannot produce a production/source-backed claim. After separately governed
production issuer, schema, and trust extensions plus admitted evidence, they are
designed to emit source-bound research artifacts; they never place orders or
produce personalized buy instructions. Synthetic executions are behavioral
tests only and never support a production-evidence, model-validity, or
research-candidate claim.

## Externally scheduled 22:00 job — ten-year event laboratory

The CLI consumes a complete, supplied, receipt-bound Point-in-Time JSONL corpus
inside the latest ten-year window; it does not collect, build, or resume that
corpus. An external scheduler may invoke it at 22:00, but the CLI itself does
not enforce that wall-clock hour—it binds the supplied `--run-at` to the signed
execution contract. Its per-run denominator must include at least 50
`PRIMARY` events and 300 `PROBE` events, must reach the start of that window
within the configured tolerance, and must contain outcomes maturing near the
run cutoff. Eligible events include large price dislocations,
earnings/guidance, Corporate Actions, suspensions, governance, M&A, and legal
or regulatory developments.

The order is fixed:

1. Verify the receipt and its assertions, then validate structural/PIT identity,
   source-role/rights, timestamp lineage, and the cross-bindings of supplied
   denominator and Corporate Action PASS attestations. These checks do not
   independently recompute or prove official completeness.
2. Reject any factor whose `known_at` is later than its prediction cutoff.
   `NEXT_SESSION` labels must not be available before the admitted calendar's
   next trading session has ended, including its boundary uncertainty; a
   Thursday event cannot mature on the closed Friday/Saturday weekend.
3. Choose one pair of global chronological boundaries for all cohorts. Purge
   any training label or event evidence not known before validation starts and
   any validation label or event evidence not known before final holdout starts.
   Events sharing a prediction timestamp never cross a boundary; shuffling is
   forbidden.
4. Fit weights on training rows and calibrate them on validation rows.
5. Strip outcomes from final-holdout rows, generate predictions, and seal the
   packet and model fingerprints. Publish the model/prediction root first, then
   write labels to a disjoint restricted outcome-vault root; the nightly
   process creates that vault but does not score it.
6. In a separate process, open the outcome vault only after the seal verifies,
   a purpose-specific admission verifies, and its run binding matches the
   nightly report. Then report final-holdout metrics for intraday, next session,
   week, month, and year.

If a raw cohort minimum, ten-year coverage gate, or post-purge cohort minimum
fails, the published run report has status `STOP_TRAINING`; the current model is
not updated and no vault root is created. Admission, calendar, parsing, and
evidence-report validation failures raise an error before publication instead
of being relabeled as `STOP_TRAINING`. Historical returns are research
measurements, not a promise of future performance.

## Continuous open + 30 minutes + uncertainty — post-open research scan

The scan is permitted only on a trading session declared by the admitted
calendar revision and no earlier than thirty minutes after continuous trading
begins plus the revision's `boundary_uncertainty_seconds`. For example, when
continuous trading begins at `10:00:00`, a revision with 30 seconds of
uncertainty has an earliest governed scan time of `10:30:30`.
The uncertainty value is structurally capped at 300 seconds.
Every row needs an
effective-dated four-digit Saudi code, a configured model-use entitlement,
explicit latency, positive price/liquidity values, and Point-in-Time factors.
The governed maximum market-observation and factor age is 15 minutes, and the
candidate cap is 25 per horizon. This uniform factor-age rule is intentionally
conservative; per-factor freshness from `FactorDefinition` is not yet wired
into this command. Both operational paths require the same exact factor IDs on
every row and refuse silent zero-imputation, but neither currently resolves
`F9-*` IDs against `FactorRegistry`; nightly uses only a loose 370-day
structural ceiling rather than each definition's governed freshness, so
factor-specific freshness and registry lineage remain blockers. Observation codes must match the complete selectable set in
the supplied Point-in-Time identity master exactly once; missing, unexpected,
or duplicate codes cause `ABSTAIN` with
`INCOMPLETE_OBSERVATION_DENOMINATOR`.

Results are ranked separately for intraday, next session, week, month, and
year. Each result keeps its source and latency and sets `probability`,
`recommendation`, and `order` to null. Malformed fields, invalid rights,
nonpositive prices, empty factors, and malformed weights fail parsing before a
report is published. Structurally valid rows that fail scan-time freshness,
factor-set, or identity checks are rejected and produce `ABSTAIN` because the
admitted denominator becomes incomplete; session and identity gates also
abstain. The
liquidity floor is a selection filter rather than a data-completeness failure:
illiquid rows remain visible in `rejected`, and an otherwise complete scan may
rank the remaining eligible securities. If none meets the floor, it abstains
with `NO_SECURITIES_MEET_LIQUIDITY_FLOOR`.

## Data sources and storage

The official discovery registry is
[`research_sources.json`](../../config/markets/saudi/research_sources.json).
It includes Saudi Exchange historical reports, issuer announcements, market
data services, and Saudi CMA regulatory material. A URL is not an entitlement:
historical files and live/delayed feeds must pass access and rights review.

Receipt-bound runtime inputs and generated receipts belong under ignored
runtime storage, not Git. A receipt does not itself grant a legal entitlement.
No credentials, licensed market rows, private portfolio data, or outcome vaults
are committed.

## Runtime admission boundary

All three governed entry points verify purpose-specific admission v2 receipts.
The receipt uses an Ed25519 signature and is verified against public keys pinned
in the runtime trust store; there is no HMAC secret and no admission key read
from an environment variable. The signature covers the exact artifact hashes
and sizes, assertions, validity interval, purpose, and exact execution
contract, so a receipt for different files or command parameters fails closed.

The repository intentionally contains no production receipt issuer and no
production private signing key. Its built-in trust store currently contains only the
public synthetic test key with trust class `SYNTHETIC_ONLY`. The corresponding
private seed is public source code in the test helper under `tests/`; it provides
no hostile-caller authenticity and is not an operational issuer. A production deployment therefore needs a separately
governed issuer and reviewed code, schema, and trust-store extensions for its
production public key/trust class; the packaged verifier has no runtime
configuration hook for that today. Do not promote the built-in synthetic key,
copy the test private seed, or reinterpret a verified synthetic receipt as
production trust.

For `NIGHTLY_MODEL_USE`, the receipt must bind exactly the event JSONL,
effective-dated identity file, calendar revision, denominator report, and
Corporate Action report. Its execution contract binds the run ID/time and all
lookback, cohort-minimum, coverage-tolerance, maturity, and maximum-gap
parameters. The evidence reports must also cross-bind the run, admitted event
bytes, governed date coverage, event count, and the SHA-256 of the exact
identity-file bytes (the legacy field name is `security_set_sha256`);
their governed checks must pass.

For `POST_OPEN_MODEL_USE`, the receipt must bind exactly the observation JSONL,
identity file, calendar revision, and horizon weights, plus the scan time,
freshness, turnover, and candidate-limit parameters. Its denominator assertion
must be true, and the runtime independently requires one unique,
integrity-valid, fresh input observation for every selectable record in the
supplied identity bytes; the liquidity filter may then exclude a row from
candidates without making the data denominator incomplete. Both nightly and post-open
load the calendar revision from the bytes authenticated by their receipts.

For `HOLDOUT_SCORE`, a separate receipt must bind exactly the sealed prediction
packet, restricted outcome vault, and original nightly run report. Its
execution contract binds `run_id` and `scored_at`, and its assertions require
the packet seal, vault seal, and run binding to have been verified. The scorer
also rechecks the packet/vault internal digests, the nightly report binding,
and that the receipt was not issued before the packet's declared seal time.
Each sealed prediction retains `event_at` and a calendar-derived
`outcome_not_before` cutoff; scoring rechecks the vault label against that
sealed cutoff instead of reconstructing maturity from `prediction_at`.
The score report itself is not signed (`report_authenticated` remains false).
The scorer does not replay or verify the original `NIGHTLY_MODEL_USE` receipt
or its five original artifacts; it trusts structural fields in the newly bound
nightly report, so that report is not independently reauthenticated here.

Ed25519 verification establishes that the pinned key signed the bound bytes and
contract; it does not independently prove a source-authority decision, market
fact, entitlement, evidence completeness, rights assertion, or trustworthy
timestamp. A synthetic input, calendar, or admission remains synthetic after a
successful verification. Under the repository's current synthetic-only trust
store, holdout output is `SYNTHETIC_HOLDOUT_METRICS` and post-open output cannot
be promoted to a production research-candidate claim.

`PUBLIC_RESEARCH_ALLOWED` permits model fitting only inside this bounded,
non-production research workflow; it is not a deployment/commercial-use grant.
Licensed research data is rejected unless its exact grant is
`LICENSED_MODEL_USE`. These code-level distinctions do not replace legal or
contract review by the receipt issuer.

The calendar loader verifies revision-level declared coverage and knowledge
time for every event, but its weekday-plus-closures representation cannot independently detect
a missing holiday. Production needs an authoritative per-session inventory or
completeness manifest and reconciliation. A loaded revision also supplies one
schedule template across its covered interval rather than a historical revision
ledger or per-session availability history. A single backdated revision cannot
prove ten-year historical Point-in-Time calendar correctness. The supported
weekend regime begins on 2013-06-29; earlier coverage
fails closed. Calendar timestamps are canonical whole-minute `HH:MM:SS`, coverage is
bounded to 4,100 days, one declared closure is bounded to 62 days, and a
revision may declare at most 512 closures to keep receipt-bound input
processing finite. Admission also applies role-specific file-size ceilings
(8 MiB for calendar/reports/weights, 32 MiB for identity, and 128 MiB for
event/holdout data). Outcome rows similarly provide
precomputed excess returns: elapsed-day floors plus the calendar-aware
`NEXT_SESSION` end gate prevent known early-label cases, but the runtime does
not yet reconstruct every horizon from official session IDs and raw
security/benchmark/Corporate Action legs. Treat both gaps as blockers for an
official-calendar or real-backtest claim.

Factor observations are structural records in this release. Exact rights,
uniform factor-set, and temporal-cutoff checks are enforced, but runtime
registry membership, factor-specific nightly freshness, and registry evidence
lineage are not yet resolved by the commands; do not represent arbitrary
`F9-*` inputs as FactorRegistry-admitted.

The nightly evidence-report contracts are
[`saudi-denominator-report.schema.json`](../../schemas/saudi-denominator-report.schema.json)
and
[`saudi-corporate-actions-report.schema.json`](../../schemas/saudi-corporate-actions-report.schema.json).
The closed post-open output envelope is
[`saudi-post-open-report.schema.json`](../../schemas/saudi-post-open-report.schema.json);
do not detach candidate rows from that trust/status envelope.

## Commands

```bash
sadi-nightly \
  --events runtime/authorized/saudi-events.jsonl \
  --identity-file runtime/authorized/saudi-identity.json \
  --calendar-file runtime/authorized/saudi-calendar-revision.json \
  --denominator-report runtime/authorized/saudi-denominator-report.json \
  --corporate-actions-report runtime/authorized/saudi-corporate-actions-report.json \
  --admission-receipt runtime/authorized/saudi-nightly-admission.json \
  --run-id 2026-08-25-nightly \
  --run-at 2026-08-25T22:00:00+03:00 \
  --output-root runtime/runs/2026-08-25-nightly \
  --outcome-vault-output-root runtime/restricted-vaults/2026-08-25-nightly

sadi-holdout-score \
  --sealed-predictions runtime/runs/2026-08-25-nightly/sealed_predictions.json \
  --outcome-vault runtime/restricted-vaults/2026-08-25-nightly/outcome_vault.json \
  --run-report runtime/runs/2026-08-25-nightly/run_report.json \
  --admission-receipt runtime/authorized/saudi-holdout-score-admission.json \
  --run-id 2026-08-25-nightly \
  --scored-at 2026-08-25T22:00:00+03:00 \
  --output-root runtime/runs/2026-08-25-final-score

sadi-post-open \
  --observations runtime/authorized/saudi-open.jsonl \
  --weights runtime/runs/latest-nightly/horizon_weights.json \
  --identity-file runtime/authorized/saudi-identity.json \
  --calendar-file runtime/authorized/saudi-calendar-revision.json \
  --admission-receipt runtime/authorized/saudi-post-open-admission.json \
  --scan-at 2026-08-25T10:30:30+03:00 \
  --output-root runtime/runs/2026-08-25-open-plus-30
```

Each output directory is created atomically and never overwritten. For a
command to proceed, each output parent must already exist as a real,
non-symlink directory and every target path must be absent. For a
successfully prepared run, the nightly process preflights both roots, then
commits the model/prediction root before the restricted outcome-vault root. A
`STOP_TRAINING` run publishes only its report root. The successful-run roots are
separate publications, not one cross-root transaction; if vault publication
fails, a packet-only root can remain and must be treated as an incomplete,
recoverable run. Operators must retain both manifests and enforce
restricted-vault access.

The nightly/scoring boundary is process and storage-root separation, not an
independent label-custodian boundary. The nightly process sees outcomes while
creating the vault, and the governed input contract requires every outcome to
be mature by `run_at`. The split is therefore retrospective out-of-sample:
outcomes are withheld from the fitting function, but they are not prospectively
unknown at seal time. An independent custodian, independent timestamp, or blind
operator workflow must be supplied operationally if those stronger guarantees
are required. Only the CLIs may mark input admission authenticated because they
parse the exact receipt-bound bytes; lower-level in-memory library calls remain
structural and unauthenticated, including successful nightly preparation.
