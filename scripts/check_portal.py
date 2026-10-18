"""Check a real account interactively without storing or logging its credentials."""

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path
from types import ModuleType

package = ModuleType("brunata_client")
package.__path__ = [
    str(Path(__file__).resolve().parents[1] / "custom_components" / "brunata_koeln")
]
sys.modules["brunata_client"] = package


def prompt_password() -> str:
    """Show input feedback on Windows without exposing password characters."""
    if sys.platform != "win32" or not sys.stdin.isatty():
        print("Password input is active; characters are hidden. Press Enter when done.")
        return getpass.getpass("Password (hidden, not stored): ")
    import msvcrt

    print("Password (masked, not stored): ", end="", flush=True)
    characters: list[str] = []
    while True:
        character = msvcrt.getwch()
        if character in ("\r", "\n"):
            print()
            return "".join(characters)
        if character == "\x03":
            print()
            raise KeyboardInterrupt
        if character in ("\x00", "\xe0"):
            msvcrt.getwch()
            continue
        if character in ("\b", "\x7f"):
            if characters:
                characters.pop()
                print("\b \b", end="", flush=True)
        elif character.isprintable():
            characters.append(character)
            print("*", end="", flush=True)


async def main(preflight=False):
    """Print only controlled errors and medium/month/value summaries."""
    from brunata_client.api import BrunataClient
    from brunata_client.errors import BrunataError

    username = "" if preflight else input("Cologne portal username or email: ").strip()
    password = "" if preflight else prompt_password()
    if not preflight:
        if not password:
            print("No password entered; no request was sent.")
            return 1
        print("Password received. Starting portal check.")
    client = BrunataClient(username, password)
    try:
        if preflight:
            print(json.dumps(await client.async_preflight(), sort_keys=True))
            return 0
        data = await client.async_fetch()
        for medium, readings in data.items():
            latest = readings.latest
            if latest is None:
                print(f"{medium}: no actual past-month readings")
            else:
                print(f"{medium}: {latest.month:%Y-%m}, {latest.value:g} {latest.unit}")
        return 0
    except BrunataError as error:
        print(f"{type(error).__name__}: {error}")
        print(
            "Safe diagnostics: " + json.dumps(client.safe_diagnostics, sort_keys=True)
        )
        if client.safe_diagnostics.get("http_status") == 500:
            print("Checking existing-session reads without another login.")
            print(
                "Safe session probes: "
                + json.dumps(await client.async_diagnose_session(), sort_keys=True)
            )
        return 1
    except Exception:
        print("Unexpected local failure; no portal details were logged.")
        return 1
    finally:
        await client.async_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Check public login without credentials",
    )
    arguments = parser.parse_args()
    try:
        sys.exit(asyncio.run(main(arguments.preflight)))
    except (KeyboardInterrupt, EOFError):
        print("Check cancelled.")
        sys.exit(1)
