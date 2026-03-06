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

# Passage row: | <a id="ID"></a>ID | "quote" | description |
_PASSAGE_ROW_RE = re.compile(
    r"\| (?:<a id=\"[^\"]+\"></a>)?([A-Z]+\d+-?\d*) \|"
    r"\s*([^|]*?)\s*\|"
)


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


def _extract_passages(text: str, filename: str) -> tuple[dict[str, str], dict[str, str]]:
    """Extract passage IDs → (urls, quotes) from a definition file."""
    urls = {}
    quotes = {}
    for match in _PASSAGE_ROW_RE.finditer(text):
        pid = match.group(1)
        urls[pid] = f"{_GITHUB_BLOB_BASE}/{filename}#{pid}"
        quote = match.group(2).strip().strip('"').strip()
        if quote:
            quotes[pid] = quote
    return urls, quotes


DEFINITIONS: dict[str, str] = {}
PASSAGE_URLS: dict[str, str] = {}
PASSAGE_QUOTES: dict[str, str] = {}

for _key, _filename in _SARF_DEF_FILES.items():
    DEFINITIONS[_key] = _load_definition(_key, _filename)
    _urls, _quotes = _extract_passages(DEFINITIONS[_key], _filename)
    PASSAGE_URLS.update(_urls)
    PASSAGE_QUOTES.update(_quotes)


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


_LINK_OR_ID = re.compile(
    r"<a\b[^>]*>.*?</a>"     # skip HTML links
    r"|\[[^\]]*\]\([^\)]*\)" # skip markdown links
    r"|\b([A-Z]+\d+-?\d*)\b" # capture bare passage IDs
)


def linkify_passages(text: str) -> str:
    """Replace passage ID references with clickable links including hover tooltips."""
    if not text or not PASSAGE_URLS:
        return text or ""

    def _replace_match(m):
        pid = m.group(1)
        if pid is None:
            return m.group(0)
        if pid not in PASSAGE_URLS:
            return m.group(0)
        quote = PASSAGE_QUOTES.get(pid)
        if quote:
            escaped = quote.replace('"', '&quot;')
            return f'<a href="{PASSAGE_URLS[pid]}" title="{pid}: {escaped}" target="_blank">{pid}</a>'
        return f'<a href="{PASSAGE_URLS[pid]}" target="_blank">{pid}</a>'

    return _LINK_OR_ID.sub(_replace_match, text)
