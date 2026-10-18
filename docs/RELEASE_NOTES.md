# BRUNATA-METRONA Cologne 1.0.1

Branding and documentation update. Sensor behavior, authentication and historical-statistics logic are unchanged from 1.0.0.

## Changes

- Replace the enlarged low-resolution favicon with a high-resolution, transparent symbol adaptation in 256/512 pixels.
- Add the full portal wordmark and include all four icon/logo files in the release ZIP for Home Assistant's local branding support.
- Document image provenance and third-party brand rights separately from the standard MIT code license.
- Update repository links to baku404 and prioritize installation through a HACS custom repository.

## Installation and upgrade

In HACS, add `https://github.com/baku404/brunata-koeln-ha` as a custom repository of type **Integration**. Download **BRUNATA-METRONA Cologne** and restart Home Assistant. For a new setup, add the integration under **Settings → Devices & services** and enter your portal credentials.

Existing users can update through HACS without removing their configured integration. Entity identities, credentials and existing statistics are retained. Manual ZIP installation remains a fallback.

Local integration branding is supported by Home Assistant 2026.3 and later. HACS list-icon display depends on HACS branding support and caching; this release does not guarantee an icon in the HACS repository list.

## Validation and limitations

Release checks cover lint, formatting, offline tests, metadata, packaging and hassfest. This branding update has not been separately deployed to the maintainer's live instance. Heating was previously live-verified; water retains synthetic-only coverage. Existing limitations in the [verification record](https://github.com/baku404/brunata-koeln-ha/blob/main/docs/VERIFICATION.md) continue to apply.
