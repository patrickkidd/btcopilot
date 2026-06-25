"""
Gate-and-dock: directed repair of floating components after merge_runs.

GATE (free, deterministic): connected components over the union of committed
and delta people/pair_bonds. One component -> no LLM call. DOCK (one call):
present the full transcript, the main-tree roster and the floating groups;
the model proposes edges-only connections, each with a verbatim transcript
quote. Deterministic gates reject non-verbatim quotes and ids outside the
floating/main sets; accepted edges are applied programmatically (the LLM
never assigns ids). The docked delta is kept only if the floating-component
count strictly drops — worst case is the pre-dock delta, by construction.
"""

import asyncio
import copy
import enum
import logging
import re
from dataclasses import dataclass

from btcopilot.familygraph import bond_endpoints, components, default_ids, person_id
from btcopilot.llmutil import SARF_REVIEW_MODEL, gemini_structured
from btcopilot.personal.prompts import DOCK_PROMPT
from btcopilot.schema import (
    DiagramData,
    PDP,
    PairBond,
    Person,
    get_all_pdp_item_ids,
    next_neg,
)

_log = logging.getLogger(__name__)


class Relation(enum.StrEnum):
    PartnerOf = "partner_of"
    ChildOf = "child_of"
    ParentOf = "parent_of"
    SiblingOf = "sibling_of"


class Verdict(enum.StrEnum):
    Attach = "attach"
    NoneFound = "none"


@dataclass
class DockEdge:
    member_id: int
    relation: Relation
    anchor_id: int
    quote: str
    reasoning: str
    # partner_of only: False = romantic but never married (dashed bond)
    married: bool | None = None


@dataclass
class DockGroup:
    member_ids: list[int]
    verdict: Verdict
    edges: list[DockEdge]


@dataclass
class DockResult:
    groups: list[DockGroup]


def transcript_text(discussions) -> str:
    lines = []
    for disc in discussions:
        for st in sorted(disc.statements, key=lambda s: s.order or 0):
            speaker = st.speaker.name if st.speaker else f"speaker-{st.speaker_id}"
            lines.append(f"[disc {disc.id}] {speaker}: {st.text}")
    return "\n".join(lines)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _person_name(p) -> str | None:
    return p.get("name") if isinstance(p, dict) else p.name


def _names(people: list) -> dict[int, str]:
    names: dict[int, str] = {}
    for p in people:
        pid = person_id(p)
        name = _person_name(p)
        if pid is not None and name is not None and pid not in names:
            names[pid] = name
    return names


def _floats(people: list, pair_bonds: list) -> tuple[set[int], list[set[int]]]:
    """(main-tree ids, floating components with at least one non-default member)."""
    comps = components(people, pair_bonds)
    default = default_ids(people)
    main = comps[0] if comps else set()
    return main, [c for c in comps[1:] if c - default]


def _lines(ids, names: dict[int, str], partners: dict[int, list[int]]) -> str:
    out = []
    for pid in sorted(ids):
        s = f"  id={pid} {names.get(pid, '?')}"
        ps = [names.get(o, "?") for o in partners.get(pid, [])]
        if ps:
            s += f" (partner of: {', '.join(ps)})"
        out.append(s)
    return "\n".join(out)


def _prompt(
    people: list,
    pair_bonds: list,
    main: set[int],
    floats: list[set[int]],
    transcript: str,
) -> str:
    names = _names(people)
    partners: dict[int, list[int]] = {}
    for pb in pair_bonds:
        a, b = bond_endpoints(pb)
        if a is not None and b is not None:
            partners.setdefault(a, []).append(b)
            partners.setdefault(b, []).append(a)
    floats_text = "\n\n".join(
        f"FLOATING GROUP (ids {sorted(c)}):\n{_lines(c, names, partners)}"
        for c in floats
    )
    return DOCK_PROMPT.format(
        roster=_lines(main, names, partners),
        floats=floats_text,
        transcript=transcript,
    )


def _gated(
    result: DockResult, transcript: str, main: set[int], floats: list[set[int]]
) -> list[DockEdge]:
    tnorm = _norm(transcript)
    floating = set().union(*floats) if floats else set()
    group_of = {pid: i for i, c in enumerate(floats) for pid in c}
    edges = []
    for group in result.groups:
        for edge in group.edges:
            if _norm(edge.quote) not in tnorm:
                reason = "quote not verbatim"
            elif edge.member_id not in floating:
                reason = "member not floating"
            elif edge.anchor_id not in main and (
                edge.anchor_id not in floating
                or group_of[edge.anchor_id] == group_of[edge.member_id]
            ):
                reason = "anchor not in main tree or member's own group"
            else:
                edges.append(edge)
                continue
            _log.warning(
                f"dock: rejected edge {edge.member_id} {edge.relation.value} "
                f"{edge.anchor_id}: {reason}"
            )
    return edges


