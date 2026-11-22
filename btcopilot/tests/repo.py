"""Where this checkout is, so no test has to count directories up from itself."""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "btcopilot"
# The private corpus, a clone of its own: clinical data and real chats live
# there, never in this repo.
SOURCES = Path(os.environ.get("BTCOPILOT_SOURCES", REPO / "btcopilot-sources"))
