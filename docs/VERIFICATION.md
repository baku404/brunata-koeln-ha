# Verification and release readiness

Reviewed: 2026-10-18. Local target: 1.0.0. Last deployed/verified build: 0.1.0.dev4 on Core 2026.10.2 / Python 3.14.6.

## Completed

- Authorized direct HTTPS login, protected-data verification, session/tenancy initialization and heating retrieval.
- UI setup and multiple development upgrades with existing entries, HA restart recovery and stable entity/statistic identities.
- Five live entities; native source unit/month, comparison and forecast provenance verified.
- Current-year actual monthly own/property statistics and daily distributions queried through Recorder. Actual month sums and daily-share totals agree; current forecasts stop at today.
- Display icons and precision verified in HA. No current projections in actual-only main sensors/statistics.
- Offline transport/parser/history/entity-interface/recorder-orchestration regression tests, including real local TLS, DST/leap years, duplicates, revised sums and forecast-to-actual replacement.

The 1.0.0 preparation additionally fixes forecast-only initial entity creation and uses a consistent refresh date for selection and allocation. This change is tested offline, not yet deployed.

## Known validation gaps

- User observation over multiple days and live actual-publication replacement; revision/replacement currently has offline coverage.
- Live session expiry, rejected credentials, reauthentication, outage recovery and deliberate unload/session-cleanup checks.
- Full automated tests against the real HA config-flow/coordinator/entity lifecycle. Current interface doubles are not full HA runtime tests.
- Public repository `mailskurz-bit/brunata-koeln-ha` is confirmed. CI, hassfest and HACS passed on commit 808e84d; see GitHub Actions for checks on later commits.
- Establish supported HA version range beyond the single tested target.

## Known limitations

- Water schemas are synthetic-tested only; the authorized account advertises heating.
- Selected tenancy/default billing period only. No explicit property/period selection or previous-year reconciliation.
- Missing months halt contiguous history imports. Source disappearance retains existing imported statistics pending review.
- Monthly data are not measured daily/hourly profiles. Forecast attribution is present on entity attributes; historical daily statistics contain reconciled allocations, not per-point provenance labels.
- No weather adjustment, costs, dashboard management or automatic Energy preference changes.

No credentials, account identifiers or private sample values are retained here. Release preparation does not authorize publication.

## Initial publication

The maintainer explicitly authorized initial public release on 2026-10-18 with the above limitations disclosed. CI and official hassfest/HACS validation passed after adding neutral heat brand assets and repository topics. Publication does not imply completion of the remaining live lifecycle/observation checks. No changes to the maintainer HA installation are made by publishing.
