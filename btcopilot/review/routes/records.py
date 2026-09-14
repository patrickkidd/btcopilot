"""Records: the family each coding was written on, which is what a person or a
pair bond has to be drawn against.

A version of a person says almost nothing on its own — the argument is who they
are bonded to and whose child they are — so the ballot and the meeting draw each
version as a family fragment, and this is where the family around it comes from
(R-0326).
"""

from flask import jsonify, request

from btcopilot.review import adapter, snapshot
from btcopilot.review.routes import bp, coder, cut_or_404, human_codings, sees_others

PERSON_FIELDS = ("id", "name", "last_name", "gender", "parents")
BOND_FIELDS = ("id", "person_a", "person_b", "married")
EVENT_FIELDS = ("id", "kind", "person", "spouse", "child", "dateTime")


def _fields(item: dict, names) -> dict:
    return {name: adapter.plain(item.get(name)) for name in names}


def record_payload(coding_id: int, data: dict) -> dict:
    return {
        "coding_id": coding_id,
        "people": [_fields(p, PERSON_FIELDS) for p in data.get("people") or []],
        "pair_bonds": [_fields(b, BOND_FIELDS) for b in data.get("pair_bonds") or []],
        "events": [_fields(e, EVENT_FIELDS) for e in data.get("events") or []],
    }


@bp.route("/records")
def record_index():
    """One row per coding of a cut: the people, the bonds and the events the
    drawing needs. Blind until your own Done, like the items themselves."""
    user = coder()
    cut = cut_or_404(request.args.get("cut_id", type=int) or 0)
    if not sees_others(cut, user):
        return jsonify([])
    people = human_codings(cut)
    return jsonify(
        [
            record_payload(
                coding.id,
                adapter.record_of(adapter.diagram_of(coding.diagram_id)),
            )
            for coding in snapshot.done_codings(cut)
            if coding.id in people
        ]
    )
