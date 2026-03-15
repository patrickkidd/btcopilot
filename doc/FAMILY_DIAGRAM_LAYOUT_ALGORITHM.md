# Family Diagram Layout Algorithm Specification

**Version**: 1.0 (Empirically Validated)
**Status**: Active
**Related**: [FAMILY_DIAGRAM_VISUAL_SPEC.md](./FAMILY_DIAGRAM_VISUAL_SPEC.md)
**GT Analysis**: 49 real clinical diagrams, 1904 people, 614 partner pairs, 1200 parent-child measurements

This document specifies the layout algorithm for positioning people and relationships in a Bowen family diagram. It is language and toolkit agnostic.

---

## Purpose

The visual specification defines WHAT a family diagram should look like. This document defines HOW to compute positions that satisfy those requirements. All invariants and soft constraints below were derived empirically from 49 real clinical diagrams manually arranged by a trained Bowen theory practitioner.

---

## Empirical Findings Summary

These measurements were taken from ground truth data and supersede prior assumptions.

| Rule | Compliance | Notes |
|------|-----------|-------|
| Children always below parents | **100%** | Hard invariant — no exceptions |
| Partners at same Y | **96%** within 100px | Hard invariant in practice (median Y-diff = 6px) |
| Male left of female | **86%** | Default rule; overridden by structural constraints |
| Children centered under parents | **65%** within 50px | Soft constraint; median offset = 29px |
| Same-generation → same Y (global) | **0%** | **FALSE** — remove from all specs and prompts |
| Same-generation → same Y (within subtree ≤5 people) | **91%** | Holds locally, not globally |
| Generation gap | 2.2× person height | median=244px for size-5 people; stdev=116px |
| Partner horizontal spacing | median=375px, mean=555px | Highly variable; not a reliable constant |

---

## Coordinate System

- **Origin**: Scene center (0, 0)
- **X-axis**: Increases rightward
- **Y-axis**: Increases downward (higher Y = lower on screen)
- **Person position**: Center of the person's symbol

```
X increases →
↓ Y increases
         (0,0)
    ┌───┐
    │   │  Person at (x, y)
    └───┘
```

---

## Person Sizes

Person symbols are squares/circles scaled by a `size` property (1–5):

| size | pixel dimension |
|------|----------------|
| 1 | 8px |
| 2 | 16px |
| 3 | 40px |
| 4 | 80px |
| 5 | 125px |

All spacing calculations should be proportional to the person's pixel dimension, not hardcoded pixel values.

---

## Invariants (MUST NEVER BE VIOLATED)

These constraints must hold after every step of the algorithm.

### INV-1: No Overlapping Bounding Boxes

No two people may have overlapping bounding boxes. Minimum gap between any two bounding boxes: `0.3 × avg(width_a, width_b)`.

**Test**: For all pairs (A, B): bounding boxes do not overlap with the minimum gap.

### INV-2: Partner Adjacency

Partners in a pair bond must be horizontally adjacent at the same Y coordinate. Vertical Y-difference must be ≤ 30px. Horizontal gap between their bounding boxes: `0.3 × avg(width_a, width_b)` minimum.

**Test**: For all pair bonds: `|personA.y - personB.y| ≤ 30`

### INV-3: Partner Integrity

No person may be positioned between two partners of a pair bond (horizontally, at the same Y).

**Test**: For pair bond with persons at x1, x2 (x1 < x2): no other person has x where x1 < x < x2 at same Y-level.

### INV-4: Children Below Parents *(replaces former "same Y per generation" invariant)*

For every person with known parents: `child.y > max(parent_a.y, parent_b.y)`.

**Test**: For all (child, parent_a, parent_b) triples: `child.y > max(parent_a.y, parent_b.y)`

**Why the old INV-4 was wrong**: "All same-generation people at same Y" fails in 100% of real diagrams with ≥6 people. When two family trees are joined by marriage, the married-in spouse is placed at the same Y as their partner (INV-2), but their own parents' subtree may be at a completely different absolute Y level. Strict global Y-alignment is therefore geometrically impossible in multi-family diagrams.

---

## Soft Constraints (Optimize When Possible)

### SOFT-1: Children Centered Under Parents

The midpoint X of all children of a given parent pair should be within 50px of the midpoint X of the two parents. Holds in 65% of GT cases (median offset 29px).

### SOFT-2: Male Left of Female

In mixed-gender pair bonds, the male should be to the left of the female. Holds in 86% of GT cases. Override when structural constraints (existing positions, prior marriages) would require moving already-placed people.

### SOFT-3: Sibling Birth-Order → Left-to-Right

When birth dates are known, older siblings should be positioned to the left of younger siblings.

### SOFT-4: Minimal Horizontal Width

The diagram should be as compact as possible without violating invariants.

### SOFT-5: Local Y-Consistency

Within a nuclear chain (2–5 people connected by a single couple → children path), people in the same generation should be at approximately the same Y. This holds in 91% of small subtrees.

---

## Algorithm: Recursive Subtree Layout

