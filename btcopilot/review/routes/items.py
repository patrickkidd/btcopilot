"""Items: one event, person or pair bond as every coder saw it, and the
decision the meeting makes on it."""

import enum

from flask import jsonify, request

from btcopilot.extensions import db
from btcopilot.review import adapter, decision, pairing, snapshot
from btcopilot.review.models import Item, ReviewStatus
from btcopilot.schema import ItemKind
from btcopilot.review.routes import (
    admin,
    bp,
    coder,
    cut_or_404,
    human_codings,
    item_or_404,
    reads_ballot,
)


class Decision(enum.StrEnum):
    Keep = "keep"
    Change = "change"
    Unresolved = "unresolved"
    Reopen = "reopen"


CODED_KINDS = (ItemKind.Event, ItemKind.Person, ItemKind.PairBond)

DECISION_STATUS = {
    Decision.Keep: ReviewStatus.Decided,
    Decision.Change: ReviewStatus.Decided,
    Decision.Unresolved: ReviewStatus.Unresolved,
    Decision.Reopen: ReviewStatus.Disputed,
}


def payload(item: Item, named: bool) -> dict:
    data = item.as_dict()
    # The pairing call's reason and confidence are Patrick's, before the vote
    # opens, when only he reads the items; a coder never reads them (R-0961).
    if item.cut.vote_opened_at is None:
        data["pairing_confidence"] = (
            item.pairing_confidence and item.pairing_confidence.value
        )
    else:
        data.pop("pairing_reason", None)
        data.pop("pairing_confidence", None)
    if not named:
        data["opinions"] = [
            {k: v for k, v in opinion.items() if k != "user_id"}
            for opinion in (item.opinions or [])
        ]
        data.pop("user_id", None)
        data.pop("kept_coding_id", None)
    return data


def read(cut) -> dict:
    """What every opinion needs beside its own words: the turn the coder wrote it
    from, and the people of the record they wrote it on. Read once per cut, and
    only for the codings people made (R-0254)."""
    people = human_codings(cut)
    found = {}
    for coding in snapshot.done_codings(cut):
        if coding.id not in people:
            continue
        record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
        found[coding.id] = {
            "turns": {
                kind: adapter.coded_in(coding.diagram_id, kind) for kind in CODED_KINDS
            },
            "people": record.get("people") or [],
            "user_id": coding.user_id,
            "coder": adapter.initials(db.session.get(adapter.User, coding.user_id)),
        }
    return found


def voting_payload(
    item: Item, records: dict, places: dict[int, int], named: bool = False
) -> dict:
    """One item as the ballot reads it: the opinions without names, each with the
    turn it came from and the name of the person it is about, and how many
    coders left the item out (R-0252, R-0257). The meeting reads the same item
    with the names on, which is where they first appear (R-0252). Every line
    carries its number among the cut's own lines, and the item how many the
    cut holds, since the cut's statement ids skip (R-0974)."""
    data = payload(item, named=named)
    raws = [one for one in item.opinions or [] if one["coding_id"] in records]
    data["opinions"] = [
        opinion
        for raw, opinion in zip(item.opinions or [], data["opinions"])
        if raw["coding_id"] in records
    ]
    coders = len(records)
    data["coders"] = coders
    data["not_coded"] = max(coders - len({one["coding_id"] for one in raws}), 0)
    for raw, opinion in zip(raws, data["opinions"]):
        record = records[raw["coding_id"]]
        opinion["statement_id"] = _turn_of(item, raw, record)
        opinion["line"] = _line(opinion["statement_id"], places)
        opinion["person_name"] = _name_of(raw["item"], record)
        opinion["toward_names"] = _toward_names(raw["item"], record)
        if named:
            opinion["user_id"] = record["user_id"]
            opinion["coder"] = record["coder"]
    data["people"] = _people_of(item, records)
    data["lines"] = len(places)
    data["line"] = next((one["line"] for one in data["opinions"] if one["line"]), None)
    return data


def _turn_of(item: Item, raw: dict, record: dict) -> int | None:
    """Which turn of the conversation this coder wrote this opinion from. The
    record stamps the turn on every item it writes, so a person and a pair bond
    trace back the same way an event does, each coder to their own turn
    (R-0278). Nothing is stamped on what the coach replayed or what was typed
    in the editor, and those carry no turn."""
    if item.item_kind not in CODED_KINDS:
        return None
    try:
        item_id = int(raw["item_id"])
    except (KeyError, TypeError, ValueError):
        return None
    turns = (record.get("turns") or {}).get(item.item_kind) or {}
    return turns.get(item_id, {}).get("statement_id")


