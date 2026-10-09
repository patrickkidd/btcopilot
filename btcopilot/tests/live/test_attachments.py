"""A real coach turn on a message carrying a one-page PDF of family dates.
The reading call is not what is tested here: it is stood in for by the PDF's
own text, as pypdf extracts it, so the case costs nothing beyond the coach's
calls. Passes when the coach enters the file's people and events on that one
reply.

Invented names only.
"""

import io

from pypdf import PdfReader

from btcopilot.llmutil import Served, Spent, Text
from btcopilot.tests.conftest import replied
from btcopilot.tests.live.criterion import passes

LINES = [
    "Hale family notes",
    "Ada Hale born 3 March 1950 in Leeds.",
    "Ada married Hugh Hale on 14 June 1974.",
    "Their son Colm Hale born 9 May 1978.",
    "Hugh Hale died 2 November 2001.",
]


def page(lines: list[str]) -> bytes:
    """A one-page PDF with each line as text, written by hand so the test
    needs nothing to make it."""
    text = "BT /F1 12 Tf 72 720 Td 16 TL " + " ".join(f"({line}) '" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(text)} >>\nstream\n{text}\nendstream",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def named(people, name) -> list[dict]:
    return [p for p in people if p.get("name") == name]


@passes(2, of=3)
def test_a_pdf_of_family_dates_is_entered_on_the_reply_that_carries_it(
    coach, monkeypatch
):
    # R-0828, R-0829
    data = page(LINES)
    read = PdfReader(io.BytesIO(data)).pages[0].extract_text()
    monkeypatch.setattr(
        "btcopilot.metered.claude_text_sync",
        lambda content, **kw: Text(read, Spent(), Served("claude-opus-5-5")),
    )
    coach.record()
    response = coach.web.post(
        "/app/chat",
        data={
            "statement": "My aunt sent me this page of family notes.",
            "file": (io.BytesIO(data), "hale-notes.pdf"),
        },
        content_type="multipart/form-data",
        headers={"X-CSRFToken": coach.token},
    )
    assert response.status_code == 202, response.get_data(as_text=True)
    replied(response)
    people = coach.people
    assert [len(named(people, n)) for n in ("Ada", "Hugh", "Colm")] == [1, 1, 1]
    kinds = {e["kind"] for e in coach.events}
    assert {"married", "death"} <= kinds, kinds
    years = {e.get("dateTime", "")[:4] for e in coach.events}
    assert {"1950", "1974", "1978", "2001"} <= years, years
