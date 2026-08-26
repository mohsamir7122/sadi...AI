# CURRENT TASK — SAI-MERGE-001

```text
TASK_ID: SAI-MERGE-001
STATUS: IN_PROGRESS
REPOSITORY: mohsamir7122/sadi...AI
EXPECTED_TASK_BRANCH: codex/saudi-engine-merger-v1
EXPECTED_PR_MODE: DIRECT_OR_REVIEW_PR_AFTER_GATES
MERGE_ALLOWED: YES_AFTER_GATES_PER_SAI-DEC-006
FORCE_PUSH_ALLOWED: NO
PERMANENT_DELETE_ALLOWED: NO
SOURCE_REPOSITORY_WRITE_ALLOWED: NO
REAL_MARKET_DATA_COMMIT_ALLOWED: NO
PRIVATE_SOURCE_PUBLICATION_ALLOWED: SELECTED_IMPLEMENTATION_ONLY_PER_SAI-DEC-003
REAL_BACKTEST_ALLOWED: YES_WITH_AUTHORIZED_POINT_IN_TIME_DATA
LIVE_TRADING_ALLOWED: NO
```

## Mission

Create a tested Saudi-first successor to KU-BO in the target repository. Preserve KU-BO as the runtime/package/evidence foundation, port or reimplement useful non-duplicate AI-Mincy capabilities, isolate Kuwait-specific behavior, and prove migrated behavior with contracts and tests. Publish and merge after the applicable gates pass under SAI-DEC-006.

Recorded authority is in `docs/codex/USER_DECISIONS.md`; the final publication
record follows `docs/codex/HANDOFF_TEMPLATE.md`.

## Execution sequence

Continue phase to phase without asking about ordinary engineering choices. Pause only at an explicit decision boundary or genuine external blocker.

### Phase 0 — orientation and immutable source lock

1. Run `gh auth status`; verify read access to target, KU-BO, and private AI-Mincy. Stop with the exact smallest authentication/access fix if any check fails; do not change visibility as a workaround.
2. Verify target remote, visibility, `main`, control-package presence, working tree, and CI. Create/resume `codex/saudi-engine-merger-v1` from the exact verified target `main` containing this control package.
3. Fetch both source repositories without modifying them.
4. Inspect every open source PR, ancestry, CI, governing instructions, tests, and capability delta.
5. Classify each open PR as `INCLUDE`, `PORT_SELECTED`, `SUPERSEDED`, `STALE`, `CONFLICTING`, or `OUT_OF_SCOPE`, with evidence.
6. Choose the KU-BO structural snapshot using the latest coherent validated lineage, not simply the newest timestamp.
7. Choose AI-Mincy donor snapshots per capability. Do not assume one branch contains all donor work.
8. Write `docs/provenance/SOURCE_LOCK.json` with repository, visibility, exact commit, tree hash, selected branch/PR, selection reason, parent lineage, and inspection timestamp.
9. Run source baseline tests on untouched checkouts and record exact commands, counts, failures, environment, and duration.

Exit: source lock, open-PR disposition, and reproducible baseline reports exist. No implementation import occurs before this exit.

### Phase 1 — import the KU-BO engineering spine

1. Import the selected KU-BO snapshot into the target while preserving target control files.
2. Keep `src/kubo` as the compatibility namespace during v1; do not perform a gratuitous package rename.
3. Exclude source `.git`, runtime artifacts, caches, secrets, private IDs, and policy-forbidden data.
4. Add an import manifest mapping target paths to the KU-BO source SHA.
5. Reconcile `pyproject.toml`, CI, license/attribution, `.gitignore`, and security rules.
6. Make the imported baseline compile and pass the recorded KU-BO test baseline before adding Saudi behavior.

Exit: target reproduces the selected KU-BO code-and-test baseline, with documented exceptions and no Saudi claim yet.

### Phase 2 — introduce a market-adapter boundary

1. Identify all hard-coded Kuwait assumptions: timezone, currency, exchange names, source IDs, security identity, calendars, benchmarks, sectors, Corporate Actions, disclosure types, product IDs, paths, and report text.
2. Define market-neutral interfaces for universe, identity, calendar, price history, benchmarks, disclosures, Corporate Actions, status history, financial statements, ownership/flow, and source authority.
3. Move still-needed Kuwait behavior behind `markets/kuwait_legacy` or equivalent, disabled from Saudi defaults.
4. Preserve backward compatibility only where tested and low-risk; do not let legacy behavior contaminate Saudi evidence or confidence.