def _name_of(value: dict, record: dict) -> str | None:
    about = (
        value.get("child") if value.get("child") is not None else value.get("person")
    )
    if about is None:
        return None
    for one in record.get("people") or []:
        if str(one.get("id")) == str(about):
            return one.get("name")
    return None


def _toward_names(value: dict, record: dict) -> list[str]:
    """Who a relationship shift is toward, named as that coder's copy names
    them."""
    names = {str(one.get("id")): one.get("name") for one in record.get("people") or []}
    return [names.get(str(one)) for one in value.get("relationshipTargets") or []]


def _people_of(item: Item, records: dict) -> list[dict]:
    """The people of the record the first opinion was written on, so an opinion of
    your own can name one of them (R-0257)."""
    opinions = [one for one in item.opinions or [] if one["coding_id"] in records]
    if not opinions:
        return []
    record = records[opinions[0]["coding_id"]]
    return [
        {"id": one.get("id"), "name": one.get("name")}
        for one in record.get("people") or []
    ]


def _line(statement_id: int | None, places: dict[int, int]) -> dict | None:
    """The transcript line one version was written from, which the ballot shows
    and can open, and which is never edited there."""
    if not statement_id:
        return None
    said = adapter.statement(statement_id)
    if said is None:
        return None
    speaker = said.speaker
    return {
        "statement_id": said.id,
        "who": (speaker.name if speaker and speaker.name else None) or "Someone",
        "text": said.text or "",
        "number": places.get(said.id),
    }


@bp.route("/items")
def item_index():
    user = coder()
    # Names appear at the meeting and never before it (R-0252, R-0272): the
    # meeting screen asks for them, and only Patrick may ask.
    named = request.args.get("named") == "true"
    if named:
        admin()
    cut = cut_or_404(request.args.get("cut_id", type=int) or 0)
    if not reads_ballot(cut, user):
        return jsonify([])
    return jsonify(listing(cut.items, cut, named))


def listing(items: list[Item], cut, named: bool = False) -> list[dict]:
    records = read(cut)
    places = {
        s.id: at
        for at, s in enumerate(
            adapter.statements_between(
                cut.diagram_id, cut.start_statement_id, cut.end_statement_id
            ),
            start=1,
        )
    }
    return [
        voting_payload(i, records, places, named or cut.ratified_at is not None)
        for i in sorted(items, key=lambda i: i.id)
    ]


@bp.route("/items", methods=["POST"])
def item_create():
    """The ballot's pairings: with only a cut, the pairing job starts; with
    entries named, Patrick splits them off into a pairing of their own
    (R-0961, R-0963)."""
    user = admin()
    body = request.get_json() or {}
    cut = cut_or_404(body.get("cut_id") or 0)
    if "opinions" not in body:
        pairing.start(cut, user.id)
        return jsonify({"ballot": pairing.Ballot.Building.value}), 202
    return _moved(cut, None, body["opinions"]), 201


def _moved(cut, target: Item | None, named: list[dict]):
    touched, deleted = pairing.moved(cut, target, named)
    db.session.commit()
    return jsonify({"items": listing(touched, cut), "deleted": deleted})


@bp.route("/items/<int:item_id>", methods=["PATCH"])
def item_patch(item_id: int):
    """The meeting's decision: keep what a coder had, change it, or leave it
    unresolved. Every item must carry one before a cut is ratified (R-0257)."""
    user = admin()
    item = item_or_404(item_id)
    if item.cut.ratified_at is not None:
        raise ValueError("that cut is ratified and cannot be decided again")
    body = request.get_json() or {}
    if item.cut.vote_opened_at is None:
        # Before the vote opens a PATCH is Patrick's join (R-0963).
        return _moved(item.cut, item, body.get("opinions") or [])
    try:
        choice = Decision(body.get("choice"))
    except ValueError:
        raise ValueError("a decision is keep, change, unresolved or reopen")

    item.status = DECISION_STATUS[choice]
    item.user_id = None if choice is Decision.Reopen else user.id
    given = body.get("value")
    # Only keeping a coder's version says whose version it is; writing one out,
    # leaving it unresolved or reopening it leaves nothing lit (R-0339).
    item.kept_coding_id = (
        given.get("coding_id")
        if choice is Decision.Keep and isinstance(given, dict)
        else None
    )

    if choice is Decision.Reopen:
        item.decision_change_id = None
    elif choice is not Decision.Unresolved:
        change = decision.write(item, decision.values_of(item, given), user)
        item.decision_change_id = change.id

    db.session.commit()
    return jsonify(payload(item, True))
