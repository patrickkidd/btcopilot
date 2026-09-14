"""Where this checkout is, so no test has to count directories up from itself."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "btcopilot"
