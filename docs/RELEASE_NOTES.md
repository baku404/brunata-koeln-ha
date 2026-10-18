# BRUNATA-METRONA Cologne 1.0.0

Initial public release, authorized by the maintainer on 2026-10-18. See the verification record for the tested scope and remaining validation gaps.

Native Home Assistant integration for the Cologne tenant portal, using direct asynchronous HTTPS access without browser automation, MQTT or an extra app/container.

## Features

- Daily shared polling with isolated account sessions, UI setup and reauthentication.
- Five entities per fully supported medium: actual latest month, property average, own percentage deviation, own average daily distribution and property average daily distribution.
- Independent current-year historical statistics for actual own monthly consumption, property-average monthly consumption and both average daily distributions.
- Current-month forecasts supply daily distributions through today. Actual values replace forecasts for the same month; main monthly sensors remain actual-only.
- Stable identities, native units, calendar-day allocation, source provenance and safe diagnostics. Three display decimals for derived values preserve full internal precision.

## Verified scope and limitations

Heating and initial/repeated-upgrade startup have been live-tested on Core 2026.10.2 / Python 3.14.6. Water parsing has synthetic coverage but no live account verification. Only the selected tenancy/default billing period is supported. No measured daily/hourly profile, cost calculation, weather adjustment or automatic dashboard configuration is provided.

Day shares represent average daily distribution from monthly totals, not a measured profile. Current-year history stops at gaps rather than inventing zero consumption. Source disappearance does not automatically delete imported records. Cross-year corrections require the portal to expose the affected historical data; prior-year reconciliation is not implemented. Existing statistics remain after integration removal.

Full HA automated config-flow/lifecycle tests, extended observation and live forecast-to-actual publication/recovery checks remain known validation gaps. They are not claimed as completed by this release.

## Installation and upgrade

**Recommended: HACS custom repository.** Open HACS → three-dot menu → Custom repositories, paste `https://github.com/mailskurz-bit/brunata-koeln-ha`, select **Integration** and add it. Download **BRUNATA-METRONA Cologne**, restart Home Assistant, then add the integration under **Settings → Devices & services** and enter your portal credentials.

Future updates are available through HACS. Existing manual/development entries retain their entity/statistic identities and credentials; download through HACS over the existing files and keep the configured integration entry. Take a backup before upgrading.

Manual ZIP installation is a fallback only. See the [step-by-step installation guide](https://github.com/mailskurz-bit/brunata-koeln-ha#installation) and the verification record for limitations.
