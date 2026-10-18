# Changelog

## [Unreleased]

- Replace the enlarged 16-pixel favicon with a high-resolution symbol adaptation and add the full portal logo for Home Assistant branding, with source attribution and separate third-party rights notices.

## [1.0.0] - 2026-10-18

Initial public release. See docs/VERIFICATION.md for verified scope and known limitations.

### Added

- Native async Cologne tenant-portal integration with UI setup, reauthentication and shared 24-hour polling.
- Actual monthly own consumption, property-average and percentage-deviation sensors.
- Separate average daily distribution entities and historical statistics for own/property values; current forecasts are replaced by actual monthly data.
- Current-year backfill, calendar-day allocation, stable identities, safe diagnostics, masked local checker and allowlisted release ZIP.
- Sensor icon defaults and three display decimals for derived values, retaining internal precision.
- CI plus official hassfest/HACS workflows and draft-only stable/prerelease packaging.

### Fixed during preparation

- Use browser-compatible cookies and initialize tenant context before protected consumption reads.
- Permit forecast-only daily entities on a first setup before the first actual month is published.
- Use one refresh date when selecting and distributing current-month forecasts.

### Validation

Live heating/setup/statistics verification applies to 0.1.0.dev4. Local 1.0.0 preparation is subject to the checks and release gates in docs/VERIFICATION.md. Water and broader HA compatibility are not claimed as live-verified.
