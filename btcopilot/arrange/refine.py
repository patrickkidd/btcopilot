"""
Iterative refinement layer for fd_layout.

Implements the "painter" approach: hill-climbing over discrete subtree-slide
moves. Each move slides a subtree (person + right-ward partners + descendants)
horizontally and is accepted only if it improves intrinsic quality without
creating collisions or violating Bowen invariants.

Used as a post-pass in fd_layout.layout() after _sweep + _compact.

Quality is INTRINSIC (collisions, width, compactness) — not GT-based.
GT comparison happens only at the global validation level (fd_fitness.py).
"""

from btcopilot.arrange import layout as fd_layout

SIZE_PX = {1: 8, 2: 16, 3: 40, 4: 80, 5: 125}


def _px(p):
    return SIZE_PX.get(p.get("size", 5), 125) if p else 125


def _build_children_of(by_id):
    children_of = {pid: [] for pid in by_id}
    for p in by_id.values():
        for par in (p.get("parent_a"), p.get("parent_b")):
            if par in children_of:
                children_of[par].append(p["id"])
    return children_of


def _subtree(by_id, children_of, positions, pid):
    """Set of person ids that move with pid: pid + right-ward partners + all descendants."""
    if pid not in positions:
        return set()
    start_x = positions[pid][0]
    seen, queue = set(), [pid]
    while queue:
        curr = queue.pop()
        if curr in seen:
            continue
        seen.add(curr)
        for q in (by_id.get(curr, {}).get("partners") or []):
            if q not in seen and q in positions and positions[q][0] >= start_x:
                queue.append(q)
        queue.extend(children_of.get(curr, []))
    return seen


def _bbox_width(positions):
    if not positions:
        return 0
    xs = [v[0] for v in positions.values()]
    return max(xs) - min(xs)


def _count_collisions(by_id, positions, label_buffer):
    """Count real label-symbol collisions (overlap > label_buffer) AND symbol-symbol overlaps."""
    rows = {}
    for pid, (x, y) in positions.items():
        rows.setdefault(round(y), []).append(pid)
    real = 0
    for row in rows.values():
        row.sort(key=lambda p: positions[p][0])
        for i in range(len(row) - 1):
            pid, qid = row[i], row[i + 1]
            p, q = by_id.get(pid), by_id.get(qid)
            if not p or not q:
                continue
            px, qx = positions[pid][0], positions[qid][0]
            symbol_gap = (qx - _px(q) / 2) - (px + _px(p) / 2)
            if symbol_gap < 0:
                real += 100  # symbol-symbol overlap is a hard failure — heavy weight
            label_right = px + _px(p) / 2 + fd_layout._label_px(p) - label_buffer
            overlap = label_right - (qx - _px(q) / 2)
            if overlap > label_buffer:
                real += 1
    return real


def _has_symbol_overlap(by_id, positions):
    """Check ALL pairs (not just same-row neighbors) for symbol bbox overlap. Hard reject."""
    items = [(pid, positions[pid][0], positions[pid][1], _px(by_id.get(pid))) for pid in positions]
    for i in range(len(items)):
        pid_a, ax, ay, asz = items[i]
        for j in range(i + 1, len(items)):
            pid_b, bx, by, bsz = items[j]
            if abs(ax - bx) < (asz + bsz) / 2 and abs(ay - by) < (asz + bsz) / 2:
                return True
    return False


def _violates_bowen(by_id, positions):
    """Return True if any hard Bowen invariant is broken."""
    for pid, (x, y) in positions.items():
        p = by_id.get(pid)
        if not p:
            continue
        for par_id in (p.get("parent_a"), p.get("parent_b")):
            if par_id and par_id in positions:
                if positions[par_id][1] >= y:
                    return True
        for partner_id in (p.get("partners") or []):
            if partner_id in positions and partner_id < pid:
                if abs(positions[partner_id][1] - y) > 30:
                    return True
    return False


def _quality(by_id, positions, label_buffer):
    """Lower is better. Hard rejections return float('inf')."""
    if _violates_bowen(by_id, positions):
        return float("inf")
    if _has_symbol_overlap(by_id, positions):
        return float("inf")
    collisions = _count_collisions(by_id, positions, label_buffer)
    if collisions > 0:
        return float("inf")
    return _bbox_width(positions)


def _candidate_anchors(by_id, positions, children_of):
    """Persons whose subtree is meaningful to slide.

    Includes:
    - Roots (no parents in positions)
    - Children that anchor a sub-cluster (have own subtree of >= 2 people)
    - Married-in spouses (have a partner whose parents are in the diagram, and own parents not in diagram)
    """
    anchors = []
    for pid, p in by_id.items():
        if pid not in positions:
            continue
        pa, pb = p.get("parent_a"), p.get("parent_b")
        is_root = not (pa in positions or pb in positions)
        sub = _subtree(by_id, children_of, positions, pid)
        if is_root or len(sub) >= 2:
            anchors.append(pid)
    return anchors