class _Applier:
    """Applies gated edges onto the delta in committed+delta mixed id space.

    New people/bonds get fresh negative ids; parents on committed people
    become positive-id Person edit rows — the exact channel merge_runs uses,
    consumed by DiagramData.apply_parent_edits after commit.
    """

    def __init__(self, committed: DiagramData, delta: PDP):
        self.committed = committed
        self.delta = delta
        self.names = _names(committed.people + delta.people)
        self.ids = (
            get_all_pdp_item_ids(delta)
            | {p["id"] for p in committed.people}
            | {pb["id"] for pb in committed.pair_bonds}
        )

    def apply(self, edges: list[DockEdge]) -> None:
        child_anchors: dict[int, list[int]] = {}  # member -> its stated parents
        child_members: dict[int, list[int]] = {}  # anchor child -> stated parents
        siblings: list[DockEdge] = []
        for e in edges:
            if e.relation is Relation.PartnerOf:
                if self._bond_for(e.member_id, e.anchor_id) is None:
                    self._new_bond(e.member_id, e.anchor_id, married=e.married)
            elif e.relation is Relation.ChildOf:
                child_anchors.setdefault(e.member_id, []).append(e.anchor_id)
            elif e.relation is Relation.ParentOf:
                child_members.setdefault(e.anchor_id, []).append(e.member_id)
            elif e.relation is Relation.SiblingOf:
                siblings.append(e)
        for member, anchors in child_anchors.items():
            self._set_parents(member, self._couple_bond(anchors))
        for child, members in child_members.items():
            self._set_parents(child, self._couple_bond(members))
        for e in siblings:
            bond = self._parents_of(e.anchor_id)
            if bond is None:
                bond = self._placeholder_parents(e.anchor_id)
            self._set_parents(e.member_id, bond)

    def _parents_of(self, pid: int) -> int | None:
        for p in self.delta.people:
            if p.id == pid and p.parents is not None:
                return p.parents
        for p in self.committed.people:
            if p["id"] == pid and p.get("parents") is not None:
                return p["parents"]
        return None

    def _set_parents(self, pid: int, bond: int) -> None:
        existing = self._parents_of(pid)
        if existing is not None:
            if existing != bond:
                _log.warning(
                    f"dock: skipped parents={bond} on person {pid}: "
                    f"already parents={existing}"
                )
            return
        row = next((p for p in self.delta.people if p.id == pid), None)
        if row is None:
            # committed person — stage a positive-id parents edit
            self.delta.people.append(Person(id=pid, parents=bond))
        else:
            row.parents = bond

    def _bond_for(self, a: int, b: int) -> int | None:
        dyad = {a, b}
        for pb in self.delta.pair_bonds:
            if {pb.person_a, pb.person_b} == dyad:
                return pb.id
        for pb in self.committed.pair_bonds:
            if {pb["person_a"], pb["person_b"]} == dyad:
                return pb["id"]
        return None

    def _bonds_with(self, pid: int) -> list[int]:
        out = [
            pb.id for pb in self.delta.pair_bonds if pid in (pb.person_a, pb.person_b)
        ]
        out += [
            pb["id"]
            for pb in self.committed.pair_bonds
            if pid in (pb["person_a"], pb["person_b"])
        ]
        return out

    def _couple_bond(self, parents: list[int]) -> int:
        """Bond uniting `parents`: their shared bond, the sole parent's first
        bond, or a new bond with a placeholder co-parent (mirrors the
        commit-path inferred-parents primitives)."""
        uniq = list(dict.fromkeys(parents))
        if len(uniq) >= 2:
            bond = self._bond_for(uniq[0], uniq[1])
            return bond if bond is not None else self._new_bond(uniq[0], uniq[1])
        bonds = self._bonds_with(uniq[0])
        if bonds:
            return bonds[0]
        spouse = self._new_person(f"{self.names.get(uniq[0], '?')}'s spouse")
        return self._new_bond(uniq[0], spouse)

    def _placeholder_parents(self, pid: int) -> int:
        name = self.names.get(pid, "?")
        mother = self._new_person(f"{name}'s mother")
        father = self._new_person(f"{name}'s father")
        bond = self._new_bond(mother, father)
        self._set_parents(pid, bond)
        return bond

    def _new_person(self, name: str) -> int:
        pid = next_neg(self.ids)
        self.ids.add(pid)
        self.delta.people.append(Person(id=pid, name=name))
        self.names[pid] = name
        return pid

    def _new_bond(self, a: int, b: int, married: bool | None = None) -> int:
        bid = next_neg(self.ids)
        self.ids.add(bid)
        self.delta.pair_bonds.append(
            PairBond(id=bid, person_a=a, person_b=b, married=married)
        )
        return bid


def dock(committed: DiagramData, delta: PDP, transcript: str) -> PDP:
    """Return delta with floating components docked to the main tree, or the
    unchanged delta when fully connected, no edge survives the gates, or the
    floating-component count does not strictly drop."""
    people = committed.people + delta.people
    bonds = committed.pair_bonds + delta.pair_bonds
    main, floats = _floats(people, bonds)
    if not floats:
        _log.info("dock: fully connected, skipping")
        return delta

    prompt = _prompt(people, bonds, main, floats, transcript)
    result = asyncio.run(gemini_structured(prompt, DockResult, model=SARF_REVIEW_MODEL))

    edges = _gated(result, transcript, main, floats)
    if not edges:
        _log.info(f"dock: no edges accepted, keeping {len(floats)} floating")
        return delta

    docked = copy.deepcopy(delta)
    _Applier(committed, docked).apply(edges)
    _, after = _floats(
        committed.people + docked.people, committed.pair_bonds + docked.pair_bonds
    )
    if len(after) < len(floats):
        _log.info(f"dock: floating components {len(floats)} -> {len(after)}, accepted")
        return docked
    _log.warning(f"dock: floating components {len(floats)} -> {len(after)}, rejected")
    return delta
