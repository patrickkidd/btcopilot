"""Timeline picture data for the chat page, computed from committed
diagram state per doc/DRAWABILITY.md: 3-point line rule, certainty bands,
gap vs recorded no-change, undated shelf, deterministic order questions."""

import datetime
import logging
from dataclasses import MISSING, fields as dc_fields

from btcopilot.personal.intake import _enum_val, _parse_iso_date
from btcopilot.personal.refs import Ref, RefKind
from btcopilot.schema import (
    DateCertainty,
    DiagramData,
    Event,
    EventKind,
    RelationshipKind,
    TraceKey,
    VariableShift,
)

_log = logging.getLogger(__name__)

DATE_FIELDS = ("dateTime", "endDateTime")
GAP_DAYS = 730
STRIP_MAX_LANES = 2
BAND_DAYS = {
    DateCertainty.Certain.value: 7,
    DateCertainty.Approximate.value: 365,
}

VARIABLES = (
    ("symptom", "symptoms"),
    ("anxiety", "anxiety"),
    ("functioning", "functioning"),
)

PHRASES = {
    "symptom": {"up": "got worse", "down": "eased", "same": "stayed the same"},
    "anxiety": {"up": "went up", "down": "came down", "same": "stayed level"},
    "functioning": {"up": "improved", "down": "slipped", "same": "held steady"},
}

# A moment's words are who and what (owner ruling, 2026-09-09): the who comes
# from the event's links alone, and the what never says a linked person's name.
# For the kinds that describe themselves, the kind IS what happened.
KIND_WORDS = {
    EventKind.Birth.value: "born",
    EventKind.Adopted.value: "adopted",
    EventKind.Married.value: "married",
    EventKind.Separated.value: "separated",
    EventKind.Divorced.value: "divorced",
    EventKind.Bonded.value: "bonded",
    EventKind.Moved.value: "moved",
    EventKind.Death.value: "died",
}
PAIR_KINDS = (
    EventKind.Married.value,
    EventKind.Bonded.value,
    EventKind.Separated.value,
    EventKind.Divorced.value,
)


def _date_phrase(date: datetime.date, certainty: str) -> str:
    if certainty == DateCertainty.Approximate.value:
        return f"around {date.year}, give or take a year"
    return f"in {date.strftime('%B %Y')}"


def _sentence(base: str, date: datetime.date | None, certainty: str) -> str:
    base = base[0].upper() + base[1:] if base else base
    if date is None:
        return f"{base} — no date yet."
    return f"{base}, {_date_phrase(date, certainty)}."


def _life_event(person_id: int, events: list, kind: EventKind) -> dict | None:
    """This person's birth or death, which the record keeps as an event about
    them rather than a field on them. Birth is about the child; death is about
    the person (btcopilot/CLAUDE.md, Event Field Semantics)."""
    about = "child" if kind is EventKind.Birth else "person"
    for event in events:
        if not isinstance(event, dict):
            continue
        if _enum_val(event.get("kind")) != kind.value:
            continue
        if event.get(about) != person_id:
            continue
        return event
    return None


def _born(person_id: int, events: list) -> str | None:
    """The date on this person's birth event, if the record holds one."""
    event = _life_event(person_id, events, EventKind.Birth)
    date = _parse_iso_date(event.get("dateTime")) if event else None
    return date.isoformat() if date else None


def _life_id(person_id: int, events: list, kind: EventKind) -> int | None:
    event = _life_event(person_id, events, kind)
    return event.get("id") if event else None


def _person_label(person: dict | None) -> str:
    name = person.get("name") if person else None
    return name or "Someone"


def _shift_words(variable: str, direction: str) -> str:
    return f"{dict(VARIABLES)[variable]} {PHRASES[variable][direction]}"


def _event_base(event: dict, variable: str, direction: str, name: str) -> str:
    description = event.get("description")
    if description:
        return description
    return f"{name}'s {_shift_words(variable, direction)}"


def _structural_base(event: dict, kind: str, people_by_id: dict) -> str:
    """A whole sentence about one structural event, for the places that stand
    alone (the order question, a couple's lane) rather than beside a who."""
    person = people_by_id.get(event.get("person"))
    spouse = people_by_id.get(event.get("spouse"))
    child = people_by_id.get(event.get("child"))
    label = KIND_WORDS.get(kind) or EventKind(kind).menuLabel().lower()
    if kind in (EventKind.Birth.value, EventKind.Adopted.value) and child:
        return f"{_person_label(child)} was {label}"
    if person and spouse:
        return f"{_person_label(person)} and {_person_label(spouse)} {label}"
    if person:
        return f"{_person_label(person)} {label}"
    return label


