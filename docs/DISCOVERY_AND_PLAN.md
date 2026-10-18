# BRUNATA-METRONA Cologne: discovery and implementation plan

> Historical discovery record from before implementation. Statements below about untested login, unknown routes and proposed approval reflect that stage only. For current behavior and verification, use [transport contract](TRANSPORT_CONTRACT.md) and [verification status](VERIFICATION.md).

Research date: 2026-10-18. Status: proposal awaiting user approval. No integration code has been created or modified. Public reference source copies are kept separately under `work/research`; they are not project implementation files. The user will configure the VS Code workspace.

## Decision

Build a small native Home Assistant custom integration with a dedicated Cologne HTTP client, subject to confirming authenticated data endpoints. Prefer structured JSON/API responses, then server-rendered HTML over HTTP if necessary. Use browser automation only if the actual authentication or data transport requires it.

None of the four reviewed projects demonstrates working Cologne support. Their reusable value is architectural and semantic; their authentication and endpoint implementations must not be assumed compatible with Cologne.

## Repository assessment

Repository metadata was retrieved through GitHub's public API. The following are the observed main-branch heads; selected source files were inspected, not a full repository audit. Most source copies were fetched from `main` shortly after metadata retrieval, rather than pinned downloads. The MtheK scraper was fetched at the listed commit.

