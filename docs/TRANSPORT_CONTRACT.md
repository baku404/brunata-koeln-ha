# Cologne portal transport contract

Observed and live-tested on 2026-10-18 using an authorized Cologne account. Only route templates and sanitized schema information are retained; fixtures are synthetic.

## Authentication and session context

1. GET `/legacy/login` for CSRF markup and initial cookies.
2. POST URL-encoded `Username`, `Password`, `CaptchaInputText`, `CaptchaDeText`, `returnUrl` and `__RequestVerificationToken` to `/legacy/Account/Login`, with the portal Origin/Referer.
3. Follow same-origin redirects without replaying credentials on 307/308.
4. GET `/legacy/account/refreshSession` and `/legacy/spa/currentUser` with the observed AJAX header. Require a tenant role; do not accept terms automatically.
5. Set the non-authentication `.contentOnly=true` display cookie at `/`.
6. GET `/legacy/Nutzer/Nutzeinheiten` to initialize the selected tenancy. Accounts requiring an explicit choice are reported rather than guessed.
7. Verify the protected consumption overview before considering the session authenticated.

The legacy server rejects aiohttp RFC 2109 octal-quoted cookie transmission with HTTP 500. The client uses `CookieJar(quote_cookie=False)` to match browser transmission; origin restrictions and TLS verification remain enabled.

Login failure JSON exposes `Fails` and `Message`. Raw server messages are excluded from errors. The frontend requests CAPTCHA at two failures; the client stops on rejection or an interactive challenge rather than retrying automatically.

## Consumption

GET `/legacy/Uvi/Nutzer/Index` advertises medium links such as `/legacy/Uvi/Nutzer/MonthCompare?mediumType=Heizung`. Follow only advertised same-origin links.

Detail pages contain `script[type="text/plain"][id^="chart-data-"]` payloads. The full chart object contains JavaScript callbacks; decode only the JSON series array and never execute JavaScript.

The selected series has:

- `name = "Ausgewählter Abrechnungszeitraum"`
- `valueType` for the native unit
- `data` points with epoch-millisecond `x`, numeric `y` and boolean `isHochrechnung`

The chart medium must match the request. Interpret dates in Europe/Berlin. Expose only explicit non-estimated past-month values. Ambiguous series, unknown units and conflicting duplicates fail closed. Missing data never become zero; interval readings never become cumulative totals.

The same chart also carries `name = "Vorheriger Abrechnungszeitraum"`. Its points use the selected period's timestamps (so both bars share a month) and have no `isHochrechnung` flag. Each point is moved to the same month one year earlier; points explicitly flagged as estimates are skipped, and the result is then validated like the selected series. The previous period is optional: when it is missing, ambiguous or malformed, the selected period is still returned and diagnostics report `previous_period_unavailable`.

## Evidence and limits

Direct HTTP heating retrieval and initial HA sensor creation passed. Water responses, live session expiry/reauthentication, explicit tenancy/period selection and further HA lifecycle checks remain open. See [verification status](VERIFICATION.md).
