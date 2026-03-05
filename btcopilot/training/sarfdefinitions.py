import logging
import os
import urllib.request
from pathlib import Path

_log = logging.getLogger(__name__)

_SARF_DEF_FILES = {
    "functioning": "01-functioning.md",
    "anxiety": "02-anxiety.md",
    "symptom": "03-symptom.md",
    "conflict": "04-conflict.md",
    "distance": "05-distance.md",
    "cutoff": "06-cutoff.md",
    "overfunctioning": "07-overfunctioning.md",
    "underfunctioning": "08-underfunctioning.md",
    "projection": "09-projection.md",
    "inside": "10-inside.md",
    "outside": "11-outside.md",
    "defined-self": "12-definedself.md",
}

_GITHUB_RAW_BASE = "https://raw.githubusercontent.com/patrickkidd/btcopilot/master/doc/sarf-definitions"
_LOCAL_DIR = Path(__file__).parent.parent.parent / "doc" / "sarf-definitions"
_CACHE_DIR = Path(__file__).parent / "data" / "sarf_definitions"


def _load_definition(key: str, filename: str) -> str:
    # 1. Local filesystem (dev checkout)
    local_path = _LOCAL_DIR / filename
    if local_path.exists():
        return local_path.read_text()

    # 2. Cached from previous fetch
    cache_path = _CACHE_DIR / filename
    if cache_path.exists():
        return cache_path.read_text()

    # 3. Fetch from GitHub
    url = f"{_GITHUB_RAW_BASE}/{filename}"
    _log.info(f"Fetching SARF definition '{key}' from {url}")
    with urllib.request.urlopen(url, timeout=30) as resp:
        text = resp.read().decode("utf-8")

    # Cache for next time
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text)
    return text


DEFINITIONS: dict[str, str] = {}
for _key, _filename in _SARF_DEF_FILES.items():
    DEFINITIONS[_key] = _load_definition(_key, _filename)


def definitions_for_event(event: dict) -> dict[str, str]:
    """Return applicable SARF definitions keyed by field label."""
    result = {}
    for field in ("symptom", "anxiety", "functioning"):
        if event.get(field):
            result[field] = DEFINITIONS[field]
    rel = event.get("relationship")
    if rel:
        val = rel.value if hasattr(rel, "value") else rel
        if val in DEFINITIONS:
            result[f"relationship:{val}"] = DEFINITIONS[val]
    return result
