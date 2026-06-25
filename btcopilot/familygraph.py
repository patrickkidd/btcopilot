"""
Family-graph connectivity over people + pair_bonds lists, accepting committed
dicts or schema dataclasses interchangeably.

Edges: pair_bonds (person_a--person_b) plus parent-child links resolved
through pair_bonds (a child connects to both members of its parents bond).
The User (primary or id=1) stays in the graph as a connecting node but is
excluded from size counts; the Assistant (id=2) is dropped entirely.
"""


def person_id(p) -> int | None:
    return p.get("id") if isinstance(p, dict) else p.id


def bond_id(pb) -> int | None:
    return pb.get("id") if isinstance(pb, dict) else pb.id


def bond_endpoints(pb) -> tuple[int | None, int | None]:
    if isinstance(pb, dict):
        return pb.get("person_a"), pb.get("person_b")
    return pb.person_a, pb.person_b


def person_parents(p) -> int | None:
    return p.get("parents") if isinstance(p, dict) else p.parents


def person_primary(p) -> bool:
    if isinstance(p, dict):
        return bool(p.get("primary"))
    return bool(getattr(p, "primary", False))


def default_ids(people: list) -> set[int]:
    """IDs of User (primary or id=1) and Assistant (id=2) people."""
    ids: set[int] = set()
    for p in people:
        pid = person_id(p)
        if pid is not None and (person_primary(p) or pid in (1, 2)):
            ids.add(pid)
    return ids


def speaker_ids(people: list) -> tuple[int | None, int | None]:
    """(user_id, assistant_id): user is the primary-flagged person, else id=1;
    assistant is id=2. None when absent."""
    user = next((person_id(p) for p in people if person_primary(p)), None)
    if user is None and any(person_id(p) == 1 for p in people):
        user = 1
    assistant = 2 if any(person_id(p) == 2 for p in people) else None
    return user, assistant


def components(people: list, pair_bonds: list) -> list[set[int]]:
    """
    Connected components of the family graph, sorted by non-default member
    count descending — the main tree first, floating components after.
    """
    default = default_ids(people)
    nodes = {person_id(p) for p in people} - {None, 2}
    adj: dict[int, set[int]] = {n: set() for n in nodes}

    bond_by_id: dict[int, tuple[int | None, int | None]] = {}
    for pb in pair_bonds:
        a, b = bond_endpoints(pb)
        pb_id = bond_id(pb)
        if pb_id is not None:
            bond_by_id[pb_id] = (a, b)
        if a in nodes and b in nodes:
            adj[a].add(b)
            adj[b].add(a)

    for p in people:
        pid = person_id(p)
        if pid not in nodes:
            continue
        bond = bond_by_id.get(person_parents(p))
        if bond is None:
            continue
        for parent in bond:
            if parent in nodes:
                adj[pid].add(parent)
                adj[parent].add(pid)

    visited: set[int] = set()
    comps: list[set[int]] = []
    for start in nodes:
        if start in visited:
            continue
        queue, comp = [start], {start}
        visited.add(start)
        while queue:
            cur = queue.pop()
            for nb in adj[cur]:
                if nb not in visited:
                    visited.add(nb)
                    comp.add(nb)
                    queue.append(nb)
        comps.append(comp)

    comps.sort(key=lambda c: len(c - default), reverse=True)
    return comps


def lcc_percent(people: list, pair_bonds: list) -> dict:
    """
    LCC% of the family tree, EXCLUDING the User and Assistant from the count but
    keeping the User as a CONNECTING node. In a Personal-app diagram the User is
    the proband: spouse, children, parents and siblings all connect through them,
    so deleting the User node fragments correctly-extracted families. The Assistant
    (id=2) is the AI and is dropped from the graph entirely.

    Returns:
        total: int — non-default people count (excludes User + Assistant)
        components: int — number of connected components (User-as-connector graph)
        lcc: int — non-default members of the largest component
        lcc_pct: float — lcc / total * 100 (0.0 if total == 0)
    """
    default = default_ids(people)
    total = sum(
        1 for p in people if person_id(p) is not None and person_id(p) not in default
    )
    comps = components(people, pair_bonds)
    if not comps or total == 0:
        return {"total": total, "components": 0, "lcc": 0, "lcc_pct": 0.0}

    lcc = len(comps[0] - default)
    return {
        "total": total,
        "components": len(comps),
        "lcc": lcc,
        "lcc_pct": round(lcc / total * 100, 1),
    }
