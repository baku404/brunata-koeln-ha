"""Build the release archive using an explicit allowlist."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from validate import INTEGRATION, ROOT, validate

RELEASE_FILES = (
    "__init__.py",
    "const.py",
    "config_flow.py",
    "api.py",
    "errors.py",
    "models.py",
    "history.py",
    "statistics.py",
    "parser.py",
    "coordinator.py",
    "sensor.py",
    "diagnostics.py",
    "manifest.json",
    "strings.json",
    "translations/en.json",
)


def package() -> Path:
    """Include only reviewed integration files and the project license."""
    validate()
    destination = ROOT / "dist" / "brunata_koeln.zip"
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for relative in RELEASE_FILES:
            archive.write(INTEGRATION / relative, relative)
        archive.write(ROOT / "LICENSE", "LICENSE")
    return destination


if __name__ == "__main__":
    print(package())
