"""Outstanding-intake-categories engine.

Schema-derived. No LLM calls. No conversation-history reads — coverage is
computed from committed `DiagramData` alone, so it works in returning-user
sessions where conversation history starts blank.

Consumers:
- Personal-app chat (FD-326): steers the coach toward what's missing
- Discuss-tab burn-down (FD-327)
- Plan-tab Tier (a) outstanding questions (FD-328)
"""
import enum
from dataclasses import dataclass

from btcopilot.schema import DiagramData


class DataCategory(enum.StrEnum):
    PresentingProblem = "presenting_problem"
    Mother = "mother"
    Father = "father"
    ParentsStatus = "parents_status"
    Siblings = "siblings"
    MaternalGrandparents = "maternal_grandparents"
    PaternalGrandparents = "paternal_grandparents"
    AuntsUncles = "aunts_uncles"
    Spouse = "spouse"
    Children = "children"
    NodalEvents = "nodal_events"
    # Functioning / SARF — derived from shift events on the timeline
    FamilyFunctioning = "family_functioning"
    RelationshipPatterns = "relationship_patterns"
    SymptomTimeline = "symptom_timeline"
    EventSymptomConnections = "event_symptom_connections"


class CoverageStatus(enum.StrEnum):
    NotCovered = "not_covered"
    Partial = "partial"
    Covered = "covered"


@dataclass
class CategoryCoverage:
    category: DataCategory
    status: CoverageStatus
    detail: str = ""


_NODAL_KINDS = {"death", "married", "divorced", "separated", "moved"}
_MARITAL_KINDS = {"married", "divorced", "separated", "bonded"}
_SARF_FIELDS = ("symptom", "anxiety", "relationship", "functioning")
_CONNECTION_DAYS = 365


def coverage(diagram_data: DiagramData | None) -> dict[DataCategory, CategoryCoverage]:
    if diagram_data is None:
        result = {c: CategoryCoverage(c, CoverageStatus.NotCovered) for c in DataCategory}
        result[DataCategory.PresentingProblem] = CategoryCoverage(
            DataCategory.PresentingProblem,
            CoverageStatus.Covered,
            "(conversation-derived)",
        )
        return result

    people = diagram_data.people or []
    events = diagram_data.events or []
    pair_bonds = diagram_data.pair_bonds or []

    speaker_id = _speaker_id(people)
    speaker = _person_by_id(people, speaker_id) if speaker_id else None
    parents_pb_id = speaker.get("parents") if speaker else None
    parents_pb = _pair_bond_by_id(pair_bonds, parents_pb_id) if parents_pb_id else None

    mother = _find_parent(parents_pb, people, "female")
    father = _find_parent(parents_pb, people, "male")

    result = {
        DataCategory.PresentingProblem: CategoryCoverage(
            DataCategory.PresentingProblem,
            CoverageStatus.Covered,
            "(conversation-derived)",
        ),
        DataCategory.Mother: _parent_coverage(parents_pb, people, "female", DataCategory.Mother),
        DataCategory.Father: _parent_coverage(parents_pb, people, "male", DataCategory.Father),
        DataCategory.ParentsStatus: _parents_status_coverage(parents_pb, events),
        DataCategory.Siblings: _list_coverage(
            [p for p in people
             if parents_pb_id is not None
             and p.get("parents") == parents_pb_id
             and p.get("id") != speaker_id],
            DataCategory.Siblings, "siblings",
        ),
        DataCategory.MaternalGrandparents: _grandparents_coverage(
            mother, people, pair_bonds, DataCategory.MaternalGrandparents,
        ),
        DataCategory.PaternalGrandparents: _grandparents_coverage(
            father, people, pair_bonds, DataCategory.PaternalGrandparents,
        ),
        DataCategory.AuntsUncles: _list_coverage(
            _aunts_uncles(mother, father, people), DataCategory.AuntsUncles, "aunts/uncles",
        ),
    }

    speaker_pbs = [
        pb for pb in pair_bonds
        if speaker_id is not None
        and (pb.get("person_a") == speaker_id or pb.get("person_b") == speaker_id)
    ]
    spouses = [_other_person(pb, speaker_id, people) for pb in speaker_pbs]
    spouses = [s for s in spouses if s is not None]
    result[DataCategory.Spouse] = _list_coverage(spouses, DataCategory.Spouse, "spouse(s)")

    children = []
    for pb in speaker_pbs:
        pb_id = pb.get("id")
        children.extend(p for p in people if p.get("parents") == pb_id)
    result[DataCategory.Children] = _list_coverage(children, DataCategory.Children, "children")

    nodal = [e for e in events if e.get("kind") in _NODAL_KINDS]
    if len(nodal) >= 3:
        nodal_status = CoverageStatus.Covered
    elif nodal:
        nodal_status = CoverageStatus.Partial
    else:
        nodal_status = CoverageStatus.NotCovered
    result[DataCategory.NodalEvents] = CategoryCoverage(
        DataCategory.NodalEvents, nodal_status,
        f"{len(nodal)} nodal event(s)" if nodal else "",
    )

    shifts = [e for e in events if e.get("kind") == "shift"]
    result[DataCategory.FamilyFunctioning] = _functioning_coverage(shifts)
    result[DataCategory.RelationshipPatterns] = _relationship_patterns_coverage(shifts)
    result[DataCategory.SymptomTimeline] = _symptom_timeline_coverage(shifts)
    result[DataCategory.EventSymptomConnections] = _connections_coverage(shifts, nodal)

    return result