Exit: generic contracts are tested and active defaults no longer require Kuwait providers.

### Phase 3 — build the Saudi foundation

Implement the initial Saudi adapter against `SAUDI_ADAPTER_SPEC.md`, including:

- `SAR` and `Asia/Riyadh`;
- Main Market universe and effective-dated identity;
- official security code, symbol, ISIN, issuer, sector, listing/status intervals;
- official session calendar and non-trading/suspension states;
- `TASI` and explicit sector benchmarks;
- Saudi Corporate Actions and adjusted/raw basis separation;
- Saudi Exchange issuer announcements, financial calendars, historical/market reports, CMA regulatory evidence, and issuer IR roles;
- an authority/freshness/rights registry that defaults every unproven source to `DEFINED_ONLY`;
- synthetic and minimal recorded-authorized fixtures only.

Effective-date every session, price-limit, tick-size, financial-deadline, and segment rule. Do not turn package-creation observations into timeless literals.

Nomu remains disabled unless `SAI-DEC-004` authorizes first-release coverage and its own contracts pass.

Exit: Saudi synthetic end-to-end research run works without any Kuwait source or assumption.

### Phase 4 — port AI-Mincy capabilities in governed slices

Enforce the path-level publication guards in approved `SAI-DEC-003`. For each `AIM-*` row in `CAPABILITY_MATRIX.md`:

1. compare donor behavior with existing KU-BO behavior;
2. select `REUSE_KUBO`, `PORT`, `REIMPLEMENT`, `COMPOSE`, or `ARCHIVE_CONTEXT`;
3. import the smallest coherent behavior, not an entire duplicate skill tree;
4. adapt market-specific logic to Saudi interfaces;
5. add provenance, contract, unit, adversarial, and parity tests;
6. update the matrix status and evidence;
7. commit a coherent capability slice.

Exit: every AI-Mincy capability is `PARITY_PROVEN`, `SUPERSEDED_WITH_EQUIVALENCE`, or `BLOCKED` with a precise external reason. `NOT_REVIEWED` is not an acceptable final state.

### Phase 5 — unified workflows and Codex skills

1. Provide one canonical CLI and library path for research, scanning, monitoring, historical pipeline, dataset preparation, backtest audit, and portfolio validation.
2. Keep `research_network` separate from strict `validated_forecast`.
3. Package repeated user-facing workflows as narrow repository skills only after the underlying code is stable.
4. Remove duplicate entrypoints by deprecation/compatibility wrappers, not deletion.
5. Document inputs, outputs, evidence classes, allowed claims, and blocked states.

Exit: one discoverable interface reaches all proven capabilities without ambiguous duplicate commands.

### Phase 6 — full validation and adversarial review

Run all applicable gates in `ACCEPTANCE_GATES.md`, including:

- source baseline comparison;
- compile, format/lint if configured, schema and strict JSON checks;
- full unit, integration, migration, parity, and adversarial suites;
- secret/privacy/publication scan;
- package build, isolated install, installed CLI smoke;
- deterministic replay on synthetic fixtures;
- Saudi end-to-end synthetic run;
- repository-wide scan for active Kuwait leakage;
- `/review` or equivalent dedicated diff review.

Complete `REVIEW_CHECKLIST.md` with evidence on the exact proposed PR head.

Exit: all applicable gates pass, or final status is `PARTIAL/BLOCKED` with no overclaim.

### Phase 7 — publication boundary

1. Push `codex/saudi-engine-merger-v1` without force.
2. Include source lock, capability results, exact tests, claims/non-claims, open decisions, and known limitations in the publication record.
3. Write the final handoff under `docs/codex/handoffs/SAI-MERGE-001-result.md`.
4. Merge into `main` only when applicable local and remote checks pass; never force push.

## Done when

The task is complete only when every applicable acceptance gate passes, every donor capability has a final disposition with evidence, the Saudi synthetic pipeline works through the installed package, CI is green on the exact Draft PR head, and no private/publication decision is crossed without approval.