def _certainty(event: dict) -> str:
    return _enum_val(event.get("dateCertainty")) or DateCertainty.Certain.value


def event_payload(event: dict) -> dict:
    """One committed event chunk as JSON: every field the schema declares, enum
    values out of enums, Qt dates out of dates. A stored event only carries the
    fields something set, and the page is entitled to the whole shape."""
    out = {name: value for name, value in _event_defaults()}
    out.update({key: _enum_val(value) for key, value in event.items()})
    for key in DATE_FIELDS:
        date = _parse_iso_date(event.get(key))
        out[key] = date.isoformat() if date else None
    return out


def _event_defaults():
    for f in dc_fields(Event):
        if f.default_factory is not MISSING:
            yield f.name, f.default_factory()
        else:
            yield f.name, _enum_val(None if f.default is MISSING else f.default)


def _label(event: dict, people_by_id: dict) -> str:
    """What happened, with no linked person's name in it: the who is said by
    the event's links, not twice (owner ruling, 2026-09-09)."""
    description = (event.get("description") or "").strip()
    kind = _enum_val(event.get("kind"))
    if kind in KIND_WORDS:
        word = KIND_WORDS[kind]
        return f"{word} \u00b7 {description}" if description else word
    for variable, _ in VARIABLES:
        direction = _enum_val(event.get(variable))
        if direction:
            return description or _shift_words(variable, direction)
    if description:
        return description
    relationship = _enum_val(event.get("relationship"))
    if relationship:
        return RelationshipKind(relationship).menuLabel().lower()
    return "Something happened"


def _who(event: dict, people_by_id: dict) -> str:
    """Who the moment is about, from the event's links alone. Birth and
    adoption are about the child; a pair-bond kind and a shift with a spouse
    are about both; a shift aimed at someone is about that pair."""
    kind = _enum_val(event.get("kind"))
    if kind in (EventKind.Birth.value, EventKind.Adopted.value):
        return _person_label(people_by_id.get(event.get("child")))
    person = _person_label(people_by_id.get(event.get("person")))
    spouse = event.get("spouse")
    if spouse is not None and (kind in PAIR_KINDS or kind == EventKind.Shift.value):
        return f"{person} & {_person_label(people_by_id.get(spouse))}"
    targets = event.get("relationshipTargets") or []
    if kind == EventKind.Shift.value and targets:
        return f"{person} \u2192 {_person_label(people_by_id.get(targets[0]))}"
    return person


def _undated(chunk: dict) -> bool:
    return (
        not chunk["dateTime"]
        or chunk.get("dateCertainty") == DateCertainty.Unknown.value
    )


def _events_payload(data: DiagramData, people_by_id: dict) -> list[dict]:
    events = []
    for event in data.events:
        if not isinstance(event, dict) or event.get("id") is None:
            continue
        chunk = event_payload(event)
        chunk["label"] = _label(event, people_by_id)
        chunk["person_name"] = _who(event, people_by_id)
        chunk["sentence"] = _sentence(
            chunk["label"],
            None if _undated(chunk) else _parse_iso_date(chunk["dateTime"]),
            _certainty(chunk),
        )
        events.append(chunk)
    return sorted(events, key=lambda e: (_undated(e), e["dateTime"] or "", e["id"]))


def _cluster_label(start: datetime.date, end: datetime.date) -> str:
    return str(start.year) if start.year == end.year else f"{start.year}–{end.year}"


def _cluster_group(cluster: dict, by_id: dict, claimed: set) -> list:
    """The dated events one stored cluster owns: the ones it names, or the ones
    inside its date range when it names none. An event belongs to one cluster."""
    ids = [
        event_id
        for event_id in (cluster.get("eventIds") or [])
        if event_id in by_id and event_id not in claimed
    ]
    if ids:
        return sorted((by_id[event_id] for event_id in ids), key=lambda pair: pair[1])
    start = _parse_iso_date(cluster.get("startDate"))
    if start is None:
        return []
    end = _parse_iso_date(cluster.get("endDate")) or start
    return sorted(
        (
            pair
            for event_id, pair in by_id.items()
            if event_id not in claimed and start <= pair[1] <= end
        ),
        key=lambda pair: pair[1],
    )


