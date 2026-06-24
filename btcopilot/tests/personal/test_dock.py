"""
Unit tests for the gate-and-dock floating-component repair (FD-338).
The single dock LLM call is patched; everything else is deterministic.

Committed: User (1) -- Alice (10) bond 101, Alice -- Bob bond 100,
           Carol (12) child of Alice/Bob (parents=100).
Main tree = {1, 10, 11, 12}; each test stages its own floating delta people.
"""

import copy

from btcopilot.schema import DiagramData, PDP, PairBond, Person

COMMITTED_PEOPLE = [
    {"id": 1, "name": "User", "gender": None, "parents": None, "primary": True},
    {"id": 10, "name": "Alice", "gender": "female", "parents": None},
    {"id": 11, "name": "Bob", "gender": "male", "parents": None},
    {"id": 12, "name": "Carol", "gender": "female", "parents": 100},
]
COMMITTED_BONDS = [
    {"id": 100, "person_a": 10, "person_b": 11},
    {"id": 101, "person_a": 1, "person_b": 10},
]

TRANSCRIPT = """\
[disc 7] User: Dave is married to Alice.
[disc 7] Assistant: Tell me more.
[disc 7] User: Kim is the child of Alice and Bob.
[disc 7] User: Mona is Bob's mother.
[disc 7] User: Sara is Carol's sister.
[disc 7] User: Kyle is Carol's son.
[disc 7] User: Evan is Alice's ex-boyfriend."""


def _committed() -> DiagramData:
    dd = DiagramData()
    dd.people = copy.deepcopy(COMMITTED_PEOPLE)
    dd.pair_bonds = copy.deepcopy(COMMITTED_BONDS)
    dd.lastItemId = 101
    return dd


def _gemini(result, calls=None):
    async def gemini_structured(prompt, response_format, **kwargs):
        if calls is not None:
            calls.append(prompt)
        return result

    return gemini_structured


def _attach(*edges):
    from btcopilot.personal.dock import DockGroup, DockResult, Verdict

    return DockResult(
        groups=[
            DockGroup(
                member_ids=sorted({e.member_id for e in edges}),
                verdict=Verdict.Attach,
                edges=list(edges),
            )
        ]
    )


def test_dock_skips_when_fully_connected(monkeypatch):
    from btcopilot.personal import dock as dock_mod

    calls = []
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(None, calls))
    delta = PDP(
        people=[Person(id=-1, name="Dave")],
        pair_bonds=[PairBond(id=-2, person_a=-1, person_b=10)],
    )
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)
    assert out is delta
    assert calls == []


def test_dock_partner_of_creates_bond(monkeypatch):
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    edge = DockEdge(
        member_id=-1,
        relation=Relation.PartnerOf,
        anchor_id=10,
        # whitespace/case variant of the transcript sentence — must still pass
        quote="dave is  MARRIED to Alice.",
        reasoning="stated",
    )
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(edge)))
    delta = PDP(people=[Person(id=-1, name="Dave")])
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)

    bonds = [pb for pb in out.pair_bonds if {pb.person_a, pb.person_b} == {-1, 10}]
    assert len(bonds) == 1
    assert bonds[0].id < 0
    assert bonds[0].married is None


def test_dock_ex_partner_stages_unmarried_bond(monkeypatch):
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    edge = DockEdge(
        member_id=-1,
        relation=Relation.PartnerOf,
        anchor_id=10,
        quote="Evan is Alice's ex-boyfriend.",
        reasoning="stated ex-partner",
        married=False,
    )
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(edge)))
    delta = PDP(people=[Person(id=-1, name="Evan")])
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)

    bonds = [pb for pb in out.pair_bonds if {pb.person_a, pb.person_b} == {-1, 10}]
    assert len(bonds) == 1
    assert bonds[0].married is False


def test_dock_child_of_two_anchors_reuses_committed_bond(monkeypatch):
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    quote = "Kim is the child of Alice and Bob."
    edges = [
        DockEdge(
            member_id=-1,
            relation=Relation.ChildOf,
            anchor_id=10,
            quote=quote,
            reasoning="stated",
        ),
        DockEdge(
            member_id=-1,
            relation=Relation.ChildOf,
            anchor_id=11,
            quote=quote,
            reasoning="stated",
        ),
    ]
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(*edges)))
    delta = PDP(people=[Person(id=-1, name="Kim")])
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)

    kim = next(p for p in out.people if p.id == -1)
    assert kim.parents == 100
    assert out.pair_bonds == []
    assert len(out.people) == 1


def test_dock_child_of_single_anchor_creates_placeholder_coparent(monkeypatch):
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    edge = DockEdge(
        member_id=-1,
        relation=Relation.ChildOf,
        anchor_id=12,
        quote="Kyle is Carol's son.",
        reasoning="stated",
    )
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(edge)))
    delta = PDP(people=[Person(id=-1, name="Kyle")])
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)

    spouse = next(p for p in out.people if p.name == "Carol's spouse")
    assert spouse.id < 0
    bond = next(
        pb for pb in out.pair_bonds if {pb.person_a, pb.person_b} == {12, spouse.id}
    )
    assert bond.id < 0
    kyle = next(p for p in out.people if p.id == -1)
    assert kyle.parents == bond.id


