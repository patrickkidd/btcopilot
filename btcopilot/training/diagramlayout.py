"""
Family Diagram Layout Algorithm

Implements the layout algorithm specified in btcopilot/doc/FAMILY_DIAGRAM_LAYOUT_ALGORITHM.md.
Computes X,Y positions for people and pair bonds in a family diagram.

The algorithm proceeds in phases:
- Phase 0: Data preparation
- Phase 1: Generation assignment
- Phase 2: Initial horizontal positioning
- Phase 3: Compaction
- Phase 4: Canopy adjustment
- Phase 5: Final pair bond calculation

Supports two modes:
1. Full layout (default): Compute positions for all people from scratch
2. Constrained layout: Some people have fixed positions, only compute movable ones

For constrained layout, pass `constraints` dict with:
- "fixed": dict mapping person_id -> {"x": float, "y": float} for fixed positions

Usage:
    # For SVG rendering (training app):
    layout = diagramlayout.compute(render_data)

    # For pro app arrange selection:
    from btcopilot.arrange import Diagram, DiagramDelta
    delta = diagramlayout.arrange(diagram)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from btcopilot.arrange import Diagram, DiagramDelta


PERSON_SIZE = 50
PERSON_SPACING = 120
GENERATION_GAP = 110
PAIR_BOND_DROP = int(PERSON_SIZE / 2.2)
NAME_OFFSET = int(PERSON_SIZE * 0.2)
BASE_X = 100
BASE_Y = 100
CANOPY_PADDING = PERSON_SPACING // 2
COLLISION_THRESHOLD = PERSON_SPACING + PERSON_SIZE // 2


@dataclass
class PersonLayout:
    x: float
    y: float
    person: dict
    labelPosition: str = "right"


@dataclass
class PairBondLayout:
    x1: float
    x2: float
    coupleX1: float
    coupleX2: float
    y: float
    pairBond: dict


@dataclass
class Layout:
    people: dict[int, PersonLayout] = field(default_factory=dict)
    pairBonds: dict[int, PairBondLayout] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "people": {
                pid: {
                    "x": p.x,
                    "y": p.y,
                    "labelPosition": p.labelPosition,
                }
                for pid, p in self.people.items()
            },
            "pairBonds": {
                pbid: {
                    "x1": pb.x1,
                    "x2": pb.x2,
                    "coupleX1": pb.coupleX1,
                    "coupleX2": pb.coupleX2,
                    "y": pb.y,
                }
                for pbid, pb in self.pairBonds.items()
            },
        }


@dataclass
class LayoutContext:
    peopleById: dict[int, dict] = field(default_factory=dict)
    pairBondsByPerson: dict[int, list[dict]] = field(default_factory=dict)
    childrenByPairBond: dict[int, list[int]] = field(default_factory=dict)
    generations: dict[int, int] = field(default_factory=dict)
    layout: Layout = field(default_factory=Layout)
    fixedIds: set[int] = field(default_factory=set)


def compute(data: dict, constraints: dict | None = None) -> dict:
    """
    Compute layout positions for a family diagram.

    Args:
        data: Dict with 'people', 'pair_bonds', 'parent_child' lists
        constraints: Optional dict with:
            - "fixed": dict mapping person_id -> {"x": float, "y": float}
              People in this dict keep their positions; others are computed.

    Returns:
        Dict with 'people' and 'pairBonds' position data suitable for template
    """
    ctx = LayoutContext()

    _phase0_prepare(ctx, data, constraints)
    _phase1_generations(ctx, data)
    _phase2_positioning(ctx, data)
    _phase3_compaction(ctx, data)
    _phase4_canopy(ctx, data)
    _phase5_pairbonds(ctx, data)
    _computeLabelPositions(ctx, data)

    return ctx.layout.as_dict()


def arrangeSelection(diagram: dict) -> dict:
    """
    Compute new positions for selected (movable) people in a diagram.

    This is the entry point for the pro app's /arrange endpoint.
    Converts from the pro app's Person format to the layout algorithm's format.

    Args:
        diagram: Dict with 'people' list where each person has:
            - id: int
            - center: {"x": float, "y": float}
            - isMovable: bool (True = selected, can move; False = fixed)
            - partners: list[int] of partner IDs
            - parent_a: int | None
            - parent_b: int | None

    Returns:
        Dict with 'people' list of {"id": int, "center": {"x": float, "y": float}}
        containing only the movable people with their new positions.
    """
    people = diagram.get("people", [])
    if not people:
        return {"people": []}

    data = _convertFromProAppFormat(people)

    fixed = {}
    for p in people:
        if not p.get("isMovable", False):
            fixed[p["id"]] = {"x": p["center"]["x"], "y": p["center"]["y"]}

    constraints = {"fixed": fixed} if fixed else None

    layout = compute(data, constraints)

    result = []
    for p in people:
        if p.get("isMovable", False):
            pos = layout["people"].get(p["id"])
            if pos:
                result.append({"id": p["id"], "center": {"x": pos["x"], "y": pos["y"]}})

    return {"people": result}


def _convertFromProAppFormat(people: list[dict]) -> dict:
    pairBondsById: dict[int, dict] = {}
    pairBondId = -1

    for p in people:
        for partnerId in p.get("partners", []):
            key = tuple(sorted([p["id"], partnerId]))
            if key not in pairBondsById:
                pairBondsById[key] = {
                    "id": pairBondId,
                    "person_a": key[0],
                    "person_b": key[1],
                    "married": True,
                    "separated": False,
                    "divorced": False,
                }
                pairBondId -= 1

    parentChildById: dict[int, dict] = {}
    for p in people:
        parentA = p.get("parent_a")
        parentB = p.get("parent_b")
        if parentA is not None and parentB is not None:
            parentKey = tuple(sorted([parentA, parentB]))
            if parentKey in pairBondsById:
                pbId = pairBondsById[parentKey]["id"]
                parentChildById[p["id"]] = {"child_id": p["id"], "pair_bond_id": pbId}

    peopleList = []
    for p in people:
        parentA = p.get("parent_a")
        parentB = p.get("parent_b")
        parentsId = None
        if parentA is not None and parentB is not None:
            parentKey = tuple(sorted([parentA, parentB]))
            if parentKey in pairBondsById:
                parentsId = pairBondsById[parentKey]["id"]

        peopleList.append(
            {
                "id": p["id"],
                "name": f"Person {p['id']}",
                "gender": "unknown",
                "parents": parentsId,
            }
        )

    return {
        "people": peopleList,
        "pair_bonds": list(pairBondsById.values()),
        "parent_child": list(parentChildById.values()),
    }


def _phase0_prepare(
    ctx: LayoutContext, data: dict, constraints: dict | None = None
) -> None:
    for p in data.get("people", []):
        ctx.peopleById[p["id"]] = p

    for pb in data.get("pair_bonds", []):
        ctx.pairBondsByPerson.setdefault(pb["person_a"], []).append(pb)
        ctx.pairBondsByPerson.setdefault(pb["person_b"], []).append(pb)

    for pc in data.get("parent_child", []):
        ctx.childrenByPairBond.setdefault(pc["pair_bond_id"], []).append(pc["child_id"])

    if constraints and "fixed" in constraints:
        for pid, pos in constraints["fixed"].items():
            pid = int(pid) if isinstance(pid, str) else pid
            if pid in ctx.peopleById:
                ctx.fixedIds.add(pid)
                person = ctx.peopleById[pid]
                ctx.layout.people[pid] = PersonLayout(
                    x=pos["x"], y=pos["y"], person=person
                )


def _phase1_generations(ctx: LayoutContext, data: dict) -> None:
    """Assign generation numbers to each person.

    When constraints are present, infer generations from fixed Y positions.
    """
    visited: set[int] = set()

    if ctx.fixedIds:
        _inferGenerationsFromFixed(ctx, data)
        return

    def assign(personId: int, gen: int) -> None:
        if personId in visited:
            return
        visited.add(personId)
        ctx.generations[personId] = gen

        for pb in ctx.pairBondsByPerson.get(personId, []):
            spouseId = pb["person_b"] if pb["person_a"] == personId else pb["person_a"]
            if spouseId not in visited:
                visited.add(spouseId)
                ctx.generations[spouseId] = gen

            for childId in ctx.childrenByPairBond.get(pb["id"], []):
                assign(childId, gen + 1)

    parentIds: set[int] = set()
    for pc in data.get("parent_child", []):
        pb = next(
            (b for b in data.get("pair_bonds", []) if b["id"] == pc["pair_bond_id"]),
            None,
        )
        if pb:
            parentIds.add(pb["person_a"])
            parentIds.add(pb["person_b"])

    rootParents = [
        p
        for p in data.get("people", [])
        if p["id"] in parentIds and not p.get("parents")
    ]
    for person in rootParents:
        assign(person["id"], 0)

    for person in data.get("people", []):
        if person["id"] in ctx.generations:
            continue
        if person.get("parents"):
            parentPb = next(
                (
                    pb
                    for pb in data.get("pair_bonds", [])
                    if pb["id"] == person["parents"]
                ),
                None,
            )
            if parentPb:
                parentGen = ctx.generations.get(
                    parentPb["person_a"]
                ) or ctx.generations.get(parentPb["person_b"])
                if parentGen is not None:
                    assign(person["id"], parentGen + 1)

    for person in data.get("people", []):
        if person["id"] not in ctx.generations:
            ctx.generations[person["id"]] = 0


def _inferGenerationsFromFixed(ctx: LayoutContext, data: dict) -> None:
    """Infer generation numbers from fixed Y positions when constraints are present."""
    fixedYs = sorted(set(ctx.layout.people[pid].y for pid in ctx.fixedIds))
    yToGen = {y: i for i, y in enumerate(fixedYs)}

    for pid in ctx.fixedIds:
        pos = ctx.layout.people[pid]
        ctx.generations[pid] = yToGen[pos.y]

    visited = set(ctx.fixedIds)

    def assignFromRelatives(personId: int) -> int | None:
        if personId in ctx.generations:
            return ctx.generations[personId]

        person = ctx.peopleById.get(personId)
        if not person:
            return None

        if person.get("parents"):
            parentPb = next(
                (
                    pb
                    for pb in data.get("pair_bonds", [])
                    if pb["id"] == person["parents"]
                ),
                None,
            )
            if parentPb:
                parentGenA = ctx.generations.get(parentPb["person_a"])
                parentGenB = ctx.generations.get(parentPb["person_b"])
                parentGen = parentGenA if parentGenA is not None else parentGenB
                if parentGen is not None:
                    ctx.generations[personId] = parentGen + 1
                    return parentGen + 1

        for pb in ctx.pairBondsByPerson.get(personId, []):
            spouseId = pb["person_b"] if pb["person_a"] == personId else pb["person_a"]
            if spouseId in ctx.generations:
                ctx.generations[personId] = ctx.generations[spouseId]
                return ctx.generations[spouseId]

        for pb in ctx.pairBondsByPerson.get(personId, []):
            for childId in ctx.childrenByPairBond.get(pb["id"], []):
                if childId in ctx.generations:
                    ctx.generations[personId] = ctx.generations[childId] - 1
                    return ctx.generations[childId] - 1

        return None

    changed = True
    while changed:
        changed = False
        for person in data.get("people", []):
            pid = person["id"]
            if pid not in ctx.generations:
                if assignFromRelatives(pid) is not None:
                    changed = True

    for person in data.get("people", []):
        if person["id"] not in ctx.generations:
            ctx.generations[person["id"]] = 0


def _updatePairBondsForGeneration(ctx: LayoutContext, data: dict, gen: int) -> None:
    """Calculate pair bond positions for couples in the given generation.

    Called after each generation is positioned so that children in the next
    generation can be placed relative to their parents' pair bond positions.
    """
    for pb in data.get("pair_bonds", []):
        personA = ctx.layout.people.get(pb["person_a"])
        personB = ctx.layout.people.get(pb["person_b"])
        if not personA or not personB:
            continue

        genA = ctx.generations.get(pb["person_a"])
        genB = ctx.generations.get(pb["person_b"])
        if genA != gen or genB != gen:
            continue

        y = max(personA.y, personB.y) + PERSON_SIZE / 2 + PAIR_BOND_DROP
        coupleX1 = min(personA.x, personB.x)
        coupleX2 = max(personA.x, personB.x)

        ctx.layout.pairBonds[pb["id"]] = PairBondLayout(
            x1=coupleX1,
            x2=coupleX2,
            coupleX1=coupleX1,
            coupleX2=coupleX2,
            y=y,
            pairBond=pb,
        )


def _phase2_positioning(ctx: LayoutContext, data: dict) -> None:
    """Assign initial X,Y positions to all people."""
    byGeneration: dict[int, list[dict]] = {}
    for person in data.get("people", []):
        gen = ctx.generations.get(person["id"], 0)
        byGeneration.setdefault(gen, []).append(person)

    unconnectedIds = _findUnconnected(ctx, data)
    positioned: set[int] = set(ctx.fixedIds)

    genYMap = _computeGenYMap(ctx, byGeneration)

    for gen in sorted(byGeneration.keys()):
        genY = genYMap.get(gen, BASE_Y + gen * GENERATION_GAP)
        peopleInGen = byGeneration[gen]

        familyUnits = _buildFamilyUnits(ctx, data, gen, peopleInGen, positioned)
        familyUnits = _sortFamilyUnits(ctx, familyUnits)

        currentX = _computeStartX(ctx, gen, positioned)
        for unit in familyUnits:
            currentX = _positionFamilyUnit(ctx, unit, currentX, genY, positioned)
            currentX += PERSON_SPACING // 2

        currentX = _positionRemainingSiblings(
            ctx, data, gen, peopleInGen, currentX, genY, positioned, unconnectedIds
        )
        _positionAdditionalSpouses(
            ctx, data, gen, peopleInGen, genY, positioned, unconnectedIds
        )
        _positionNoParents(ctx, peopleInGen, currentX, genY, positioned, unconnectedIds)

        # Calculate pair bonds for this generation so children can reference them
        _updatePairBondsForGeneration(ctx, data, gen)

    _positionUnconnected(ctx, data, unconnectedIds, positioned)


def _computeGenYMap(
    ctx: LayoutContext, byGeneration: dict[int, list[dict]]
) -> dict[int, float]:
    genYMap: dict[int, float] = {}

    if not ctx.fixedIds:
        for gen in byGeneration:
            genYMap[gen] = BASE_Y + gen * GENERATION_GAP
        return genYMap

    for pid in ctx.fixedIds:
        gen = ctx.generations.get(pid)
        if gen is not None:
            pos = ctx.layout.people[pid]
            if gen not in genYMap:
                genYMap[gen] = pos.y
            else:
                genYMap[gen] = (genYMap[gen] + pos.y) / 2

    allGens = sorted(set(byGeneration.keys()) | set(genYMap.keys()))
    for gen in allGens:
        if gen in genYMap:
            continue
        lowerFixed = max((g for g in genYMap if g < gen), default=None)
        upperFixed = min((g for g in genYMap if g > gen), default=None)

        if lowerFixed is not None and upperFixed is not None:
            lowerY = genYMap[lowerFixed]
            upperY = genYMap[upperFixed]
            ratio = (gen - lowerFixed) / (upperFixed - lowerFixed)
            genYMap[gen] = lowerY + ratio * (upperY - lowerY)
        elif lowerFixed is not None:
            genYMap[gen] = genYMap[lowerFixed] + (gen - lowerFixed) * GENERATION_GAP
        elif upperFixed is not None:
            genYMap[gen] = genYMap[upperFixed] - (upperFixed - gen) * GENERATION_GAP
        else:
            genYMap[gen] = BASE_Y + gen * GENERATION_GAP

    return genYMap


def _computeStartX(ctx: LayoutContext, gen: int, positioned: set[int]) -> float:
    fixedInGen = [
        ctx.layout.people[pid].x
        for pid in ctx.fixedIds
        if ctx.generations.get(pid) == gen
    ]
    if fixedInGen:
        return max(fixedInGen) + PERSON_SPACING
    return BASE_X


def _findUnconnected(ctx: LayoutContext, data: dict) -> set[int]:
    parentIds: set[int] = set()
    for pc in data.get("parent_child", []):
        pb = next(
            (b for b in data.get("pair_bonds", []) if b["id"] == pc["pair_bond_id"]),
            None,
        )
        if pb:
            parentIds.add(pb["person_a"])
            parentIds.add(pb["person_b"])

    unconnected: set[int] = set()
    for p in data.get("people", []):
        pid = p["id"]
        hasParents = p.get("parents") is not None
        hasSpouse = len(ctx.pairBondsByPerson.get(pid, [])) > 0
        isParent = pid in parentIds
        if not hasParents and not hasSpouse and not isParent:
            unconnected.add(pid)
    return unconnected


def _buildFamilyUnits(
    ctx: LayoutContext,
    data: dict,
    gen: int,
    peopleInGen: list[dict],
    positioned: set[int],
) -> list[dict]:
    units: list[dict] = []
    processed: set[int] = set()

    siblingGroups: dict[int, list[dict]] = {}
    for person in peopleInGen:
        if person.get("parents"):
            siblingGroups.setdefault(person["parents"], []).append(person)

    spouseOf: dict[int, int] = {}
    for person in peopleInGen:
        for pb in ctx.pairBondsByPerson.get(person["id"], []):
            partnerId = (
                pb["person_b"] if pb["person_a"] == person["id"] else pb["person_a"]
            )
            if ctx.generations.get(partnerId) == gen:
                spouseOf[person["id"]] = partnerId
                break

    for person in peopleInGen:
        if person["id"] in processed:
            continue
        spouseId = spouseOf.get(person["id"])
        if not spouseId:
            continue
        spouse = ctx.peopleById.get(spouseId)
        if not spouse or spouseId in processed:
            continue

        pb = next(
            (
                b
                for b in ctx.pairBondsByPerson.get(person["id"], [])
                if (b["person_a"] == person["id"] and b["person_b"] == spouseId)
                or (b["person_b"] == person["id"] and b["person_a"] == spouseId)
            ),
            None,
        )
        isDivorced = pb and (pb.get("divorced") or pb.get("separated"))

        personParents = person.get("parents")
        spouseParents = spouse.get("parents")

        personSiblings = [
            s
            for s in siblingGroups.get(personParents, [])
            if s["id"] != person["id"] and s["id"] not in spouseOf
        ]
        spouseSiblings = [
            s
            for s in siblingGroups.get(spouseParents, [])
            if s["id"] != spouseId and s["id"] not in spouseOf
        ]

        personOnLeft = _determineLeftRight(
            ctx, person, spouse, personParents, spouseParents
        )

        if personOnLeft:
            leftSiblings, rightSiblings = personSiblings, spouseSiblings
            person1, person2 = person, spouse
        else:
            leftSiblings, rightSiblings = spouseSiblings, personSiblings
            person1, person2 = spouse, person

        units.append(
            {
                "couple": [person1, person2],
                "leftSiblings": leftSiblings,
                "rightSiblings": rightSiblings,
                "personParents": personParents,
                "spouseParents": spouseParents,
                "isDivorced": isDivorced,
                "pairBondId": pb["id"] if pb else None,
            }
        )

        processed.add(person["id"])
        processed.add(spouseId)

    return units


def _determineLeftRight(
    ctx: LayoutContext,
    person: dict,
    spouse: dict,
    personParents: int | None,
    spouseParents: int | None,
) -> bool:
    personParentX = None
    spouseParentX = None

    if personParents and personParents in ctx.layout.pairBonds:
        pb = ctx.layout.pairBonds[personParents]
        personParentX = (pb.x1 + pb.x2) / 2

    if spouseParents and spouseParents in ctx.layout.pairBonds:
        pb = ctx.layout.pairBonds[spouseParents]
        spouseParentX = (pb.x1 + pb.x2) / 2

    if personParentX is not None and spouseParentX is not None:
        return personParentX <= spouseParentX
    if personParentX is not None:
        return True
    if spouseParentX is not None:
        return False

    personGender = person.get("gender", "unknown")
    spouseGender = spouse.get("gender", "unknown")
    if personGender == "male":
        return True
    if spouseGender == "male":
        return False
    return True


def _sortFamilyUnits(ctx: LayoutContext, units: list[dict]) -> list[dict]:
    def getOrder(unit: dict) -> tuple[int, float]:
        total = 0.0
        count = 0
        for parentPbId in [unit.get("personParents"), unit.get("spouseParents")]:
            if parentPbId and parentPbId in ctx.layout.pairBonds:
                pb = ctx.layout.pairBonds[parentPbId]
                total += (pb.x1 + pb.x2) / 2
                count += 1
        if count > 0:
            return (0, total / count)
        return (1, 0)

    return sorted(units, key=getOrder)


def _positionFamilyUnit(
    ctx: LayoutContext, unit: dict, currentX: float, genY: float, positioned: set[int]
) -> float:
    for sib in unit["leftSiblings"]:
        if sib["id"] not in positioned:
            ctx.layout.people[sib["id"]] = PersonLayout(x=currentX, y=genY, person=sib)
            positioned.add(sib["id"])
            currentX += PERSON_SPACING

    coupleSpacing = PERSON_SPACING * 1.5 if unit["isDivorced"] else PERSON_SPACING
    for p in unit["couple"]:
        if p["id"] not in positioned:
            ctx.layout.people[p["id"]] = PersonLayout(x=currentX, y=genY, person=p)
            positioned.add(p["id"])
            currentX += coupleSpacing

    currentX -= coupleSpacing
    currentX += PERSON_SPACING

    for sib in unit["rightSiblings"]:
        if sib["id"] not in positioned:
            ctx.layout.people[sib["id"]] = PersonLayout(x=currentX, y=genY, person=sib)
            positioned.add(sib["id"])
            currentX += PERSON_SPACING

    return currentX


def _positionRemainingSiblings(
    ctx: LayoutContext,
    data: dict,
    gen: int,
    peopleInGen: list[dict],
    currentX: float,
    genY: float,
    positioned: set[int],
    unconnectedIds: set[int],
) -> float:
    siblingGroups: dict[int, list[dict]] = {}
    for person in peopleInGen:
        if person.get("parents"):
            siblingGroups.setdefault(person["parents"], []).append(person)

    for parentPbId, siblings in siblingGroups.items():
        unpositioned = [
            s
            for s in siblings
            if s["id"] not in positioned and s["id"] not in unconnectedIds
        ]
        if not unpositioned:
            continue

        groupStartX = currentX
        if parentPbId in ctx.layout.pairBonds:
            parentPb = ctx.layout.pairBonds[parentPbId]
            parentCenterX = (parentPb.x1 + parentPb.x2) / 2
            groupWidth = len(unpositioned) * PERSON_SPACING
            groupStartX = max(currentX, parentCenterX - groupWidth / 2)

        x = groupStartX
        for sib in unpositioned:
            ctx.layout.people[sib["id"]] = PersonLayout(x=x, y=genY, person=sib)
            positioned.add(sib["id"])
            x += PERSON_SPACING
        currentX = x + PERSON_SPACING // 2

    return currentX


def _positionAdditionalSpouses(
    ctx: LayoutContext,
    data: dict,
    gen: int,
    peopleInGen: list[dict],
    genY: float,
    positioned: set[int],
    unconnectedIds: set[int],
) -> None:
    """Position people who are additional spouses of already-positioned people.

    Handles multiple marriages: if person A has two spouses B and C, and A-B
    were positioned as a family unit, C needs to be positioned adjacent to A
    on the opposite side from B.
    """
    for person in peopleInGen:
        pid = person["id"]
        if pid in positioned or pid in unconnectedIds:
            continue

        for pb in ctx.pairBondsByPerson.get(pid, []):
            spouseId = pb["person_b"] if pb["person_a"] == pid else pb["person_a"]
            if ctx.generations.get(spouseId) != gen:
                continue
            if spouseId not in positioned:
                continue

            spousePos = ctx.layout.people.get(spouseId)
            if not spousePos:
                continue

            otherSpouseX = None
            for otherPb in ctx.pairBondsByPerson.get(spouseId, []):
                otherSpouseId = (
                    otherPb["person_b"]
                    if otherPb["person_a"] == spouseId
                    else otherPb["person_a"]
                )
                if otherSpouseId == pid:
                    continue
                if otherSpouseId in positioned:
                    otherPos = ctx.layout.people.get(otherSpouseId)
                    if otherPos and abs(otherPos.y - genY) < PERSON_SIZE:
                        otherSpouseX = otherPos.x
                        break

            if otherSpouseX is not None:
                if otherSpouseX > spousePos.x:
                    newX = spousePos.x - PERSON_SPACING
                else:
                    newX = spousePos.x + PERSON_SPACING
            else:
                newX = spousePos.x + PERSON_SPACING

            collision = False
            for otherId, otherPos in ctx.layout.people.items():
                if abs(otherPos.y - genY) < PERSON_SIZE:
                    if abs(otherPos.x - newX) < PERSON_SPACING:
                        collision = True
                        break

            if collision:
                maxX = max(
                    (
                        p.x
                        for p in ctx.layout.people.values()
                        if abs(p.y - genY) < PERSON_SIZE
                    ),
                    default=BASE_X,
                )
                newX = maxX + PERSON_SPACING

            ctx.layout.people[pid] = PersonLayout(x=newX, y=genY, person=person)
            positioned.add(pid)
            break


def _positionNoParents(
    ctx: LayoutContext,
    peopleInGen: list[dict],
    currentX: float,
    genY: float,
    positioned: set[int],
    unconnectedIds: set[int],
) -> None:
    for person in peopleInGen:
        if person["id"] not in positioned and person["id"] not in unconnectedIds:
            ctx.layout.people[person["id"]] = PersonLayout(
                x=currentX, y=genY, person=person
            )
            positioned.add(person["id"])
            currentX += PERSON_SPACING


def _positionUnconnected(
    ctx: LayoutContext, data: dict, unconnectedIds: set[int], positioned: set[int]
) -> None:
    if not unconnectedIds:
        return

    maxX = BASE_X
    minY = float("inf")
    maxY = float("-inf")

    for pid, pos in ctx.layout.people.items():
        if pid not in unconnectedIds:
            maxX = max(maxX, pos.x)
            minY = min(minY, pos.y)
            maxY = max(maxY, pos.y)

    middleY = BASE_Y if minY == float("inf") else (minY + maxY) / 2
    unconnectedX = BASE_X if minY == float("inf") else maxX + PERSON_SPACING * 1.5

    for pid in unconnectedIds:
        person = ctx.peopleById.get(pid)
        if person and pid not in positioned:
            ctx.layout.people[pid] = PersonLayout(
                x=unconnectedX, y=middleY, person=person
            )
            positioned.add(pid)
            unconnectedX += PERSON_SPACING


def _phase3_compaction(ctx: LayoutContext, data: dict) -> None:
    if ctx.fixedIds:
        return

    unconnectedIds = _findUnconnected(ctx, data)

    byGen: dict[int, list[tuple[int, PersonLayout]]] = {}
    for pid, pos in ctx.layout.people.items():
        if pid in unconnectedIds:
            continue
        gen = ctx.generations.get(pid, 0)
        byGen.setdefault(gen, []).append((pid, pos))

    for gen in sorted(byGen.keys()):
        people = sorted(byGen[gen], key=lambda x: x[1].x)
        if not people:
            continue

        # Compute minimum start X based on parents' positions
        # Children shouldn't be shifted left of their parents' span
        minStartX = BASE_X
        for pid, pos in people:
            person = ctx.peopleById.get(pid)
            if person and person.get("parents"):
                parentPbId = person["parents"]
                parentPb = ctx.layout.pairBonds.get(parentPbId)
                if parentPb:
                    # Children should start no earlier than left edge of parent span
                    parentLeftX = min(parentPb.x1, parentPb.x2)
                    minStartX = max(minStartX, parentLeftX)

        currentMinX = min(p[1].x for p in people)
        shift = currentMinX - minStartX
        if shift > 0:
            for pid, pos in people:
                if pid not in ctx.fixedIds:
                    pos.x -= shift

        for i in range(1, len(people)):
            prevPid, prevPos = people[i - 1]
            currPid, currPos = people[i]
            gap = currPos.x - prevPos.x

            minGap = PERSON_SPACING
            pb = next(
                (
                    b
                    for b in data.get("pair_bonds", [])
                    if (b["person_a"] == prevPid and b["person_b"] == currPid)
                    or (b["person_b"] == prevPid and b["person_a"] == currPid)
                ),
                None,
            )
            if pb and (pb.get("divorced") or pb.get("separated")):
                minGap = int(PERSON_SPACING * 1.5)

            if gap > minGap:
                reduction = gap - minGap
                for j in range(i, len(people)):
                    pid_j = people[j][0]
                    if pid_j not in ctx.fixedIds:
                        people[j][1].x -= reduction


def _phase4_canopy(ctx: LayoutContext, data: dict) -> None:
    """Shift couples to better center over their unmarried children.

    Unlike expanding parents apart (which violates INV-2 couple adjacency),
    this shifts the ENTIRE couple as a unit to center over children.
    """
    if ctx.fixedIds:
        return

    for pb in data.get("pair_bonds", []):
        personA = ctx.layout.people.get(pb["person_a"])
        personB = ctx.layout.people.get(pb["person_b"])
        if not personA or not personB:
            continue

        children = ctx.childrenByPairBond.get(pb["id"], [])
        if not children:
            continue

        # Only consider unmarried children for canopy
        childMinX = float("inf")
        childMaxX = float("-inf")
        for childId in children:
            childPbs = ctx.pairBondsByPerson.get(childId, [])
            if childPbs:
                continue
            childPos = ctx.layout.people.get(childId)
            if childPos:
                childMinX = min(childMinX, childPos.x)
                childMaxX = max(childMaxX, childPos.x)

        if childMinX == float("inf"):
            continue

        leftParent = personA if personA.x < personB.x else personB
        rightParent = personB if personA.x < personB.x else personA
        coupleSpacing = rightParent.x - leftParent.x

        # Children already within parents' span - no adjustment needed
        if childMinX >= leftParent.x and childMaxX <= rightParent.x:
            continue

        # Compute desired couple center to cover children
        childCenter = (childMinX + childMaxX) / 2
        coupleCenter = (leftParent.x + rightParent.x) / 2

        # Shift couple to center over children
        shift = childCenter - coupleCenter

        # Check for collisions with neighbors in same generation
        leftParentGen = ctx.generations.get(
            leftParent.person.get("id") if leftParent.person else None
        )
        if leftParentGen is not None and shift != 0:
            newLeftX = leftParent.x + shift
            newRightX = rightParent.x + shift

            for otherId, otherPos in ctx.layout.people.items():
                leftPid = leftParent.person.get("id") if leftParent.person else None
                rightPid = rightParent.person.get("id") if rightParent.person else None
                if otherId in (leftPid, rightPid):
                    continue
                if ctx.generations.get(otherId) != leftParentGen:
                    continue

                # Check collision with left shift
                if shift < 0 and otherPos.x < leftParent.x:
                    minAllowed = otherPos.x + PERSON_SPACING
                    if newLeftX < minAllowed:
                        shift = minAllowed - leftParent.x

                # Check collision with right shift
                if shift > 0 and otherPos.x > rightParent.x:
                    maxAllowed = otherPos.x - PERSON_SPACING
                    if newRightX > maxAllowed:
                        shift = maxAllowed - rightParent.x

        # Apply shift to both parents, maintaining couple spacing
        if shift != 0:
            leftParent.x += shift
            rightParent.x += shift


def _phase5_pairbonds(ctx: LayoutContext, data: dict) -> None:
    for pb in data.get("pair_bonds", []):
        personA = ctx.layout.people.get(pb["person_a"])
        personB = ctx.layout.people.get(pb["person_b"])
        if not personA or not personB:
            continue

        y = max(personA.y, personB.y) + PERSON_SIZE / 2 + PAIR_BOND_DROP
        coupleX1 = min(personA.x, personB.x)
        coupleX2 = max(personA.x, personB.x)

        ctx.layout.pairBonds[pb["id"]] = PairBondLayout(
            x1=coupleX1,
            x2=coupleX2,
            coupleX1=coupleX1,
            coupleX2=coupleX2,
            y=y,
            pairBond=pb,
        )


def _computeLabelPositions(ctx: LayoutContext, data: dict) -> None:
    halfSize = PERSON_SIZE / 2
    tightThreshold = PERSON_SPACING * 1.25

    for personId, pos in ctx.layout.people.items():
        person = pos.person or ctx.peopleById.get(personId)
        if not person:
            continue

        labelText = person.get("name") or f"Person {personId}"
        estimatedLabelWidth = len(labelText) * 7
        labelWouldOverlapSelf = estimatedLabelWidth > (halfSize + NAME_OFFSET)

        rightNeighborDist = float("inf")
        leftNeighborDist = float("inf")

        for otherId, otherPos in ctx.layout.people.items():
            if otherId == personId:
                continue
            if abs(otherPos.y - pos.y) < PERSON_SIZE:
                dist = otherPos.x - pos.x
                if dist > 0:
                    rightNeighborDist = min(rightNeighborDist, dist)
                elif dist < 0:
                    leftNeighborDist = min(leftNeighborDist, -dist)

        hasParents = person.get("parents") is not None

        labelRightEdge = halfSize + NAME_OFFSET + estimatedLabelWidth
        rightLabelWouldCollide = rightNeighborDist < (labelRightEdge + halfSize + 10)

        labelPosition = "right"
        if (
            hasParents
            and rightNeighborDist < tightThreshold
            and leftNeighborDist < tightThreshold
        ):
            labelPosition = "above-right"
        elif rightLabelWouldCollide:
            if labelWouldOverlapSelf:
                labelPosition = "above-right" if hasParents else "right"
            elif leftNeighborDist < COLLISION_THRESHOLD:
                labelPosition = "above-right" if hasParents else "right"
            else:
                labelPosition = "left"

        pos.labelPosition = labelPosition


def arrange(diagram: Diagram) -> DiagramDelta:
    """
    Arrange selected people in a diagram while respecting fixed positions.

    This is the entry point for the pro app's arrange feature. It converts
    the pro app's Diagram format to the internal format, runs the layout
    algorithm with constraints, and returns only the delta for movable people.

    Args:
        diagram: btcopilot.arrange.Diagram with people (some isMovable=True)

    Returns:
        btcopilot.arrange.DiagramDelta with new positions for movable people
    """
    from btcopilot.arrange import DiagramDelta, PersonDelta, Point

    pairBondIdCounter = -1

    def nextPairBondId() -> int:
        nonlocal pairBondIdCounter
        pairBondIdCounter -= 1
        return pairBondIdCounter

    peopleList = []
    pairBondsList = []
    parentChildList = []
    seenPartnerPairs: set[tuple[int, int]] = set()

    for person in diagram.people:
        parentPbId = None
        if person.parent_a is not None and person.parent_b is not None:
            parentKey = tuple(sorted([person.parent_a, person.parent_b]))
            if parentKey not in seenPartnerPairs:
                parentPbId = nextPairBondId()
                pairBondsList.append(
                    {
                        "id": parentPbId,
                        "person_a": person.parent_a,
                        "person_b": person.parent_b,
                        "married": True,
                        "separated": False,
                        "divorced": False,
                    }
                )
                seenPartnerPairs.add(parentKey)
            else:
                for pb in pairBondsList:
                    if tuple(sorted([pb["person_a"], pb["person_b"]])) == parentKey:
                        parentPbId = pb["id"]
                        break

            if parentPbId is not None:
                parentChildList.append(
                    {
                        "child_id": person.id,
                        "pair_bond_id": parentPbId,
                    }
                )

        peopleList.append(
            {
                "id": person.id,
                "name": f"Person {person.id}",
                "gender": "unknown",
                "parents": parentPbId,
            }
        )

    for person in diagram.people:
        for partnerId in person.partners:
            key = tuple(sorted([person.id, partnerId]))
            if key not in seenPartnerPairs:
                pairBondsList.append(
                    {
                        "id": nextPairBondId(),
                        "person_a": person.id,
                        "person_b": partnerId,
                        "married": True,
                        "separated": False,
                        "divorced": False,
                    }
                )
                seenPartnerPairs.add(key)

    data = {
        "people": peopleList,
        "pair_bonds": pairBondsList,
        "parent_child": parentChildList,
    }

    fixed = {}
    for person in diagram.people:
        if not person.isMovable:
            fixed[person.id] = {"x": person.center.x, "y": person.center.y}

    constraints = {"fixed": fixed} if fixed else None

    layout = compute(data, constraints)

    deltaPersons = []
    for person in diagram.people:
        if person.isMovable and person.id in layout["people"]:
            pos = layout["people"][person.id]
            deltaPersons.append(
                PersonDelta(
                    id=person.id,
                    center=Point(x=pos["x"], y=pos["y"]),
                )
            )

    return DiagramDelta(people=deltaPersons)