def _drawn_clusters(events: list[dict], clusters: list[dict]) -> list[dict]:
    """The clusters the picture draws, which are the clusters the record holds.
    A moment no cluster claims is a moment on its own: it stays a dot on the
    wire rather than being boxed with whatever happened near it."""
    dated = [
        (chunk, datetime.date.fromisoformat(chunk["dateTime"]))
        for chunk in events
        if not _undated(chunk)
    ]
    by_id = {chunk["id"]: (chunk, date) for chunk, date in dated}
    claimed: set = set()
    groups: list[tuple[list, dict | None]] = []
    for cluster in clusters:
        if not isinstance(cluster, dict) or not cluster.get("id"):
            continue
        group = _cluster_group(cluster, by_id, claimed)
        if not group:
            # Re-detection removes a cluster whose events are gone, so this
            # should not happen; say so rather than let the row disappear.
            _log.warning(
                f"Stored cluster {cluster['id']} holds no event on the line"
            )
            continue
        claimed.update(chunk["id"] for chunk, _ in group)
        groups.append((group, cluster))
    groups.sort(key=lambda pair: pair[0][0][1])

    drawn = []
    previous_end = None
    for group, cluster in groups:
        start, end = group[0][1], group[-1][1]
        drawn.append(
            {
                # It carries the record's own id, so a chip written about it
                # resolves in the record.
                "id": str(cluster["id"]),
                "label": _cluster_label(start, end),
                "title": (
                    cluster.get("name") or cluster.get("title") or _cluster_label(start, end)
                ),
                "summary": cluster.get("summary"),
                # Why these events are one episode, in the coach's own sentence.
                "reason": cluster.get("reason"),
                "cluster_ids": [str(cluster["id"])],
                "source": cluster.get("source"),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "event_ids": [chunk["id"] for chunk, _ in group],
                "count": len(group),
                "gap_days": (start - previous_end).days if previous_end else 0,
            }
        )
        previous_end = end
    return drawn


def aimable(refs: list[Ref], data: DiagramData) -> list[Ref]:
    """A chip the picture cannot go to is not a chip. `resolve` keeps only
    references the diagram holds; this keeps the ones the picture can aim at,
    which is any dated moment on the wire and any cluster it draws. A moment
    inside no cluster is still a dot, and a chip naming it lights that dot."""
    people_by_id = {
        p["id"]: p
        for p in data.people
        if isinstance(p, dict) and p.get("id") is not None
    }
    events = _events_payload(data, people_by_id)
    clusters = _drawn_clusters(events, data.clusters)
    dated = {event["id"]: event for event in events if not _undated(event)}
    named_clusters = {name for cluster in clusters for name in cluster["cluster_ids"]}

    kept = []
    for ref in refs:
        if ref.kind is RefKind.Events:
            if not dated.keys() & set(ref.event_ids):
                _log.warning(f"Reference {ref.label!r} names no event on the line")
                continue
        elif ref.kind is RefKind.Person:
            if not any(_links(event, ref.person_id) for event in dated.values()):
                _log.warning(f"Reference {ref.label!r} names a person with no events")
                continue
        elif ref.kind is RefKind.Range:
            if not any(
                ref.start <= event["dateTime"] <= ref.end for event in dated.values()
            ):
                _log.warning(f"Reference {ref.label!r} covers no event on the line")
                continue
        elif ref.kind is RefKind.Cluster:
            if ref.cluster_id not in named_clusters:
                _log.warning(f"Reference {ref.label!r} names no cluster on the line")
                continue
        kept.append(ref)
    return kept


def _links(event: dict, person_id: int) -> bool:
    return person_id in (
        event.get("person"),
        event.get("spouse"),
        event.get("child"),
    ) or person_id in (event.get("relationshipTargets") or [])


