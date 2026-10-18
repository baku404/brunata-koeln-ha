# Tests

Run `python -m unittest discover -s tests -t . -v`.

The offline tests cover chart extraction, previous periods, estimates, missing/zero values, timezone boundaries, conflicts, units, medium discovery, login rejection, CAPTCHA, expiry, redirects and outages.

Fixtures in `helpers.py` are entirely synthetic. HTTP doubles never contact Brunata. A namespace import loads standalone client modules without installing Home Assistant.

Remaining before production: automated config-flow and reauthentication tests with HA, entity/coordinator lifecycle tests, and live checks listed in `docs/VERIFICATION.md`. Manual initial HA setup and heating sensor creation have passed.

Real HTTP transport tests additionally run against a local HTTPS server with a trusted test CA. They verify actual cookie transmission, redirect handling, cookie-path errors and safe probes after an auxiliary endpoint failure. No external portal credentials are used.

Regression coverage includes the legacy backend rejecting octal-quoted cookie values, successful browser-style transmission, and required tenancy initialization. Live heating retrieval was verified separately; live credentials are never used by CI.

History tests cover correction identity, repeated imports, DST/year boundaries, gaps, duplicates and mixed units. Comparison tests cover unique average selection, units and estimate exclusion. Recorder orchestration tests use interface doubles and do not replace live HA validation.
