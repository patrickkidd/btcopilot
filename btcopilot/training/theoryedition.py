"""The public edition of the concept pages, ported from the public mode of
theory/CONCEPTS/verify.py in btcopilot-sources. Keep the two in step."""

import ast
import re

LINK = re.compile(r"(?<!!)\[((?:[^\[\]\n]|\[[^\]\n]*\])*)\]\(([^)\s]+)\)")
PUBLIC_NOTE = (
    "This is the public edition: excerpts from confidential sources are left out, "
    "and so are the paths to the source files ([`README.md`](README.md))."
)
FORBIDDEN = re.compile(
    r"CONFIDENTIAL|private/|/Users/|seminar-20|App Seminar 20|patrick-journal|\.tsv\b|\.vtt\b"
)


def _check(name, text):
    bad = [l for l in text.split("\n") if FORBIDDEN.search(l)]
    if bad:
        raise ValueError(f"{name}: public copy still names private material: {bad}")


def _keyform(text):
    t = text.replace("`", "")
    t = re.sub(r"\bCASES/([\w-]+)\.md", r"case card \1", t)
    t = re.sub(r"\bnotes/([\w-]+)\.md", r"reading notes \1", t)
    t = t.replace("verify.py", "the quote checker")
    return re.sub(r"\b([A-Z_]+)\.md\b", r"\1", t)


def public(name: str, text: str, names: list[str]) -> str:
    pages = {f"{n}.md" for n in names} | {"README.md"}

    def link(m):
        label, target = m.groups()
        path = target.split("#")[0]
        if path == "INDEX.md":
            return f"[{label}](README.md)"
        if not path or path in pages:
            return m.group(0)
        return _keyform(label)

    out = re.sub(r"<!-- CONFIDENTIAL -->.*?<!-- /CONFIDENTIAL -->\n?", "", text, flags=re.S)
    out = "\n".join(l for l in out.split("\n") if "· CONFIDENTIAL" not in l)
    out = re.sub(r" ?<!-- v .*? -->", "", out)
    out = LINK.sub(link, out)
    out = re.sub(
        r"Every excerpt is marked PUBLIC or CONFIDENTIAL\. The public copy drops every CONFIDENTIAL line and block \(.*?\)\.",
        PUBLIC_NOTE,
        out,
    )
    out = re.sub(
        r"(IRR coders' meeting entries (in this section )?are PUBLIC\. )?App Seminar entries are CONFIDENTIAL[^.]*\.",
        "App Seminar excerpts are in the private edition only.",
        out,
    )
    out = out.replace(" · PUBLIC", "")
    _check(name, out)
    return out


def _intro(verify):
    return next(
        ast.literal_eval(n.value)
        for n in ast.parse(verify).body
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "INTRO"
    )


def index(table: str, readme: str, verify: str, pages: dict[str, str]) -> str:
    rows = []
    for line in table.split("\n"):
        m = re.match(r"\| \[`(\S+)\.md`\]\(\S+\) (\(\w+\)) \| (.+?) \| \d+ \| (.+?) \|$", line)
        if m:
            count = len(re.findall(r'<a id="\w+"></a>', pages[m.group(1)]))
            rows.append(
                f"| [{m.group(1)}]({m.group(1)}.md) {m.group(2)} | {m.group(3)} | {count} | {m.group(4)} |"
            )
    keys = []
    for line in readme.split("\n"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 4 and cells[3].startswith(("PUBLIC", "CONFIDENTIAL where")):
            keys.append(f"| {cells[0]} | {cells[1]} |")
    out = _intro(verify).format(rows="\n".join(rows), keys="\n".join(keys))
    _check("index", out)
    return out


def links(text: str, targets: dict[str, str]) -> str:
    """Point links to the pages at `targets` (file name to URL); every other
    link becomes its plain label, since coders cannot open those files."""

    def link(m):
        label, target = m.groups()
        path, sep, anchor = target.partition("#")
        if not path:
            return m.group(0)
        if path in targets:
            return f"[{label}]({targets[path]}{sep}{anchor})"
        return label

    return LINK.sub(link, text)