def build_timeline(data: DiagramData) -> dict:
    people = [p for p in data.people if isinstance(p, dict) and p.get("id") is not None]
    people_by_id = {p["id"]: p for p in people}

    dated = []
    shelf = []
    for event in data.events:
        if not isinstance(event, dict):
            continue
        date = _parse_iso_date(event.get("dateTime"))
        certainty = _certainty(event)
        if date is None or certainty == DateCertainty.Unknown.value:
            base = _label(event, people_by_id)
            shelf.append(
                {
                    "event_id": event.get("id"),
                    "label": base,
                    "sentence": _sentence(base, None, certainty),
                }
            )
        else:
            dated.append((event, date, certainty))

    lanes = []
    for person in people:
        name = _person_label(person)
        for variable, noun in VARIABLES:
            marks = []
            for event, date, certainty in dated:
                if event.get("person") != person["id"]:
                    continue
                direction = _enum_val(event.get(variable))
                if direction is None:
                    continue
                marks.append((date, event, certainty, direction))
            if not marks:
                continue
            marks.sort(key=lambda m: (m[0], m[1].get("id") or 0))

            value = 0
            points = []
            same_marks = []
            for date, event, certainty, direction in marks:
                if direction == VariableShift.Up.value:
                    value += 1
                elif direction == VariableShift.Down.value:
                    value -= 1
                entry = {
                    "event_id": event.get("id"),
                    "date": date.isoformat(),
                    "band_days": BAND_DAYS[certainty],
                    "certainty": certainty,
                    "value": value,
                    "sentence": _sentence(
                        _event_base(event, variable, direction, name), date, certainty
                    ),
                }
                if direction == VariableShift.Same.value:
                    same_marks.append(entry)
                else:
                    entry["direction"] = direction
                    points.append(entry)

            directed_count = len(points)
            has_line = directed_count >= 3
            ordered = sorted(points + same_marks, key=lambda e: e["date"])
            segments = []
            if has_line:
                for a, b in zip(ordered, ordered[1:]):
                    da = datetime.date.fromisoformat(a["date"])
                    db_ = datetime.date.fromisoformat(b["date"])
                    segments.append(
                        {
                            "a": a["date"],
                            "b": b["date"],
                            "va": a["value"],
                            "vb": b["value"],
                            "gap": (db_ - da).days > GAP_DAYS,
                        }
                    )
            values = [e["value"] for e in ordered]
            lanes.append(
                {
                    "key": f"p{person['id']}:{variable}",
                    "person": person["id"],
                    "variable": variable,
                    "label": f"{name} — {noun}",
                    "points": points,
                    "same_marks": same_marks,
                    "segments": segments,
                    "has_line": has_line,
                    "directed_count": directed_count,
                    "v_min": min(values + [0]),
                    "v_max": max(values + [0]),
                }
            )

    bonds = []
    bond_lanes = []
    for bond in data.pair_bonds:
        if not isinstance(bond, dict) or bond.get("id") is None:
            continue
        pair = {bond.get("person_a"), bond.get("person_b")} - {None}
        label = " & ".join(_person_label(people_by_id.get(pid)) for pid in sorted(pair))
        bonds.append(
            {
                "id": bond["id"],
                "person_a": bond.get("person_a"),
                "person_b": bond.get("person_b"),
                "label": label,
            }
        )
        marks = []
        for event, date, certainty in dated:
            kind = _enum_val(event.get("kind"))
            relationship = _enum_val(event.get("relationship"))
            try:
                is_bond_kind = EventKind(kind).isPairBond()
            except ValueError:
                continue
            if event.get("person") not in pair:
                continue
            if is_bond_kind:
                spouse = event.get("spouse")
                if spouse is not None and spouse not in pair:
                    continue
                label_word = kind
                base = _structural_base(event, kind, people_by_id)
            elif relationship and set(event.get("relationshipTargets") or []) & pair:
                label_word = relationship
                base = event.get("description") or relationship
            else:
                continue
            marks.append(
                {
                    "event_id": event.get("id"),
                    "date": date.isoformat(),
                    "band_days": BAND_DAYS[certainty],
                    "certainty": certainty,
                    "kind": label_word,
                    "sentence": _sentence(base, date, certainty),
                }
            )
        marks.sort(key=lambda m: m["date"])
        if marks:
            bond_lanes.append(
                {
                    "key": f"b{bond['id']}",
                    "pair_bond": bond["id"],
                    "label": label,
                    "marks": marks,
                }
            )

    questions = _order_questions(lanes, dated, people_by_id)

    # Resting strip: the user's own most-directed lane first, then the most
    # active couple/household lane (coach-chosen defaults and user pins come
    # later; nothing person-specific is hardcoded).
    def _lane_rank(lane):
        # The symptom lane is the presenting problem (DRAWABILITY): it leads
        # whenever it can draw a line, ahead of busier anxiety/functioning.
        return (
            lane["variable"] == "symptom" and lane["has_line"],
            lane["directed_count"],
            len(lane["points"]) + len(lane["same_marks"]),
        )

    def _strip_person_lane(lane):
        ordered = sorted(lane["points"] + lane["same_marks"], key=lambda e: e["date"])
        return {
            "key": lane["key"],
            "label": lane["label"],
            "line": (
                [[e["date"], e["value"]] for e in ordered] if lane["has_line"] else None
            ),
            "marks": [
                {"type": "dot", "date": e["date"], "value": e["value"]} for e in ordered
            ],
            "questions": [
                {"type": "question", "date": q["date"]}
                for q in questions
                if q["lane"] == lane["key"]
            ],
            "v_min": lane["v_min"],
            "v_max": lane["v_max"],
        }

    primary_ids = {p["id"] for p in people if p.get("primary")}
    own = sorted(
        [l for l in lanes if l["person"] in primary_ids], key=_lane_rank, reverse=True
    )
    others = sorted(
        [l for l in lanes if l["person"] not in primary_ids],
        key=_lane_rank,
        reverse=True,
    )
    busiest_bond = max(bond_lanes, key=lambda l: len(l["marks"]), default=None)

    strip_lanes = [_strip_person_lane(lane) for lane in (own[:1] or others[:1])]
    if busiest_bond is not None and len(strip_lanes) < STRIP_MAX_LANES:
        strip_lanes.append(
            {
                "key": busiest_bond["key"],
                "label": busiest_bond["label"],
                "line": None,
                "marks": [
                    {"type": "dot", "date": m["date"], "value": 0}
                    for m in busiest_bond["marks"]
                ],
                "questions": [],
                "v_min": 0,
                "v_max": 0,
            }
        )
    for lane in own[1:] + others:
        if len(strip_lanes) >= STRIP_MAX_LANES:
            break
        if any(s["key"] == lane["key"] for s in strip_lanes):
            continue
        strip_lanes.append(_strip_person_lane(lane))

    drawn_dates = sorted(date.isoformat() for _, date, _ in dated)
    axis = {"min": drawn_dates[0], "max": drawn_dates[-1]} if drawn_dates else None

    coded_in = {
        event["id"]: {
            "discussion_id": event[TraceKey.Discussion.value],
            "statement_id": event.get(TraceKey.Statement.value),
        }
        for event in data.events
        if isinstance(event, dict) and event.get(TraceKey.Discussion.value)
    }

    events = _events_payload(data, people_by_id)
    return {
        "coded_in": coded_in,
        "people": [
            {
                "id": p["id"],
                "name": _person_label(p),
                "last_name": p.get("last_name"),
                "gender": _enum_val(p.get("gender")),
                "notes": p.get("notes"),
                "primary": bool(p.get("primary")),
                # when someone was born is an event about them, not a field on
                # them, so the list is handed the date its rows are ordered by
                "birth": _born(p["id"], data.events),
                # the two events the person editor sends the reader to
                "birth_event": _life_id(p["id"], data.events, EventKind.Birth),
                "death_event": _life_id(p["id"], data.events, EventKind.Death),
            }
            for p in people
        ],
        "events": events,
        "clusters": _drawn_clusters(events, data.clusters),
        "pair_bonds": bonds,
        "lanes": lanes,
        "bond_lanes": bond_lanes,
        "strip": {"lanes": strip_lanes},
        "shelf": shelf,
        "questions": questions,
        "axis": axis,
    }


