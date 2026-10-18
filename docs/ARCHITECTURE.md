# Architecture

- `api.py`: account-isolated aiohttp session and serialized fetch/login.
- `parser.py`: allowlisted links and structured chart series using HTMLParser/JSON.
- `models.py`: immutable monthly records independent of Home Assistant.
- `errors.py`: controlled errors without server payloads.
- `config_flow.py`: protected-data validation, duplicate prevention and reauthentication.
- `coordinator.py`: one daily refresh shared by entities.
- `sensor.py`: dynamically discovered latest actual past-month sensors.
- `diagnostics.py`: allowlisted operational counts and status.
- `history.py`: deterministic monthly baselines and cumulative interval sums.
- `statistics.py`: stable external statistic IDs, previous-year baseline lookup and daily reconciliation through Recorder APIs.

Malformed responses fail the shared update. Missing media become unavailable. Unit changes make existing entities unavailable rather than silently changing their history.

Only the selected tenancy and default billing period are currently supported. Explicit tenancy discovery is a separate next step.

Structured chart data are used because no stable separate JSON consumption API has been established. No browser runtime, MQTT broker or standalone container is required.

Target: Core 2026.10.2. Client/parser tests run offline. Manual UI setup and initial heating sensor creation passed on this target; automated HA lifecycle tests remain a release prerequisite. See [verification status](VERIFICATION.md).

The verified startup sequence is login -> session refresh -> current user context -> iframe display cookie -> legacy tenancy initialization -> consumption overview and medium details. Cookies retain origin restrictions and TLS verification; only RFC 2109 octal quoting is disabled to match browser behavior. This is not CookieJar unsafe mode.
