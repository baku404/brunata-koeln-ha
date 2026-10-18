# Security policy

## Supported versions

Security fixes target the latest published 1.x release. Version 1.0.0 is the initial release; see docs/VERIFICATION.md for verified scope and outstanding checks.

## Reporting

Never put secrets or personal data in public issues. Once hosted on GitHub, use private vulnerability reporting if enabled. Otherwise request a private reporting channel without disclosing the vulnerability publicly. Do not assume private reporting is enabled until the maintainer confirms it.

## Credential handling

- HA UI setup retains credentials in the config entry; protect HA configuration and backups.
- The standalone checker prompts for masked/hidden input and never persists credentials.
- Account-isolated sessions retain TLS verification and same-origin redirect restrictions; POST credentials are never replayed via 307/308.
- No raw server messages, token-bearing URLs, response bodies, cookies or credentials are logged by the client.
- Authentication errors stop coordinator polling through HA reauthentication; no automatic CAPTCHA solving or terms acceptance.
- Diagnostics use an allowlist without account identifiers or response bodies.
- Only synthetic fixtures belong in Git. Raw pages, HARs, environment files and private captures are ignored and must not be staged.
