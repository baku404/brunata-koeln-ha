# Contributing

This project is an experimental native integration. Read the architecture, transport contract and verification status before changing authentication or adding endpoint assumptions.

1. Use a feature branch and Python 3.14 for HA runtime work; standalone client tests also support Python 3.12.
2. Keep code, comments, issues and documentation in English.
3. Prefer async HTTP/API access. Separate transport, parsing and Home Assistant entities.
4. Use synthetic fixtures only. Do not commit credentials, personal identifiers, cookies, tokens or raw network captures.
5. Run `python -m unittest discover -s tests -t . -v`, `python scripts/validate.py`, `python -m ruff check .` and `python -m ruff format --check .`.
6. Add meaningful behavior tests as functionality is implemented.
7. Describe behavior, validation and limitations in the pull request.

Do not infer measurement units, cumulative state classes or successful authentication from UI labels alone. Do not silently replace missing readings with zero.