def outstanding_categories(
    diagram_data: DiagramData | None,
) -> list[CategoryCoverage]:
    """Categories that are NotCovered or Partial. PresentingProblem excluded
    (conversation-derived, never appears as outstanding from diagram alone)."""
    return [
        c for c in coverage(diagram_data).values()
        if c.status != CoverageStatus.Covered
        and c.category != DataCategory.PresentingProblem
    ]


_PLACEHOLDER_NAME_FRAGMENTS = ("'s spouse", "'s child", "'s partner")
_PLACEHOLDER_NAMES = {"unknown", "new person", "assistant", "user"}
_ROSTER_CAP = 60


def roster_for_prompt(diagram_data: DiagramData | None) -> str:
    """Every committed, real-named person — independent of whether the speaker
    is structurally linked to them. Coverage() traverses from the speaker and
    goes blank when a link is missing; this guarantees the coach is still
    handed who is on file by name. Partner is annotated when both ends are
    named (cheap, no deep traversal)."""
    if diagram_data is None:
        return ""
    people = diagram_data.people or []
    pair_bonds = diagram_data.pair_bonds or []
    speaker_id = _speaker_id(people)

    events = diagram_data.events or []
    by_id = {
        p["id"]: p for p in people
        if isinstance(p, dict) and p.get("id") is not None
    }
    life = _life_facts_index(events)
    named = []
    for p in people:
        if not isinstance(p, dict):
            continue
        name = (p.get("name") or "").strip()
        if not name or name.lower() in _PLACEHOLDER_NAMES:
            continue
        if any(frag in name for frag in _PLACEHOLDER_NAME_FRAGMENTS):
            continue
        named.append(p)

    entries = []
    for p in named[:_ROSTER_CAP]:
        label = p["name"].strip()
        gender = p.get("gender")
        if gender in ("male", "female"):
            label += f" ({gender})"
        if p.get("id") == speaker_id:
            label += " — the user"
        else:
            partner = _roster_partner(p, speaker_id, pair_bonds, by_id)
            if partner:
                label += f" — partner of {partner}"
        facts = life.get(p.get("id"), "")
        if facts:
            label += f" [{facts}]"
        entries.append(label)

    if not entries:
        return ""
    out = "People on file: " + "; ".join(entries) + "."
    extra = len(named) - len(entries)
    if extra > 0:
        out += f" (+{extra} more)"
    return out


def _life_facts_index(events):
    """One pass over events → {person_id: "b. <date>, d. <date>"}. Committed
    dated facts the coach must not re-ask. Birth keyed by child or person,
    death by person; last dated event wins (matches prior per-person scan)."""
    born, died = {}, {}
    for e in events:
        kind = e.get("kind")
        if kind == "birth":
            d = _parse_iso_date(e.get("dateTime"))
            if d:
                for key in (e.get("child"), e.get("person")):
                    if key is not None:
                        born[key] = d
        elif kind == "death":
            p = e.get("person")
            if p is not None:
                d = _parse_iso_date(e.get("dateTime"))
                if d:
                    died[p] = d
    out = {}
    for pid in set(born) | set(died):
        parts = []
        if pid in born:
            parts.append(f"b. {born[pid].isoformat()}")
        if pid in died:
            parts.append(f"d. {died[pid].isoformat()}")
        out[pid] = ", ".join(parts)
    return out


def _roster_partner(person, speaker_id, pair_bonds, by_id):
    pid = person.get("id")
    for pb in pair_bonds:
        a, b = pb.get("person_a"), pb.get("person_b")
        if pid not in (a, b):
            continue
        other = by_id.get(b if a == pid else a)
        other_name = ((other or {}).get("name") or "").strip()
        if not other_name or other_name.lower() in _PLACEHOLDER_NAMES:
            continue
        if any(frag in other_name for frag in _PLACEHOLDER_NAME_FRAGMENTS):
            continue
        return "the user" if other and other.get("id") == speaker_id else other_name
    return None