| Repository | Observed head | Architecture, authentication and data retrieval | Reuse assessment |
| --- | --- | --- | --- |
| [MtheK/brunata-fetcher-ha-addon](https://github.com/MtheK/brunata-fetcher-ha-addon) | `e50f34984394b3da08c11d8057e61ca191414bc8` | Container add-on; Playwright scrapes Munich SAP/UI5 pages; server publishes MQTT Discovery and query-health entities. UI navigation selects heating, cold water and hot water, then parses displayed German numbers and update date. | Useful operational reference, but its selectors and navigation are Munich-specific. A configurable login URL does not provide portal compatibility. GitHub metadata did not identify a license: verify permission before copying implementation. |
| [MSL-DA/brunata_online](https://github.com/MSL-DA/brunata_online) | `71d39e4a5fe6095d8c358b0929a08e512983db69` | Native custom integration, domain `brunata`. Async HTTPX client; Keycloak authorization code/PKCE and token lifecycle at `online.brunata.com`. API root `/online-webservice/v2/rest`; reads `/consumer/metersforconsumer`, locale lookup tables, and `/consumer/consumption` for daily figures used in allocator reset handling. | Useful meter models, unit validation, error separation and reset-handling concepts. International portal, not Cologne. MIT metadata. |
| [fjfricke/brunata-api](https://github.com/fjfricke/brunata-api) | `ffd54b519b7dee51e2d8535cf2e4f750e16f5504` | Independent async HTTPX library and CLI for Munich. SAP OData `$batch`: `NP_REG_LOGON_SRV_01` / `CredentialSet` for login, cookies/CSRF and subsequent SAP authentication, `NP_APPLAUNCHER_SRV` for context, `NP_DASHBOARD_SRV` for periods and consumption. Exposes heating/hot-water readings, period totals, comparisons and room breakdowns. | Demonstrates browser-free access to Munich, not an established Cologne API. Do not assume equivalent services or cold-water coverage. MIT metadata. |
| [patricklind/brunata-to-home-assistant](https://github.com/patricklind/brunata-to-home-assistant) | `1714a1c497072d988dc096ad2a714aabb3321337` | Native integration, domain `brunata_online`; coordinator, meter and aggregate sensors, history and panel. Current source uses Keycloak/PKCE; synchronous Requests authentication is separate from aiohttp data retrieval. Token exchange/refresh uses `/online-auth-webservice/v1/rest/oauth/token`; data uses `/online-webservice/v2/rest/consumer` and `/consumer/meters`, including dated requests/history. | Useful identity, reauthentication, diagnostics and aggregation concepts; larger scope than the proposed first release. International portal, not Cologne. MIT metadata. |

Primary source files inspected:

- [MtheK scraper](https://github.com/MtheK/brunata-fetcher-ha-addon/blob/e50f34984394b3da08c11d8057e61ca191414bc8/brunata_fetcher/_brunata_scraper.py)
- [MSL-DA API](https://github.com/MSL-DA/brunata_online/blob/71d39e4a5fe6095d8c358b0929a08e512983db69/custom_components/brunata/api.py)
- [fjfricke client](https://github.com/fjfricke/brunata-api/blob/ffd54b519b7dee51e2d8535cf2e4f750e16f5504/src/brunata_api/client.py)
- [patricklind API](https://github.com/patricklind/brunata-to-home-assistant/blob/1714a1c497072d988dc096ad2a714aabb3321337/custom_components/brunata_online/api.py)

Older references to Azure B2C in READMEs/discussions do not describe the current international clients: the inspected code uses Keycloak. This migration does not establish any relationship to Cologne authentication.

## Cologne reports

[MtheK discussion #2: Brunata Online Portal Köln](https://github.com/MtheK/brunata-fetcher-ha-addon/discussions/2) reproduces the exact reported failure:

- MQTT Discovery succeeds and creates heating, cold-water and hot-water entities, but the portal fetch fails.
- The scraper times out waiting for `#__component0---Start--idEmailInput-inner`.
- On 2026-06-24 the maintainer reports a different backend stack and no indication of Munich's SAP stack in the Cologne page.
- The reporter notes that the suggested alternatives target different portals. The visible discussion is unanswered and contains no working Cologne implementation.

The visible open issue list also includes browser startup and Docker installation reports; these are not evidence of Cologne compatibility. Discovery of MQTT entities is not evidence of successful consumption retrieval.

Coverage limitation: GitHub API rate limiting interrupted a broader all-state issue/comment retrieval. Several other issue/discussion pages could not be fetched by the web reader. No comprehensive absence claim is made about closed issues, forks or every discussion in the other repositories. The specific Cologne discussion above was read in full.

## Direct observations from the public Cologne frontend

The [login page](https://online.brunata-koeln.de/legacy/login) and its [authentication JavaScript](https://online.brunata-koeln.de/legacy/Scripts/Views/Authentication/index.js) were fetched without credentials. No login POST was sent.

Confirmed in the delivered frontend:

- Vue-based login view; input identifiers `username` and `password` agree with the user-provided DOM observations.
- A hidden `__RequestVerificationToken` is read from the page.
- The login model serializes `Username`, `Password`, `CaptchaInputText`, `CaptchaDeText`, `returnUrl`, and `__RequestVerificationToken` with `URLSearchParams`.
- Submission is `POST /legacy/Account/Login` with `Content-Type: application/x-www-form-urlencoded; charset=UTF-8` and redirect following.
- The UI treats a redirected response as successful navigation. Otherwise it reads JSON fields `Message` and `Fails`.
- The frontend requests a CAPTCHA when its failure count reaches 2 and uses `GET /legacy/Account/RefreshCaptcha`. This is client behavior, not proof of the server's complete enforcement policy.

Implications: input IDs are not wire-format field names. A direct HTTP login appears feasible, but has not been tested. Use one isolated cookie session for the initial page GET, CSRF extraction and POST. Verify the authenticated state with a known protected resource; a redirect alone is not sufficient. Do not assume ASP.NET, SAP, OAuth, or a particular cookie name from these observations.

Unknown: protected data routes, account/property selection, exact session expiry, MFA/CAPTCHA behavior on a real account, response schemas, meter IDs, available media, units, measurement frequency and whether values represent meter indexes, monthly consumption or year-to-date totals. No public documented Cologne consumption API was established by this research.

## Proposed implementation, after approval

### 1. Confirm the transport contract

Inspect the selected VS Code workspace and applicable repository instructions first. Inspect public application assets, then observe one normal authorized account login and consumption-page visit. Record only route templates, methods, field names, status behavior and sanitized response shapes. Never retain a raw HAR, credential payload, session cookie or token in logs or fixtures.

Confirm each required medium separately. Produce an endpoint map and synthetic fixtures, including units, period boundaries and missing-data behavior. Stop automatic retries on rejected credentials or a CAPTCHA challenge; surface an actionable authentication error. Revisit the transport choice if structured endpoints are unavailable.

Exit criterion: a reproducible login/session lifecycle and a validated retrieval path for the available heating, cold-water and hot-water data. Explicitly report any medium absent from the account.

### 2. Implement a Cologne client

Use an async client with an injectable transport and account-isolated cookie state. Separate session/authentication, fetching and parsing. Provide typed readings with source identity, medium, value, native unit, reading timestamp, period and value semantics. Distinguish authentication rejection, temporary network errors and incompatible responses. Apply bounded timeouts, limited retry/backoff for transient errors and rate-limit handling. Avoid repeated credential submissions.

Log only controlled error categories and safe status information. Do not log request/response bodies, authorization headers, passwords, CSRF tokens, cookies, token-bearing URLs or unsanitized exception text. Keep TLS verification enabled and restrict credential-bearing requests to the expected trusted origin.

### 3. Add the Home Assistant integration

Proposed domain: `brunata_koeln`, avoiding the existing `brunata` and `brunata_online` domains. Use UI config flow, reauthentication, a shared DataUpdateCoordinator, stable unique IDs and correct unload behavior. Keep the HTTP client independent of entity logic. Start with daily polling as a proposal, then adjust to the verified portal publication cadence.

Expose heating, cold-water and hot-water sensors only where supported by actual data. Include reading date/period and availability information. Distinguish fetch time from measurement time. Missing values must never become zero.

Sensor semantics must follow the verified source:

- Volume in m³ can use the water device class. Warm-water volume and warm-water energy are distinct measurements.
- Heating in kWh can use energy semantics; heat-cost allocator units cannot be presented as kWh.
- Use `total_increasing` only for suitable cumulative nondecreasing readings with understood resets. Monthly interval consumption must not be treated as a monotonically increasing meter.
- Aggregate only compatible units and periods; handle meter replacement and rollover explicitly. Energy dashboard compatibility is conditional on the source semantics.

Follow Home Assistant's [coordinator guidance](https://developers.home-assistant.io/docs/integration_fetching_data/) and [sensor rules](https://developers.home-assistant.io/docs/core/entity/sensor/).

### 4. Validate and package

Test the transport contract with synthetic responses: CSRF/cookie continuity, login failure, session expiry, CAPTCHA, HTML returned instead of JSON, timeouts, 429 responses, missing media, locale numbers, units, duplicate/stale readings, resets and meter replacement. Add integration tests for config flow, reauthentication, coordinator availability, unique IDs and unload. Verify secrets are absent from errors and diagnostics.

Compare one authorized live sample per available medium against the portal before acceptance. Add English README/setup/troubleshooting documentation, manifest and HACS metadata; run applicable lint, tests and integration validation. A live login and data fetch remain unverified until this stage.

## Approval scope

Recommended next authorization: proceed with transport validation and a minimal native integration in the user's selected workspace. Browser scraping, a dashboard panel, derived cost estimates and historical statistics backfill are outside the initial scope. No GitHub issue/comment has been posted, no remote project created and no credentials requested or used.
