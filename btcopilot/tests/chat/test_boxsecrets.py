"""Every setting the app reads without a fallback must have a home on the box:
the secrets template or the compose file. A key read by the code and absent
from both is a server error waiting for the first user to reach that path
(2026-09-21: the Gemini key, reached by cluster detection)."""

import re
from pathlib import Path

import btcopilot

REPO = Path(btcopilot.__file__).parents[1]
DEPLOY = REPO / "deploy" / "chat"
# Read by the extraction pipeline the chat app never runs.
NOT_THE_CHAT_APP = {"ANTHROPIC_EXTRACTION_API_KEY"}


def hard_reads() -> set[str]:
    found = set()
    for path in (REPO / "btcopilot").rglob("*.py"):
        if "tests" in path.parts or "archive" in path.parts:
            continue
        found |= set(re.findall(r'os\.environ\["([A-Z_]+)"\]', path.read_text()))
    return found - NOT_THE_CHAT_APP


def on_the_box() -> set[str]:
    template = (DEPLOY / "secrets.env.example").read_text()
    compose = (DEPLOY / "docker-compose.yml").read_text()
    return set(re.findall(r"^([A-Z_]+)=", template, re.M)) | set(
        re.findall(r"^\s+([A-Z_]+):", compose, re.M)
    )


def test_every_setting_the_app_requires_has_a_home_on_the_box():
    # R-0465
    assert hard_reads() - on_the_box() == set()