The key insight from GT analysis: **family diagrams are forests, not trees**. Multiple independent family subtrees (each rooted at a childless couple or individual) are laid out independently and then packed horizontally. Trying to assign global Y coordinates by graph depth fails because different subtrees have independently determined vertical positions.

### Phase 0: Data Preparation

Build lookup structures:
- `byId`: Map person_id → person
- `partnersByPerson`: Map person_id → [partner_ids] (via pair bonds)
- `childrenByCouple`: Map (person_a_id, person_b_id) → [child_ids]
- `parentCouple`: Map person_id → (parent_a_id, parent_b_id) or null

### Phase 1: Identify Root Couples

A **root couple** is a pair bond where neither partner has known parents in this diagram. Root couples are the top-level anchors of independent family subtrees.

Root individuals (unpaired people with no known parents) are also layout roots.

Process root couples/individuals in the order they appear in the data (no forced global ordering).

### Phase 2: Recursive Subtree Placement

For each root couple/individual, recursively compute positions:

```
function placeSubtree(coupleOrPerson, x, y):
    place couple at (x, y) with male left of female (SOFT-2)

    children = childrenByCouple[couple] (sorted by birthDate if known, else by ID)
    if no children: return bounding width of couple

    // Compute total width needed for children's subtrees
    childWidths = [subtreeWidth(child) for child in children]
    totalWidth = sum(childWidths) + gaps

    // Place children centered under couple (SOFT-1), below couple (INV-4)
    childY = y + couple.height + generationGap(couple.size)
    startX = coupleX - totalWidth / 2
    for each child:
        placeSubtree(child's couple, startX + childWidth/2, childY)
        startX += childWidth + gap
```

**Generation gap** between a parent couple and their children:
- Default: `2.2 × parent_symbol_height` (empirical median)
- Minimum: `1.5 × parent_symbol_height`

### Phase 3: Married-In Spouses

When a child in one subtree marries someone from another subtree (or an unparented individual), the spouse is placed adjacent to the child (INV-2) at the same Y level. The spouse's own parents' subtree, if present, must then be connected.

**Conflict resolution**: If placing the married-in spouse adjacent to their partner would conflict with that spouse's own parents' positions (different Y level), the spouse's parent subtree takes priority and the couple's Y is adjusted to satisfy INV-4 for both sides. This is the primary source of Y-level variation in large diagrams — it is expected and correct behavior.

### Phase 4: Pack Independent Subtrees

After each root subtree is internally laid out, pack them horizontally left-to-right with a gap of `2 × largest_person_size` between their bounding boxes.

Vertical position of each subtree's root can be adjusted so that the most-connected person (most family relationships) is vertically centered in the viewport.

### Phase 5: Collision Resolution

Scan all person positions for INV-1 violations. For any collision, shift the right-side person (and all their descendants) right until the gap is satisfied. Repeat until no collisions.

### Phase 6: Compaction

After collision resolution, scan for unnecessary horizontal gaps. Close gaps that don't involve couple adjacency constraints. Apply left-to-right, then right-to-left, to avoid bias.

---

## Constants and Proportional Spacing

All spacing is proportional to person symbol size, not hardcoded pixels. For size-5 people (125px):

| Measurement | Formula | Size-5 value |
|-------------|---------|-------------|
| Min horizontal gap between people | `0.3 × avg_width` | ~38px |
| Partner spacing (center-to-center) | `1.3 × avg_width` | ~163px |
| Generation gap | `2.2 × parent_height` | ~275px |
| Between-subtree gap | `2.0 × max_size_px` | ~250px |

Note: GT data shows high variance in partner spacing (median 375px, mean 555px), suggesting practitioners freely vary this. Use the formula as a default, not a constraint.

---

## Test Cases

### TC-1: Simple Nuclear Family

```
Input: Father + Mother (pair bond), one Child (parents: Father+Mother)

Expected:
  Father: left of Mother, same Y
  Mother: right of Father, same Y
  Child: below both parents, X between Father and Mother

Invariants checked: INV-1, INV-2, INV-4, SOFT-1, SOFT-2
```

### TC-2: Three-Generation Chain

```
Input: Grandpa + Grandma → Father → Father + Mother → Son + Daughter

Expected:
  Grandpa, Grandma: top row, male left
  Father: below Grandpa/Grandma, Mother adjacent
  Son, Daughter: below Father/Mother, ordered by birth if known

Invariants checked: INV-1, INV-2, INV-3, INV-4, SOFT-2, SOFT-3
```

### TC-3: Two Independent Families Joined by Marriage

```
Input:
  Family A: GpaA + GmaA → DadA  (GpaA and GmaA have no parents)
  Family B: GpaB + GmaB → MomB  (GpaB and GmaB have no parents)
  DadA married MomB → Child

Expected:
  Family A subtree laid out independently
  Family B subtree laid out independently
  DadA and MomB adjacent at same Y (INV-2)
  IF Family A root Y ≠ Family B root Y: DadA and MomB's Y is
    a compromise that satisfies INV-4 for both sides
  Child below DadA and MomB

Key: DadA.y and MomB.y need NOT equal GpaA.y + gap or GpaB.y + gap
     They are placed where they need to be to satisfy INV-2 and INV-4.

Invariants checked: INV-1, INV-2, INV-4, SOFT-1
```