def _slide_move(by_id, children_of, pos, pid, delta):
    """Apply a slide of pid's subtree by delta. Returns new positions dict."""
    sub = _subtree(by_id, children_of, pos, pid)
    new_pos = dict(pos)
    for mid in sub:
        if mid in new_pos:
            x, y = new_pos[mid]
            new_pos[mid] = (x + delta, y)
    return new_pos


def _cluster_compress_move(by_id, children_of, pos, parent_pid, scale):
    """Compress parent's children's subtrees toward their collective midpoint by scale (<1.0)."""
    children = [c for c in children_of.get(parent_pid, []) if c in pos]
    if len(children) < 2:
        return None
    xs = [pos[c][0] for c in children]
    center_x = (min(xs) + max(xs)) / 2
    new_pos = dict(pos)
    for c in children:
        sub = _subtree(by_id, children_of, pos, c)
        delta = (scale - 1) * (pos[c][0] - center_x)
        if abs(delta) < 1:
            continue
        for mid in sub:
            if mid in new_pos:
                x, y = new_pos[mid]
                new_pos[mid] = (x + delta, y)
    return new_pos


def _try_best_slide(by_id, children_of, pos, pid, deltas, label_buffer, baseline_q):
    """Try each delta as a slide of pid; return (new_pos, new_q) for best move, or (None, baseline_q)."""
    best_delta, best_q = 0, baseline_q
    for d in deltas:
        trial = _slide_move(by_id, children_of, pos, pid, d)
        q = _quality(by_id, trial, label_buffer)
        if q < best_q:
            best_q, best_delta = q, d
    if best_delta != 0:
        return _slide_move(by_id, children_of, pos, pid, best_delta), best_q
    return None, baseline_q


def _recenter_couple_move(by_id, children_of, pos, person_pid):
    """Move a couple (person + their primary partner) to be horizontally centered above their children."""
    p = by_id.get(person_pid)
    if not p or person_pid not in pos:
        return None
    partners = p.get("partners") or []
    children = children_of.get(person_pid, [])
    if not partners or not children:
        return None
    # Pick the partner that shares the most children
    partner = max(
        partners,
        key=lambda q: sum(1 for c in children if person_pid in (by_id.get(c, {}).get("parent_a"), by_id.get(c, {}).get("parent_b"))
                          and q in (by_id.get(c, {}).get("parent_a"), by_id.get(c, {}).get("parent_b"))),
    )
    if partner not in pos:
        return None

    shared_children = [
        c for c in children
        if c in pos
        and partner in (by_id.get(c, {}).get("parent_a"), by_id.get(c, {}).get("parent_b"))
    ]
    if not shared_children:
        return None
    children_center = sum(pos[c][0] for c in shared_children) / len(shared_children)
    couple_center = (pos[person_pid][0] + pos[partner][0]) / 2
    delta = children_center - couple_center
    if abs(delta) < 5:
        return None

    # Slide both members of the couple by delta (NOT their subtrees — children stay where they are)
    new_pos = dict(pos)
    for member in (person_pid, partner):
        x, y = new_pos[member]
        new_pos[member] = (x + delta, y)
    return new_pos


def _recenter_children_move(by_id, children_of, pos, person_pid):
    """Move the collective children's subtree so their center aligns with their parents' center."""
    p = by_id.get(person_pid)
    if not p or person_pid not in pos:
        return None
    partners = p.get("partners") or []
    children = [c for c in children_of.get(person_pid, []) if c in pos]
    if not partners or not children:
        return None
    partner = max(
        partners,
        key=lambda q: sum(1 for c in children
                          if q in (by_id.get(c, {}).get("parent_a"), by_id.get(c, {}).get("parent_b"))),
    )
    if partner not in pos:
        return None
    shared_children = [
        c for c in children
        if partner in (by_id.get(c, {}).get("parent_a"), by_id.get(c, {}).get("parent_b"))
    ]
    if not shared_children:
        return None
    children_center = sum(pos[c][0] for c in shared_children) / len(shared_children)
    couple_center = (pos[person_pid][0] + pos[partner][0]) / 2
    delta = couple_center - children_center
    if abs(delta) < 5:
        return None
    new_pos = dict(pos)
    moved = set()
    for c in shared_children:
        sub = _subtree(by_id, children_of, pos, c)
        for mid in sub:
            if mid in moved or mid in (person_pid, partner):
                continue
            if mid in new_pos:
                x, y = new_pos[mid]
                new_pos[mid] = (x + delta, y)
                moved.add(mid)
    return new_pos