def test_dock_parent_of_emits_committed_parent_edit(monkeypatch):
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    edge = DockEdge(
        member_id=-1,
        relation=Relation.ParentOf,
        anchor_id=11,
        quote="Mona is Bob's mother.",
        reasoning="stated",
    )
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(edge)))
    delta = PDP(people=[Person(id=-1, name="Mona")])
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)

    spouse = next(p for p in out.people if p.name == "Mona's spouse")
    bond = next(
        pb for pb in out.pair_bonds if {pb.person_a, pb.person_b} == {-1, spouse.id}
    )
    edit = next(p for p in out.people if p.id == 11)
    assert edit.parents == bond.id


def test_dock_sibling_of_copies_anchor_parents(monkeypatch):
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    edge = DockEdge(
        member_id=-1,
        relation=Relation.SiblingOf,
        anchor_id=12,
        quote="Sara is Carol's sister.",
        reasoning="stated",
    )
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(edge)))
    delta = PDP(people=[Person(id=-1, name="Sara")])
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)

    sara = next(p for p in out.people if p.id == -1)
    assert sara.parents == 100
    assert out.pair_bonds == []


def test_dock_sibling_of_creates_placeholder_parents(monkeypatch):
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    edge = DockEdge(
        member_id=-1,
        relation=Relation.SiblingOf,
        anchor_id=11,
        quote="Mona is Bob's mother.",
        reasoning="sibling of Bob",
    )
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(edge)))
    delta = PDP(people=[Person(id=-1, name="Sara")])
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)

    mother = next(p for p in out.people if p.name == "Bob's mother")
    father = next(p for p in out.people if p.name == "Bob's father")
    bond = next(
        pb
        for pb in out.pair_bonds
        if {pb.person_a, pb.person_b} == {mother.id, father.id}
    )
    edit = next(p for p in out.people if p.id == 11)
    assert edit.parents == bond.id
    sara = next(p for p in out.people if p.id == -1)
    assert sara.parents == bond.id


def test_dock_sibling_anchor_edit_survives_birth_event_backfill(monkeypatch):
    """GT diagram-1924 item 3: a wrong committed birth event (anchor as child of
    a committed couple) must not beat the dock's explicit placeholder-parents
    edit — after commit BOTH the anchor and the member carry the new bond."""
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    edge = DockEdge(
        member_id=-1,
        relation=Relation.SiblingOf,
        anchor_id=11,
        quote="Mona is Bob's mother.",
        reasoning="sibling of Bob",
    )
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(edge)))
    committed = _committed()
    committed.events = [
        {"id": 200, "kind": "birth", "person": 1, "spouse": 10, "child": 11}
    ]
    delta = PDP(people=[Person(id=-1, name="Sara")])
    out = dock_mod.dock(committed, delta, TRANSCRIPT)
    mother = next(p for p in out.people if p.name == "Bob's mother")
    father = next(p for p in out.people if p.name == "Bob's father")
    bond_neg = next(
        pb.id
        for pb in out.pair_bonds
        if {pb.person_a, pb.person_b} == {mother.id, father.id}
    )

    committed.pdp = out
    neg_ids = [p.id for p in out.people if p.id is not None and p.id < 0]
    neg_ids += [pb.id for pb in out.pair_bonds if pb.id is not None and pb.id < 0]
    mapping = committed.commit_pdp_items(neg_ids)
    committed.apply_parent_edits()

    bond_id = mapping[bond_neg]
    bob = next(p for p in committed.people if p["id"] == 11)
    assert bob["parents"] == bond_id
    sara = next(p for p in committed.people if p["id"] == mapping[-1])
    assert sara["parents"] == bond_id


def test_dock_rejects_bad_quote_and_ids(monkeypatch):
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    edges = [
        # not verbatim
        DockEdge(
            member_id=-1,
            relation=Relation.PartnerOf,
            anchor_id=10,
            quote="Dave divorced Alice.",
            reasoning="",
        ),
        # member not floating
        DockEdge(
            member_id=12,
            relation=Relation.PartnerOf,
            anchor_id=10,
            quote="Dave is married to Alice.",
            reasoning="",
        ),
        # anchor not in the main tree
        DockEdge(
            member_id=-1,
            relation=Relation.PartnerOf,
            anchor_id=-1,
            quote="Dave is married to Alice.",
            reasoning="",
        ),
    ]
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(*edges)))
    delta = PDP(people=[Person(id=-1, name="Dave")])
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)
    assert out is delta
    assert out.pair_bonds == []


def test_dock_noop_when_floating_count_does_not_drop(monkeypatch):
    from btcopilot.personal import dock as dock_mod
    from btcopilot.personal.dock import DockEdge, Relation

    # Kim already has parents inside her floating component, so the only
    # proposed edge is skipped at apply time and the count cannot drop.
    edge = DockEdge(
        member_id=-1,
        relation=Relation.ChildOf,
        anchor_id=12,
        quote="Kim is the child of Alice and Bob.",
        reasoning="stated",
    )
    monkeypatch.setattr(dock_mod, "gemini_structured", _gemini(_attach(edge)))
    delta = PDP(
        people=[
            Person(id=-1, name="Kim", parents=-2),
            Person(id=-3, name="Mom"),
            Person(id=-4, name="Dad"),
        ],
        pair_bonds=[PairBond(id=-2, person_a=-3, person_b=-4)],
    )
    out = dock_mod.dock(_committed(), delta, TRANSCRIPT)
    assert out is delta
    assert all(p.name != "Carol's spouse" for p in out.people)
