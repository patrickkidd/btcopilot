"""Timeline picture data for the companion page, computed from committed
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
CHAPTER_SPLIT_DAYS = 3 * 365
CHAPTER_MERGE_DAYS = 6 * 365
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


def _date_phrase(date: datetime.date, certainty: str) -> str:
    if certainty == DateCertainty.Approximate.value:
        return f"around {date.year}, give or take a year"
    return f"in {date.strftime('%B %Y')}"


def _sentence(base: str, date: datetime.date | None, certainty: str) -> str:
    base = base[0].upper() + base[1:] if base else base
    if date is None:
        return f"{base} — no date yet."
    return f"{base}, {_date_phrase(date, certainty)}."


def _person_label(person: dict | None) -> str:
    name = person.get("name") if person else None
    return name or "Someone"


def _event_base(event: dict, variable: str, direction: str, name: str) -> str:
    description = event.get("description")
    if description:
        return description
    noun = dict(VARIABLES)[variable]
    return f"{name}'s {noun} {PHRASES[variable][direction]}"


def _structural_base(event: dict, kind: str, people_by_id: dict) -> str:
    description = event.get("description")
    if description:
        return description
    person = people_by_id.get(event.get("person"))
    spouse = people_by_id.get(event.get("spouse"))
    child = people_by_id.get(event.get("child"))
    if kind in (EventKind.Birth.value, EventKind.Adopted.value) and child:
        return f"{_person_label(child)} was born"
    label = EventKind(kind).menuLabel().lower()
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
    """The words the picture and the list show for one event."""
    name = _person_label(people_by_id.get(event.get("person")))
    for variable, _ in VARIABLES:
        direction = _enum_val(event.get(variable))
        if direction:
            return _event_base(event, variable, direction, name)
    kind = _enum_val(event.get("kind"))
    if kind and kind != EventKind.Shift.value:
        return _structural_base(event, kind, people_by_id)
    description = event.get("description")
    if description:
        return description
    relationship = _enum_val(event.get("relationship"))
    if relationship:
        return f"{name}: {RelationshipKind(relationship).menuLabel().lower()}"
    return "Something happened"


def _subject(event: dict, people_by_id: dict) -> dict | None:
    """Birth and adoption are about the child; every other kind is about the
    person (btcopilot/CLAUDE.md, Event Field Semantics)."""
    kind = _enum_val(event.get("kind"))
    if kind in (EventKind.Birth.value, EventKind.Adopted.value) and event.get("child"):
        return people_by_id.get(event["child"])
    return people_by_id.get(event.get("person"))


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
        chunk["person_name"] = _person_label(_subject(event, people_by_id))
        chunk["sentence"] = _sentence(
            chunk["label"],
            None if _undated(chunk) else _parse_iso_date(chunk["dateTime"]),
            _certainty(chunk),
        )
        events.append(chunk)
    return sorted(events, key=lambda e: (_undated(e), e["dateTime"] or "", e["id"]))


def _group_by_gap(dated: list[tuple[dict, datetime.date]]) -> list[list]:
    """Chapters are episodes: a run of events with no long silence in it. A
    lone event next to a chapter belongs to it rather than standing alone."""
    groups = []
    for chunk, date in dated:
        if groups and (date - groups[-1][-1][1]).days > CHAPTER_SPLIT_DAYS:
            groups.append([])
        elif not groups:
            groups.append([])
        groups[-1].append((chunk, date))
    for i in range(len(groups) - 1, -1, -1):
        if len(groups[i]) != 1:
            continue
        previous = groups[i - 1] if i else None
        following = groups[i + 1] if i + 1 < len(groups) else None
        before = (groups[i][0][1] - previous[-1][1]).days if previous else None
        after = (following[0][1] - groups[i][0][1]).days if following else None
        reach = [
            d for d in (before, after) if d is not None and d <= CHAPTER_MERGE_DAYS
        ]
        if not reach:
            continue
        if (
            before is not None
            and before in reach
            and (after is None or before <= after)
        ):
            previous.extend(groups.pop(i))
        else:
            following[:0] = groups.pop(i)
    return groups


def _chapter_label(start: datetime.date, end: datetime.date) -> str:
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


def _chapters(events: list[dict], clusters: list[dict]) -> list[dict]:
    """A chapter is a grouping the picture draws. A stored cluster is one,
    because clusters are what the coach names; whatever no cluster claims is
    grouped by the silences between events."""
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
            continue
        claimed.update(chunk["id"] for chunk, _ in group)
        groups.append((group, cluster))
    rest = [pair for pair in dated if pair[0]["id"] not in claimed]
    groups.extend((group, None) for group in _group_by_gap(rest))
    groups.sort(key=lambda pair: pair[0][0][1])

    chapters = []
    previous_end = None
    for index, (group, cluster) in enumerate(groups):
        start, end = group[0][1], group[-1][1]
        chapters.append(
            {
                "id": f"ch{index}",
                "label": _chapter_label(start, end),
                "title": (cluster or {}).get("title") or _chapter_label(start, end),
                "summary": (cluster or {}).get("summary"),
                "cluster_ids": [cluster["id"]] if cluster else [],
                "start": start.isoformat(),
                "end": end.isoformat(),
                "event_ids": [chunk["id"] for chunk, _ in group],
                "count": len(group),
                "gap_days": (start - previous_end).days if previous_end else 0,
            }
        )
        previous_end = end
    return chapters


def aimable(refs: list[Ref], data: DiagramData) -> list[Ref]:
    """A chip the picture cannot go to is not a chip. `resolve` keeps only
    references the diagram holds; this keeps only the ones that land in a
    chapter, which is the only place the picture can aim."""
    people_by_id = {
        p["id"]: p
        for p in data.people
        if isinstance(p, dict) and p.get("id") is not None
    }
    events = _events_payload(data, people_by_id)
    chapters = _chapters(events, data.clusters)
    dated = {event["id"]: event for event in events if not _undated(event)}
    in_chapters = {
        event_id for chapter in chapters for event_id in chapter["event_ids"]
    }
    named_clusters = {name for chapter in chapters for name in chapter["cluster_ids"]}

    kept = []
    for ref in refs:
        if ref.kind is RefKind.Events:
            if not in_chapters.intersection(ref.event_ids):
                _log.warning(f"Reference {ref.label!r} names no event on the line")
                continue
        elif ref.kind is RefKind.Person:
            if not any(
                _links(event, ref.person_id)
                for event_id, event in dated.items()
                if event_id in in_chapters
            ):
                _log.warning(f"Reference {ref.label!r} names a person with no events")
                continue
        elif ref.kind is RefKind.Range:
            if not any(
                ref.start <= event["dateTime"] <= ref.end
                for event_id, event in dated.items()
                if event_id in in_chapters
            ):
                _log.warning(f"Reference {ref.label!r} covers no event on the line")
                continue
        elif ref.kind is RefKind.Chapter:
            if ref.cluster_id not in named_clusters:
                _log.warning(f"Reference {ref.label!r} names no chapter on the line")
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
                "gender": _enum_val(p.get("gender")),
                "primary": bool(p.get("primary")),
            }
            for p in people
        ],
        "events": events,
        "chapters": _chapters(events, data.clusters),
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
