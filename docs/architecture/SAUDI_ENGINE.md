# Saudi engine architecture

The active path is deliberately layered:

1. `src/kubo` remains the KU-BO compatibility namespace and owns evidence,
   ledgers, strict parsing, runtime trust, and packaging.
2. `src/kubo/markets/saudi` owns Saudi Exchange identity, sessions, benchmarks,
   source authority, and market rules.
3. `src/kubo/saudi_capabilities` owns reviewed workflow contracts adapted from
   AI-Mincy: Factor 9 admission, resumability, context scanning, portfolio
   structure checks, and fail-closed claim audits.

The Saudi adapter is Main Market first. A four-digit official code and
effective-dated identity are required for joins; a ticker is only a display or
provider alias. Every historical request has both `as_of` and `known_at`.

Official sources are declared but begin as `DEFINED_ONLY`. A URL in the source
catalog does not grant access, freshness, model-use rights, or redistribution
rights. Delayed and end-of-day observations remain explicitly labeled.

The system can produce a context lead or a structural validation result. It
cannot call those outputs recommendations, probabilities, accuracy, live
feeds, or execution readiness.
