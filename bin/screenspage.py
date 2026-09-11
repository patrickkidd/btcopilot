"""Render SCREENS.md as a catalogue of whole screens in live code: every screen is the real
frame lifted out of a mockup file, drawn with the app's own stylesheet, with one caption under
it and the list of behaviours folded away beneath.

  python bin/screenspage.py <out.html>

No images anywhere. The app stylesheet is inlined once; each mockup's own page-only styles are
inlined once and scoped so two mockups cannot fight over the same class.
"""
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"
MOCKUPS = DOC / "mockups"
THEME = HERE / "web" / "src" / "theme.css"

# where a mockup file stops being the app stylesheet and starts being its own page
SPLIT = "/* ---- mockup frames only ---- */"

STYLE = """html,body{height:auto!important;overflow:visible!important;display:block!important}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans);margin:0;padding-block:28px 60px;padding-left:20px;padding-right:20px;max-width:none}
h1{font:600 22px var(--sans);margin:0 0 4px}.lead{color:var(--faint);margin:0 0 10px;max-width:84ch}
code{font:12.5px var(--mono);color:var(--data)}
.counts{font:500 13px var(--mono);color:var(--faint);margin:0 0 14px}
nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin:0 0 24px;font-size:14px}nav a{color:var(--data);text-decoration:none}
h2{font:600 17px var(--sans);margin:34px 0 2px;padding-top:10px;border-top:1px solid var(--line)}
.for{color:var(--faint);font-size:14px;margin:0 0 14px;max-width:84ch}
.shots{display:flex;flex-wrap:wrap;gap:22px;margin:0 0 16px;align-items:flex-start;overflow-x:auto;max-width:100%;padding-bottom:6px}
figure{margin:0;flex:none;max-width:100%}
figcaption{font:12px/1.45 var(--mono);color:var(--faint);margin-top:8px}
.none{font-size:14px;color:var(--faint);margin:0 0 14px}
details{border-top:1px solid var(--line);padding-top:8px}
summary{cursor:pointer;font:500 13.5px var(--sans);color:var(--data);list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"\\25b8 ";}details[open] summary::before{content:"\\25be ";}
ul{margin:10px 0 0;padding:0 0 0 20px}li{margin:0 0 7px}
.pill{display:inline-block;font:500 11.5px var(--mono);border-radius:9px;padding:0 7px;margin-left:6px;white-space:nowrap;vertical-align:1px}
.built{border:1px solid var(--data);color:var(--data)}.drawn{border:1px solid var(--ask);color:var(--ask)}
.open{border:1px solid var(--ask);background:var(--ask);color:var(--panel)}
small.src{display:none;font:500 11.5px var(--mono);color:var(--faint);margin-left:6px}
#sources:checked~* small.src{display:inline}
#sources{vertical-align:-1px;margin:0 6px 18px 0}
label.toggle{font-size:13px;color:var(--faint)}"""

TAG = re.compile(r"\[(built|drawn|open)\]\s*(\{[^}]*\})?\s*$")
FRAME = re.compile(r"^@frame\s+([a-z0-9-]+)#(f\d+)\s*\|\s*(.+)$")
ID_ATTR = re.compile(r'\b(id|for|aria-labelledby|aria-controls)="([^"]+)"')
SELECTOR = re.compile(r"([^{}]+)\{([^{}]*)\}")
SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


def page_css(text: str, mockup: str) -> str:
    """A mockup's own styles, scoped under the class its frames are wrapped in. The rules that
    reshape the whole document belong to that mockup's page, not to this one, so they go."""
    block = text.split(SPLIT, 1)[1].split("</style>", 1)[0]
    out = []
    for selectors, body in SELECTOR.findall(block):
        kept = [
            f".from-{mockup} {one.strip()}"
            for one in selectors.split(",")
            if one.strip() and one.strip().split()[0] not in ("html", "body", "html,")
        ]
        if kept:
            out.append(f"{','.join(kept)}{{{body.strip()}}}")
    return "\n".join(out)


def frame(text: str, mockup: str, fid: str, seq: int) -> tuple[str, str]:
    """The frame element with that id, lifted whole, and the classes on it. Every id inside is
    made unique to this mockup and frame so two copies on one page never share one."""
    at = text.find(f'id="{fid}"')
    if at < 0:
        raise SystemExit(f"{mockup}.html has no frame {fid}")
    start = text.rfind("<div", 0, at)
    depth, end = 0, len(text)
    for match in re.finditer(r"</?div\b[^>]*>", text[start:]):
        depth += 1 if match.group().startswith("<div") else -1
        if depth == 0:
            end = start + match.end()
            break
    markup = SCRIPT.sub("", text[start:end])
    classes = re.search(r'class="([^"]*)"', markup[: markup.find(">")])
    markup = ID_ATTR.sub(lambda m: f'{m.group(1)}="{mockup}-{fid}-{seq}-{m.group(2)}"', markup)
    return markup, classes.group(1) if classes else ""