def format_coverage_for_prompt(
    coverage_map: dict[DataCategory, CategoryCoverage],
) -> str:
    """Compact prompt fragment: 'Already known: ...' / 'Still outstanding: ...'"""
    covered, outstanding = [], []
    for cat, cov in coverage_map.items():
        if cat == DataCategory.PresentingProblem:
            continue
        label = cat.value.replace("_", " ")
        if cov.status == CoverageStatus.Covered:
            covered.append(f"{label} ({cov.detail})" if cov.detail else label)
        else:
            outstanding.append(
                f"{label} — {cov.detail}" if cov.detail else label
            )
    parts = []
    if covered:
        parts.append("Already known: " + "; ".join(covered) + ".")
    if outstanding:
        parts.append("Still outstanding: " + "; ".join(outstanding) + ".")
    return "\n".join(parts)


# ── helpers ──────────────────────────────────────────────────────────────────

def _speaker_id(people):
    for p in people:
        if isinstance(p, dict) and p.get("primary"):
            return p.get("id")
    for p in people:
        if isinstance(p, dict) and p.get("id") == 1:
            return 1
    return None


def _person_by_id(people, pid):
    if pid is None:
        return None
    return next(
        (p for p in people if isinstance(p, dict) and p.get("id") == pid),
        None,
    )


def _pair_bond_by_id(pair_bonds, pbid):
    if pbid is None:
        return None
    return next((pb for pb in pair_bonds if pb.get("id") == pbid), None)


def _find_parent(pair_bond, people, gender):
    if not pair_bond:
        return None
    for side in ("person_a", "person_b"):
        person = _person_by_id(people, pair_bond.get(side))
        if person and person.get("gender") == gender:
            return person
    return None


def _other_person(pair_bond, person_id, people):
    a, b = pair_bond.get("person_a"), pair_bond.get("person_b")
    other_id = b if a == person_id else a
    return _person_by_id(people, other_id)


def _aunts_uncles(mother, father, people):
    out = []
    for parent in (mother, father):
        if not parent:
            continue
        parent_pb = parent.get("parents")
        if not parent_pb:
            continue
        out.extend(
            p for p in people
            if p.get("parents") == parent_pb and p.get("id") != parent.get("id")
        )
    return out


def _parent_coverage(parents_pb, people, gender, cat):
    if not parents_pb:
        return CategoryCoverage(cat, CoverageStatus.NotCovered)
    parent = _find_parent(parents_pb, people, gender)
    if parent and parent.get("name"):
        return CategoryCoverage(cat, CoverageStatus.Covered, parent["name"])
    return CategoryCoverage(
        cat, CoverageStatus.Partial,
        "parents PairBond exists but parent not yet named",
    )


def _parents_status_coverage(parents_pb, events):
    if not parents_pb:
        return CategoryCoverage(DataCategory.ParentsStatus, CoverageStatus.NotCovered)
    a, b = parents_pb.get("person_a"), parents_pb.get("person_b")
    relevant = [
        e for e in events
        if e.get("kind") in _MARITAL_KINDS
        and {e.get("person"), e.get("spouse")} == {a, b}
    ]
    if relevant:
        kinds = ", ".join(e.get("kind", "") for e in relevant)
        return CategoryCoverage(
            DataCategory.ParentsStatus, CoverageStatus.Covered, kinds,
        )
    return CategoryCoverage(
        DataCategory.ParentsStatus, CoverageStatus.Partial,
        "parents PairBond exists but no marital event recorded",
    )


def _list_coverage(items, cat, label):
    if not items:
        return CategoryCoverage(cat, CoverageStatus.NotCovered)
    names = [p.get("name", "?") for p in items if p.get("name")]
    detail = (
        f"{len(items)} {label}: {', '.join(names)}"
        if names else f"{len(items)} {label}"
    )
    return CategoryCoverage(cat, CoverageStatus.Covered, detail)


def _has_sarf(event):
    return any(event.get(f) for f in _SARF_FIELDS)


def _functioning_coverage(shifts):
    coded = [e for e in shifts if _has_sarf(e)]
    n = len(coded)
    if n >= 3:
        status = CoverageStatus.Covered
    elif n >= 1:
        status = CoverageStatus.Partial
    else:
        return CategoryCoverage(DataCategory.FamilyFunctioning, CoverageStatus.NotCovered)
    return CategoryCoverage(
        DataCategory.FamilyFunctioning, status,
        f"{n} shift event(s) with SARF coding",
    )


