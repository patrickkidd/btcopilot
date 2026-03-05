import re
import logging
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

_GITHUB_BLOB_BASE = "https://github.com/patrickkidd/btcopilot/blob/master/doc/sarf-definitions"
_GITHUB_RAW_BASE = "https://raw.githubusercontent.com/patrickkidd/btcopilot/master/doc/sarf-definitions"
_LOCAL_DIR = Path(__file__).parent.parent.parent / "doc" / "sarf-definitions"
_CACHE_DIR = Path(__file__).parent / "data" / "sarf_definitions"

# Passage ID pattern: uppercase letters followed by digits, optionally hyphen-digits
_PASSAGE_ID_RE = re.compile(r"\| (?:<a id=\"[^\"]+\"></a>)?([A-Z]+\d+-?\d*) \|")


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


def _extract_passage_ids(text: str, filename: str) -> dict[str, str]:
    """Extract passage IDs from a definition file and map to GitHub URLs."""
    urls = {}
    for match in _PASSAGE_ID_RE.finditer(text):
        pid = match.group(1)
        urls[pid] = f"{_GITHUB_BLOB_BASE}/{filename}#{pid}"
    return urls


DEFINITIONS: dict[str, str] = {}
PASSAGE_URLS: dict[str, str] = {}

for _key, _filename in _SARF_DEF_FILES.items():
    DEFINITIONS[_key] = _load_definition(_key, _filename)
    PASSAGE_URLS.update(_extract_passage_ids(DEFINITIONS[_key], _filename))


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


def linkify_passages(text: str) -> str:
    """Replace passage ID references in LLM markdown output with clickable GitHub links."""
    if not text or not PASSAGE_URLS:
        return text or ""

    # Match passage IDs that aren't already inside markdown links
    def _replace(match):
        pid = match.group(0)
        if pid in PASSAGE_URLS:
            return f"[{pid}]({PASSAGE_URLS[pid]})"
        return pid

    # Negative lookbehind for [ and ( to avoid double-linking existing markdown links
    return re.sub(
        r"(?<!\[)(?<!\()(?<!\")(?<!id=\")\b([A-Z]+\d+-?\d*)\b(?!\])",
        lambda m: f"[{m.group(1)}]({PASSAGE_URLS[m.group(1)]})" if m.group(1) in PASSAGE_URLS else m.group(0),
        text,
    )
