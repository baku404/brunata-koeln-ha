"""Validate metadata and syntax without importing Home Assistant."""

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "brunata_koeln"


def validate(release_tag: str | None = None) -> dict:
    """Check metadata, source syntax and release version consistency."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    if manifest["domain"] != INTEGRATION.name:
        raise ValueError("Manifest domain must match the integration directory")
    if not re.fullmatch(
        r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+|\.dev\d+)?", manifest["version"]
    ):
        raise ValueError("Unsupported release version")
    if release_tag is not None and release_tag != f"v{manifest['version']}":
        raise ValueError("Release tag must match the manifest version")
    for directory in (INTEGRATION, ROOT / "scripts", ROOT / "tests"):
        for path in directory.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
    english = json.loads(
        (INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8")
    )
    if strings != english:
        raise ValueError("English translations must match source strings")
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    if hacs["filename"] != "brunata_koeln.zip" or not hacs["zip_release"]:
        raise ValueError("HACS metadata must match the release archive")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-tag")
    args = parser.parse_args()
    result = validate(args.release_tag)
    print(f"Validated {result['domain']} {result['version']} (syntax and metadata)")