def frame_widths(text: str) -> list[tuple[frozenset, int]]:
    """What each of a mockup's frame rules sets the frame's width to, so the caption under a
    copied frame can be as wide as the frame itself."""
    block = text.split(SPLIT, 1)[1].split("</style>", 1)[0]
    found = []
    for selectors, body in SELECTOR.findall(block):
        width = re.search(r"\bwidth:\s*(\d+)px", body)
        if not width:
            continue
        for one in selectors.split(","):
            one = one.strip()
            if re.fullmatch(r"\.frame(\.[a-z0-9-]+)*", one):
                found.append((frozenset(one.split(".")[1:]), int(width.group(1))))
    return sorted(found, key=lambda pair: len(pair[0]))


def parse():
    text = (DOC / "SCREENS.md").read_text()
    head, _, rest = text.partition("\n## ")
    lead = [ln.strip() for ln in head.splitlines() if ln.strip() and not ln.startswith("#")]
    lead = [ln for ln in lead if ln != "---"]
    updated = next((ln for ln in lead if ln.startswith("Updated")), "")
    blurb = " ".join(ln for ln in lead if not ln.startswith("Updated"))

    sections, counts = [], {"built": 0, "drawn": 0, "open": 0}
    for block in rest.split("\n## ") if rest else []:
        name, _, body = block.partition("\n")
        name = name.strip()
        purpose, items, frames = "", [], []
        for line in body.splitlines():
            line = line.strip()
            shot = FRAME.match(line)
            if shot:
                frames.append((shot.group(1), shot.group(2), shot.group(3).strip()))
            elif line.startswith("What it is for:"):
                purpose = line[len("What it is for:") :].strip()
            elif line.startswith("- "):
                items.append(line[2:].strip())
        rows = []
        for item in items:
            m = TAG.search(item)
            status = m.group(1) if m else "built"
            ids = (m.group(2) or "").strip("{} ") if m else ""
            counts[status] += 1
            src = f'<small class="src">{html.escape(ids)}</small>' if ids else ""
            rows.append(
                f'<li>{inline(TAG.sub("", item).strip())}'
                f'<span class="pill {status}">{status}</span>{src}</li>'
            )
        sections.append((name, purpose, frames, rows))
    return blurb, updated, counts, sections


def main(out: str) -> int:
    blurb, updated, counts, sections = parse()
    used = sorted({m for _, _, frames, _ in sections for m, _, _ in frames})
    files = {m: (MOCKUPS / f"{m}.html").read_text() for m in used}
    widths = {m: frame_widths(files[m]) for m in used}
    seq = [0]
    slug = lambda n: re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")

    parts = [
        "<title>Family Diagram Screens</title>",
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        "family=Libre+Franklin:wght@400;500;600;800&family=IBM+Plex+Mono:wght@400;500"
        '&display=swap">',
        "<style>",
        THEME.read_text(),
        STYLE,
        "\n".join(page_css(files[m], m) for m in used),
        "</style>",
        "<h1>Family Diagram &mdash; every screen, as it looks</h1>",
        '<p class="lead">Every screen below is the running app\'s own markup and stylesheet, '
        f"drawn here as a whole screen. {inline(blurb)}</p>",
        f'<p class="counts">{counts["built"]} built &middot; {counts["drawn"]} drawn &middot; '
        f'{counts["open"]} open &middot; {html.escape(updated)}</p>',
        '<input type="checkbox" id="sources">'
        '<label class="toggle" for="sources">show sources</label>',
        "<nav>"
        + "".join(f'<a href="#{slug(n)}">{html.escape(n)}</a>' for n, _, _, _ in sections)
        + "</nav>",
    ]
    for name, purpose, frames, rows in sections:
        parts.append(f'<h2 id="{slug(name)}">{html.escape(name)}</h2>')
        if purpose:
            parts.append(f'<p class="for">{inline(purpose)}</p>')
        if frames:
            shots = ""
            for mockup, fid, caption in frames:
                seq[0] += 1
                markup, classes = frame(files[mockup], mockup, fid, seq[0])
                on = set(classes.split())
                width = next(
                    (w for names, w in reversed(widths[mockup]) if names <= on), 400
                )
                shots += (
                    f'<figure class="from-{mockup}" style="width:{width}px">{markup}'
                    f'<figcaption style="max-width:{width}px">'
                    f"{html.escape(caption)}</figcaption></figure>"
                )
            parts.append(f'<div class="shots">{shots}</div>')
        else:
            parts.append('<p class="none">No rendering yet.</p>')
        parts.append(
            f"<details><summary>what it does &middot; {len(rows)} behaviours</summary>"
            f'<ul>{"".join(rows)}</ul></details>'
        )
    Path(out).write_text("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
