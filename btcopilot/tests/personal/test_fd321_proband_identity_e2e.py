"""FD-321 C9 (e2e): with a NAMED primary (proband) on the diagram, real extraction must
reference the first-person speaker by their committed id, NOT fabricate a duplicate person
for "I"/"me". A control with an UNNAMED primary shows the duplication the fix removes.

Requires GOOGLE_GEMINI_API_KEY.
"""

import asyncio

import pytest

from btcopilot.schema import DiagramData
from btcopilot.pdp import import_text


CONVERSATION = (
    "I lost my job at the factory last June and it's been hard on my marriage to Alex. "
    "My younger sister Beth moved to Denver last year and we barely talk now. "
    "I've always been the responsible one — when our dad died in 2019 I handled everything."
)


def _named_diagram(named: bool) -> DiagramData:
    dd = DiagramData()
    primary = {"id": 1, "last_name": "Lee", "gender": "male", "primary": True}
    if named:
        primary["name"] = "Jordan"
    dd.people = [primary]
    return dd


def _self_duplicates(deltas):
    """New (negative-id) people that are really the first-person speaker recreated:
    name matches the proband, or a generic self-label."""
    bad = {"jordan", "lee", "jordan lee", "client", "the client", "the user", "narrator", "me", "myself"}
    out = []
    for p in deltas.people:
        if p.id < 0:
            full = f"{(p.name or '').strip()} {(p.last_name or '').strip()}".strip().lower()
            if (p.name or "").strip().lower() in bad or full in bad or not (p.name or "").strip():
                out.append((p.id, p.name, p.last_name))
    return out


@pytest.mark.e2e
def test_named_proband_not_duplicated():
    """Named primary -> the speaker is referenced by committed id 1, no self-duplicate."""
    dd = _named_diagram(named=True)
    _pdp, deltas = asyncio.run(import_text(dd, CONVERSATION))
    dups = _self_duplicates(deltas)
    assert dups == [], (
        f"Speaker recreated as a new person despite a named primary. "
        f"Self-duplicates: {dups}. All new people: {[(p.id, p.name, p.last_name) for p in deltas.people]}"
    )
    # Sister Beth is a genuinely new person and SHOULD appear.
    assert any((p.name or '').lower() == 'beth' for p in deltas.people), (
        f"Beth (a real new person) should be extracted: {[(p.id, p.name) for p in deltas.people]}"
    )
