# BRUNATA-METRONA Cologne for Home Assistant

Independent community integration for the [Cologne tenant portal](https://online.brunata-koeln.de/legacy/login). Not affiliated with BRUNATA-METRONA or Home Assistant.

**Version 1.0.0.** Heating is live-verified on Home Assistant Core 2026.10.2 / Python 3.14.6. The maintainer test instance was last verified on 0.1.0.dev4. Review the [verification record and known gaps](docs/VERIFICATION.md).

## Sensors

Up to five entities are created per advertised medium:

| Entity | Meaning |
| --- | --- |
| Latest reported month | Latest actual completed-month consumption |
| Property average | Actual average per tenancy for the same month |
| Deviation from property average | Own consumption relative to that average, in percent |
| Average daily distribution | Monthly own value divided by calendar days |
| Property average daily distribution | Monthly property average divided by calendar days |

Heating uses kWh; water retains its source volume unit. Missing values do not become zero. Comparison entities require supported comparison data. Percentage deviation is unavailable when the average is zero. Derived values display three decimals while internal precision is retained.

The daily entities use a current-month portal forecast when available and expose `data_basis: forecast` or `actual`, the source month, monthly value and allocation method. They represent **average daily distribution** (Durchschnittliche Tagesverteilung), not measured daily consumption. The three main entities remain actual-only. Weather adjustment and other portal display transformations are not requested.

## History and Energy

One shared coordinator fetches data every 24 hours using direct asynchronous HTTPS. No browser runtime, MQTT broker or separate app/container is needed. Transient HA retry behavior and manual refresh/reload may trigger additional requests.

On setup, upgrades and daily refresh, current-year readings are reconciled into four separate external statistics:

| Statistic ID suffix | Content |
| --- | --- |
| Original medium ID | Actual own monthly consumption |
| `_daily_average` | Own average daily distribution |
| `_property_average` | Actual property-average monthly consumption |
| `_property_daily_average` | Property average daily distribution |

Monthly statistics book the value in the month's final hour. Daily statistics distribute the month equally across calendar days, including leap years and DST days. Past day shares are booked in the day's final hour; today's provisional share is booked at local midnight, never at a future timestamp. There is no measured hourly profile.

Forecast daily shares extend only through today. Daily reconciliation updates revised forecasts; actual values replace the same month's provisional points and subsequent sums. Actual monthly statistics never contain projections. Stable IDs/timestamps prevent repeated fetches from adding duplicate consumption. Independent prior-year closing sums provide baselines; previous-year corrections are not reconciled automatically.

Use one own-consumption statistic in the Energy dashboard, not both monthly and daily series. Heating in kWh can be selected in its Gas section as a display choice for district heat, without converting to gas volume. Property-average statistics are comparisons and must not be added to own total consumption. The integration never modifies dashboard/Energy preferences automatically. Normal entity history and imported external statistics are separate; use statistic cards for the historical series.

## Installation

Manual: copy `custom_components/brunata_koeln` into HA's `config/custom_components/` and restart. Add **BRUNATA-METRONA Cologne** in **Settings → Devices & services**. Enter credentials only in HA's setup form; they are stored in its config entry. Protect configuration and backups.

Add `mailskurz-bit/brunata-koeln-ha` as a HACS custom repository of type Integration, then install and restart. The release provides a HACS-compatible integration ZIP. See the GitHub Actions results for the current validation status.

Before upgrades, take a backup. Existing development entity/statistic IDs are preserved; no credential migration or integration removal is required. Compare the source month/value with the portal after setup. Removing an entry does not delete its imported statistics.

## Limitations

- Cologne tenant accounts only; Munich SAP and international Brunata Online are different services.
- Only the portal-selected tenancy/default billing period. No explicit multi-property/period selection.
- Heating is live-tested; cold/hot water have synthetic coverage only.
- Gaps stop contiguous history import instead of fabricating zero consumption. Disappearing source data do not automatically delete existing records.
- Historical prior-year corrections require additional reconciliation not implemented here.
- No measured daily/hourly usage, cost estimates, weather adjustment or historical per-point forecast provenance labels.
- CAPTCHA or required portal review must be completed interactively. No automatic challenge solving or terms acceptance.

## Development checks

Use Python 3.14 for target HA work; standalone tests also run on Python 3.12.

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -t . -v
python scripts/validate.py --release-tag v1.0.0
python -m ruff check .
python -m ruff format --check .
python scripts/package.py
```

Fixtures are synthetic. Local real-HTTPS tests use a test CA and never portal credentials. Interface doubles verify entity/recorder orchestration but are not a full HA test harness. CI includes official hassfest and HACS validation; their successful GitHub execution is reported under the repository Actions tab.

## Troubleshooting and security

`python scripts/check_portal.py --preflight` checks public login markup without credentials. The interactive checker uses masked/hidden password input, never command-line secrets. Diagnostics expose bounded stages/status/counts, not raw responses, cookies, tokens or account details. Do not upload raw HAR files or private pages.

The legacy backend requires browser-style cookie transmission and tenant context initialization; a redirect or cookie count alone does not prove authentication. Rejected credentials/interactive challenges stop login retries; temporary outages follow HA's normal update retry behavior.

See [architecture](docs/ARCHITECTURE.md), [transport contract](docs/TRANSPORT_CONTRACT.md), [verification](docs/VERIFICATION.md), [release process](docs/RELEASING.md), [contributing](CONTRIBUTING.md) and [security](SECURITY.md). MIT license: [LICENSE](LICENSE).