def _relationship_patterns_coverage(shifts):
    rel = [e for e in shifts if e.get("relationship")]
    if not rel:
        return CategoryCoverage(DataCategory.RelationshipPatterns, CoverageStatus.NotCovered)
    kinds = sorted({
        _enum_val(e.get("relationship")) for e in rel if e.get("relationship")
    })
    if len(rel) >= 3 or len(kinds) >= 2:
        status = CoverageStatus.Covered
    else:
        status = CoverageStatus.Partial
    return CategoryCoverage(
        DataCategory.RelationshipPatterns, status,
        f"{len(rel)} event(s); kinds: {', '.join(kinds)}",
    )


def _symptom_timeline_coverage(shifts):
    dated_symptoms = [
        e for e in shifts
        if e.get("symptom") and e.get("dateTime")
    ]
    n = len(dated_symptoms)
    if n >= 2:
        ds = sorted(
            d for d in (_parse_iso_date(e["dateTime"]) for e in dated_symptoms)
            if d is not None
        )
        span = (
            f", span {ds[0].isoformat()} → {ds[-1].isoformat()}" if ds else ""
        )
        return CategoryCoverage(
            DataCategory.SymptomTimeline, CoverageStatus.Covered,
            f"{n} dated symptom event(s){span}",
        )
    if n == 1:
        return CategoryCoverage(
            DataCategory.SymptomTimeline, CoverageStatus.Partial,
            "1 dated symptom event",
        )
    return CategoryCoverage(
        DataCategory.SymptomTimeline, CoverageStatus.NotCovered,
    )


def _connections_coverage(shifts, nodal_events):
    nodal_dates = []
    for e in nodal_events:
        d = _parse_iso_date(e.get("dateTime"))
        if d is not None:
            nodal_dates.append(d)
    if not nodal_dates:
        return CategoryCoverage(
            DataCategory.EventSymptomConnections, CoverageStatus.NotCovered,
        )

    connected = 0
    for s in shifts:
        if not _has_sarf(s):
            continue
        sd = _parse_iso_date(s.get("dateTime"))
        if sd is None:
            continue
        if any(abs((sd - nd).days) <= _CONNECTION_DAYS for nd in nodal_dates):
            connected += 1

    if connected >= 2:
        status = CoverageStatus.Covered
    elif connected == 1:
        status = CoverageStatus.Partial
    else:
        return CategoryCoverage(
            DataCategory.EventSymptomConnections, CoverageStatus.NotCovered,
        )
    return CategoryCoverage(
        DataCategory.EventSymptomConnections, status,
        f"{connected} shift event(s) within {_CONNECTION_DAYS}d of a nodal event",
    )


def _enum_val(x):
    """Scene-stored fields may be Enum objects (e.g. RelationshipKind) or
    their string values depending on the writer — same dual-type situation
    as QDateTime dates. Normalize to the string value for compare/display."""
    return x.value if isinstance(x, enum.Enum) else x


def _parse_iso_date(s):
    """Normalize a date value to datetime.date. Real committed diagrams store
    dates as PyQt5 QDateTime/QDate (Scene format), not ISO strings. Handle
    str, datetime/date, and Qt date objects."""
    if not s:
        return None
    from datetime import date, datetime

    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    # PyQt5 QDateTime / QDate expose .toString("yyyy-MM-dd") and .date()
    to_string = getattr(s, "toString", None)
    if callable(to_string):
        try:
            iso = to_string("yyyy-MM-dd")
            return date.fromisoformat(iso[:10])
        except (ValueError, TypeError):
            return None
    try:
        return date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


def _date_label(s):
    """Human-safe date string for prompt rendering (never a Qt repr)."""
    d = _parse_iso_date(s)
    return d.isoformat() if d else "unknown"


def _grandparents_coverage(parent, people, pair_bonds, cat):
    if not parent:
        return CategoryCoverage(cat, CoverageStatus.NotCovered)
    gp_pb = _pair_bond_by_id(pair_bonds, parent.get("parents"))
    if not gp_pb:
        return CategoryCoverage(cat, CoverageStatus.NotCovered)
    gma = _find_parent(gp_pb, people, "female")
    gpa = _find_parent(gp_pb, people, "male")
    found = [p for p in (gma, gpa) if p and p.get("name")]
    if len(found) == 2:
        return CategoryCoverage(
            cat, CoverageStatus.Covered, ", ".join(p["name"] for p in found),
        )
    if len(found) == 1:
        return CategoryCoverage(
            cat, CoverageStatus.Partial, f"only {found[0]['name']} known",
        )
    return CategoryCoverage(
        cat, CoverageStatus.Partial,
        "grandparents PairBond exists but unnamed",
    )
