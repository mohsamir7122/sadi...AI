# Saudi integrity migration: v0.2 to v0.3

Version 0.3 is a breaking integrity release for the governed Saudi workflows.
Callers must migrate admission receipts and command-line invocations before
upgrading.

## Admission receipt v2

HMAC admission v1 and its environment-provided shared secret are no longer
accepted. Admission receipt v2 uses Ed25519 signatures and a pinned public-key
trust store. A receipt binds its purpose, execution contract, assertions, and
the exact bytes and sizes of every required artifact. No production issuer key
is shipped by the package; the repository's public tests include a deterministic
synthetic private seed that provides no hostile-caller authenticity.

The built-in key is explicitly `SYNTHETIC_ONLY`; it is suitable for fixtures
and integration testing, not production market evidence. Production use needs
an independently governed issuer plus reviewed code, schema, and trust-store
extensions; the packaged verifier does not accept a configurable production
key/trust class.

## Command-line changes

### `sadi-nightly`

In addition to the existing event and identity inputs, provide:

- `--calendar-file`
- `--denominator-report`
- `--corporate-actions-report`
- `--admission-receipt`
- a separate `--outcome-vault-output-root`

The receipt purpose must be `NIGHTLY_MODEL_USE`. It must bind the event,
identity, calendar, denominator-report, and corporate-actions-report bytes plus
the complete governed execution contract. The calendar must cover the ten-year
window, and the two evidence reports must agree on the run, input, coverage,
event count, and identity security-set hash.

### `sadi-holdout-score`

Provide the new inputs:

- `--run-report`
- `--admission-receipt`
- `--run-id`

The receipt purpose must be `HOLDOUT_SCORE` and must bind the sealed prediction
packet, outcome vault, and nightly run report. The scorer also verifies the
run ID, model fingerprint, packet seal, vault hash, and unscored nightly state
before computing metrics. The receipt must be valid at `scored_at`, its validity
window cannot exceed 24 hours, and its `issued_at` cannot precede the packet's
`sealed_at`.
The scorer does not replay or verify the original `NIGHTLY_MODEL_USE` receipt
or its five original artifacts; the newly signed holdout receipt binds the
nightly report, but does not independently reauthenticate its original chain.

### `sadi-post-open`

`--admission-receipt` remains required, but it must now be an Ed25519 v2 receipt
with purpose `POST_OPEN_MODEL_USE`. It binds observations, identity, calendar,
weights, and the scan parameters. HMAC key environment variables are ignored
and should be removed from deployment configuration. Market/factor age is now
bounded to 15 minutes and candidates to 25 per horizon. The receipt must assert
denominator completeness, and the observation codes must match every selectable
security in the supplied identity master exactly once.

## Status and claim boundaries

Successful governed CLI candidate/seal/metric outputs admitted by the packaged
synthetic key use explicit synthetic statuses, including
`SYNTHETIC_RESEARCH_CANDIDATES` and
`SYNTHETIC_SEALED_AWAITING_FINAL_SCORE` and
`SYNTHETIC_HOLDOUT_METRICS`; `ABSTAIN` and `STOP_TRAINING` remain failure/gate
statuses without a synthetic prefix. Cryptographic verification of a synthetic receipt
does not turn the result into authenticated market evidence. Generated reports
remain unauthenticated (`report_authenticated: false`) until a production trust
and publication layer is supplied.

Calendar revisions are point-in-time, coverage-bounded inputs. Nightly runs
also require complete denominator and reconciled corporate-action reports.
Missing, stale, inconsistent, or unbound evidence fails closed.
Calendar boundary uncertainty is limited to 300 seconds, canonical calendar
and CLI dates require `YYYY-MM-DD`, and a Nomu-scoped benchmark cannot be used
for the Main Market snapshot. Calendar phase times must be canonical
`HH:MM:SS`; revision coverage, individual closure intervals, and closure count
are bounded to 4,100 days, 62 days, and 512 rows respectively. Admission-bound
artifacts now have role-specific byte ceilings. Coverage before the supported
Friday/Saturday weekend regime on 2013-06-29 fails closed.
Knowledge is enforced at revision level only. The format has no historical
revision ledger or per-session publication history, so a single backdated
revision cannot prove ten-year calendar Point-in-Time correctness.

The calendar contract still represents a weekday template plus explicit
closures; it is not an independently reconciled official session inventory.
Outcome values are precomputed inputs with elapsed-time floors plus a required
calendar-aware next-session end gate, not returns independently rebuilt from
session and price legs. Version 0.3 therefore
does not establish official-calendar completeness or real-backtest readiness.

The holdout remains retrospective: its labels must already be mature at seal
time and are withheld from fitting, but the nightly process creates both the
packet and the separate vault. Packet-first publication across two roots is not
one transaction and is not an independent-custodian or trusted-timestamp
guarantee.

## Library API changes

The strict event and observation parsers and scanners now require a
`VerifiedSaudiAdmission`. In-memory values still cannot be proven to match the
receipt-bound artifact bytes, so direct successful library calls use
`UNAUTHENTICATED_SEALED_AWAITING_FINAL_SCORE`,
`UNAUTHENTICATED_RESEARCH_CANDIDATES`, or
`UNAUTHENTICATED_HOLDOUT_METRICS_COMPUTED`. Only the command-line boundaries
parse the exact verified bytes and may promote those structural results.

`prepare_nightly_run`, `build_temporal_split`, and
`seal_holdout_predictions` now require a `SaudiTradingCalendar`; they reject a
`NEXT_SESSION` outcome known before the next trading session's final phase plus
declared uncertainty. Sealed predictions retain the event-anchored maturity
cutoff so the separate scorer cannot weaken it back to the prediction time.
Training and validation rows are also purged when either their labels or their
event evidence were not known before the following boundary.
Fitted-model fingerprints and train/validation/holdout ID disjointness are
reverified at seal time. Verified admissions are verifier-registered,
non-copyable, non-serializable exact-class results rather than freely replaceable
dataclass containers. They remain reusable bearer results within the process;
there is no cross-process receipt-consumption or replay ledger.

Post-open observation factors must be an immutable tuple of governed records.
An empty selectable identity universe now returns
`EMPTY_OR_UNVERIFIED_UNIVERSE` with an incomplete denominator instead of being
misclassified as a successful complete denominator with no liquid securities.

Every event/observation must now provide the same exact factor-ID set expected
by its corpus/weights; missing factors are not silently treated as zero. Factor
observations nevertheless remain structural in v0.3: the commands do not yet
resolve arbitrary `F9-*` IDs through `FactorRegistry`. Rights and cutoff checks
still apply, and post-open uses a uniform 15-minute freshness ceiling, but
factor-specific registry freshness and lineage are not established.
