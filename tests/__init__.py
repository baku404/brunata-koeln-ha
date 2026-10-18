"""Client tests load a namespace package without importing Home Assistant."""

import sys
from pathlib import Path
from types import ModuleType

package = ModuleType("brunata_client")
package.__path__ = [
    str(Path(__file__).resolve().parents[1] / "custom_components" / "brunata_koeln")
]
sys.modules["brunata_client"] = package