### TC-4: Person with Multiple Pair Bonds

```
Input: Person A married to B (divorced), then to C

Expected:
  A is center anchor
  B and C on either side of A (or both on same side with separator)
  Children of A+B below A+B couple
  Children of A+C below A+C couple
  No children of A+B between A and C (INV-3)

Invariants checked: INV-1, INV-2, INV-3, INV-4
```

---

## What Does NOT Work (Empirically Refuted)

These approaches were tried and failed, and must not be re-attempted:

### ❌ Global Generation-to-Y Assignment

Assigning `Y = BASE_Y + generation_depth × GENERATION_GAP` fails in all real diagrams with ≥6 people. The reason: when two family trees join by marriage, the Y levels of the two trees are independently determined and cannot be reconciled with a global formula.

### ❌ Single-Pass Phase Algorithm with Y-Alignment Invariant

The prior version of this spec (v0.3) used a 5-phase algorithm where Phase 1 assigned global Y-coordinates by generation depth and Phase 2 placed people horizontally within rows. This was implemented with Claude Opus and produced poor results on real diagrams. The fundamental flaw was INV-4 (old form: same-generation → same Y), which does not hold in real data.

### ❌ LLM Direct Coordinate Assignment (Gemini/GPT)

Asking an LLM to output (x, y) coordinates for each person fails because:
- LLMs cannot reliably perform multi-step numerical constraint satisfaction
- Collision detection requires iterative spatial reasoning the LLM cannot do in one pass
- Output coordinates are often inconsistent (violate INV-2 by large margins)

LLMs can be useful for: ordering siblings when birth dates are unknown, choosing which side to place a married-in spouse, resolving ambiguous cases. Not for computing coordinates directly.

---

## Implementation Notes

### Current Implementation Status (2026-03-11)

**Implemented** (`familydiagram/bin/fd_layout.py`):
- Phase 1: Root identification and grouping into root-root couples
- Phase 2: Recursive subtree placement with proportional spacing
- Phase 3 (partial): Two-pass root loop that handles root+non-root marriages
  - Pass 1: Roots with no pre-placed children (standard subtrees)
  - Pass 2: Roots whose child was already placed (anchored above placed child)
  - Deferred roots: roots whose only partners have parents are skipped in Pass 1 — placed by the partner's family subtree when it runs
  - `coupled_roots`: IDs of roots paired together in root-root couples; `place_person` skips these as unplaced partners to prevent premature displacement

**Known limitation — non-root cross-family marriages**: When two non-root children from different subtrees marry each other (TC-3 with both parents in diagram), whoever is placed first "pulls" their partner into the wrong subtree's x-zone. The partner's siblings in the other subtree then connect to their bar via diagonal child lines. This requires Phase 5 (collision/repositioning post-pass) to fix properly and is not yet implemented.

**Not yet implemented**: Phases 4–6 (subtree packing optimization, collision resolution, compaction). The current algorithm uses sequential x-advancement for subtrees which is functional but not optimal.

### For Deterministic Algorithm Implementation

Implement Phase 2 (Recursive Subtree Placement) first. It handles the common case (nuclear families, 3-generation chains). Phases 3–6 handle edge cases and can be added incrementally.

The recursive approach naturally satisfies INV-4 without any global coordination. INV-2 and INV-3 are enforced during Phase 2 by always placing partners adjacent before placing children.

### For LLM-Based Implementation

When providing this spec to an LLM, emphasize:
1. The LLM should determine **ordering and side placement** (which sibling is leftmost, which side a married-in spouse goes on), not absolute coordinates
2. A deterministic post-processing step should compute actual coordinates from the ordering
3. The most useful LLM contribution is resolving ambiguous cases in Phase 2 and Phase 3

Provide TC-1 through TC-4 as few-shot examples with both the input and the expected output ordering (not coordinates).

---

## Failure Log

### F-0001: Kevin/Michael Label Collision
- **Date**: 2024-12-23
- **Source**: Statement 2020
- **Symptom**: Kevin and Michael labels overlap after compaction
- **Root Cause**: Compaction reduced gaps between different family units to PERSON_SPACING, but these are different family subtrees needing more separation
- **Resolution**: Addressed by Phase 4 (Pack Independent Subtrees) which uses a larger between-subtree gap

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2024-12-23 | Initial draft |
| 0.2 | 2024-12-23 | Added Self-Improvement Protocol |
| 0.3 | 2024-12-23 | Added standalone context, complete worked example |
| 1.0 | 2026-03-11 | Complete rewrite based on GT analysis of 49 real clinical diagrams. Replaced false INV-4 (global Y-alignment) with empirically correct INV-4 (children below parents). Replaced phase-based global algorithm with recursive subtree layout. Added empirical measurements. Documented what does not work. |
| 1.1 | 2026-03-11 | Added current implementation status. Documented Phase 3 two-pass approach (deferred roots, coupled_roots). Documented known limitation: non-root cross-family marriages produce diagonal child lines. |