def _swap_siblings_move(by_id, children_of, pos, parent_pid):
    """Try swapping each pair of adjacent children (and their subtrees) for parent_pid."""
    children = [c for c in children_of.get(parent_pid, []) if c in pos]
    if len(children) < 2:
        return None
    children.sort(key=lambda c: pos[c][0])
    moves = []
    for i in range(len(children) - 1):
        c1, c2 = children[i], children[i + 1]
        sub1 = _subtree(by_id, children_of, pos, c1)
        sub2 = _subtree(by_id, children_of, pos, c2)
        if sub1 & sub2:
            continue  # entangled — skip
        # Compute displacement: center of c1's subtree → center of c2's subtree
        c1_xs = [pos[m][0] for m in sub1 if m in pos]
        c2_xs = [pos[m][0] for m in sub2 if m in pos]
        if not c1_xs or not c2_xs:
            continue
        c1_center = (min(c1_xs) + max(c1_xs)) / 2
        c2_center = (min(c2_xs) + max(c2_xs)) / 2
        new_pos = dict(pos)
        for m in sub1:
            if m in new_pos:
                x, y = new_pos[m]
                new_pos[m] = (x + (c2_center - c1_center), y)
        for m in sub2:
            if m in new_pos:
                x, y = new_pos[m]
                new_pos[m] = (x - (c2_center - c1_center), y)
        moves.append(new_pos)
    return moves


def _try_best_cluster_compress(by_id, children_of, pos, parent_pid, label_buffer, baseline_q):
    """Try compressing parent's children by various scales; return (new_pos, new_q) for best."""
    best_scale, best_q = 1.0, baseline_q
    for scale in (0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3):
        trial = _cluster_compress_move(by_id, children_of, pos, parent_pid, scale)
        if trial is None:
            continue
        q = _quality(by_id, trial, label_buffer)
        if q < best_q:
            best_q, best_scale = q, scale
    if best_scale != 1.0:
        return _cluster_compress_move(by_id, children_of, pos, parent_pid, best_scale), best_q
    return None, baseline_q


def refine(by_id, positions, label_buffer=20, max_passes=40, deltas=None):
    """Hill-climb over slide + cluster-compress moves. Returns refined positions."""
    if deltas is None:
        deltas = [-500, 500, -300, 300, -150, 150, -75, 75, -30, 30, -10, 10]

    children_of = _build_children_of(by_id)
    pos = dict(positions)
    baseline_q = _quality(by_id, pos, label_buffer)
    if baseline_q == float("inf"):
        return positions

    for pass_num in range(max_passes):
        improved_this_pass = False

        # Phase 1: slide each candidate subtree
        for pid in _candidate_anchors(by_id, pos, children_of):
            new_pos, new_q = _try_best_slide(by_id, children_of, pos, pid, deltas, label_buffer, baseline_q)
            if new_pos is not None:
                pos, baseline_q = new_pos, new_q
                improved_this_pass = True

        # Phase 2: cluster-compress each parent's children
        for parent_pid in by_id:
            if parent_pid not in pos:
                continue
            new_pos, new_q = _try_best_cluster_compress(by_id, children_of, pos, parent_pid, label_buffer, baseline_q)
            if new_pos is not None:
                pos, baseline_q = new_pos, new_q
                improved_this_pass = True

        # Phase 3: recenter couples above their children
        for person_pid in by_id:
            new_pos = _recenter_couple_move(by_id, children_of, pos, person_pid)
            if new_pos is None:
                continue
            new_q = _quality(by_id, new_pos, label_buffer)
            if new_q < baseline_q:
                pos, baseline_q = new_pos, new_q
                improved_this_pass = True

        # Phase 4: recenter children under their parents
        for person_pid in by_id:
            new_pos = _recenter_children_move(by_id, children_of, pos, person_pid)
            if new_pos is None:
                continue
            new_q = _quality(by_id, new_pos, label_buffer)
            if new_q < baseline_q:
                pos, baseline_q = new_pos, new_q
                improved_this_pass = True

        # Phase 5: try swapping adjacent siblings (sibling reorder)
        for parent_pid in by_id:
            moves = _swap_siblings_move(by_id, children_of, pos, parent_pid)
            if not moves:
                continue
            for new_pos in moves:
                new_q = _quality(by_id, new_pos, label_buffer)
                if new_q < baseline_q:
                    pos, baseline_q = new_pos, new_q
                    improved_this_pass = True

        if not improved_this_pass:
            break

    return pos