def _order_questions(lanes: list, dated: list, people_by_id: dict) -> list:
    """DRAWABILITY's deterministic query: a '?' between a variable point and a
    structural family event whose certainty ranges touch."""
    structural = []
    for event, date, certainty in dated:
        kind = _enum_val(event.get("kind"))
        try:
            if not EventKind(kind).isStructural():
                continue
        except ValueError:
            continue
        band = datetime.timedelta(days=BAND_DAYS[certainty])
        structural.append((event, date - band, date + band, date, kind))

    questions = []
    seen = set()
    for lane in lanes:
        for point in lane["points"]:
            p_date = datetime.date.fromisoformat(point["date"])
            band = datetime.timedelta(days=point["band_days"])
            p_lo, p_hi = p_date - band, p_date + band
            for event, s_lo, s_hi, s_date, kind in structural:
                if event.get("id") == point["event_id"]:
                    continue
                if s_lo > p_hi or s_hi < p_lo:
                    continue
                pair_key = (point["event_id"], event.get("id"))
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                mid = (
                    min(p_date, s_date)
                    + (max(p_date, s_date) - min(p_date, s_date)) / 2
                )
                family_base = _structural_base(event, kind, people_by_id)
                point_base = point["sentence"].rstrip(".").split(",")[0].lower()
                questions.append(
                    {
                        "lane": lane["key"],
                        "date": mid.isoformat(),
                        "event_id": point["event_id"],
                        "other_event_id": event.get("id"),
                        "sentence": (
                            f"Which came first — {family_base.lower()}, or when "
                            f"{point_base}? The dates are too close to tell."
                        ),
                    }
                )
    return questions
