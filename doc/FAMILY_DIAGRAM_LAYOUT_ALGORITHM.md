# Family Diagram Layout Algorithm Specification

**Version**: 0.3 (Draft)
**Status**: Under Development
**Related**: [FAMILY_DIAGRAM_VISUAL_SPEC.md](./FAMILY_DIAGRAM_VISUAL_SPEC.md)

This document specifies the layout algorithm for positioning people and relationships in a Bowen family diagram. It is language and toolkit agnostic.

---

## Purpose

The visual specification defines WHAT a family diagram should look like. This document defines HOW to compute positions that satisfy those requirements.

---

## Implementation Context

### Current Implementation Location

The algorithm is currently implemented in JavaScript within:
```
btcopilot/btcopilot/training/templates/components/family_diagram_svg.html
```

This is a Jinja2 template that renders an SVG family diagram. The layout logic is in the `computeLayout()` function (approximately lines 190-983).

### How to Test Changes

1. **Start the Flask development server** (user manages this externally on port 8888)
2. **Navigate to a diagram render endpoint**:
   ```
   http://127.0.0.1:8888/training/diagrams/render/<statement_id>/<auditor_id>
   ```
3. **Use chrome-devtools MCP server** to take snapshots and screenshots
4. **Verify invariants manually** by inspecting person positions in the rendered SVG

### Known-Good Test Data

Use these for manual verification during development:

| Test Case | Statement | Discussion | Auditor | URL |
|-----------|-----------|------------|---------|-----|
| Multi-generation family | 1900 | 36 ("Synthetic: Sarah") | `patrick@alaskafamilysystems.com` | `/training/diagrams/render/1900/patrick@alaskafamilysystems.com` |

**CRITICAL**: The `auditor_id` parameter is required to get Ground Truth (GT) data. Without it, AI extraction is used which may lack parent-child relationships. See [DATA_MODEL_FLOW.md](DATA_MODEL_FLOW.md) §12 for GT vs AI data rules.

**Statement 1900 characteristics**:
- Multiple generations with parent-child relationships
- Pair bonds from marriage events
- Tests generation assignment, couple positioning, and canopy rules

### Reference Screenshots (Pro App Ground Truth)

These screenshots from the Pro app show the target layout style:

| Screenshot | Key Features |
|------------|--------------|
| [diagram-gt-1-multi-generation.png](/Users/patrick/Documents/2 - Work/2 - Alaska Family Systems/2 - Personal App/Diagram Arrangement GT/diagram-gt-1-multi-generation.png) | 4 generations, divorce indicators (double slash), deceased markers (X), pair bond bars with marriage dates, labels to right of shapes |
| [diagram-gt-2-complex-family.png](/Users/patrick/Documents/2 - Work/2 - Alaska Family Systems/2 - Personal App/Diagram Arrangement GT/diagram-gt-2-complex-family.png) | Many siblings, multiple marriages per person, geographic annotations, wide horizontal spread |
| [diagram-gt-3-wide-family.png](/Users/patrick/Documents/2 - Work/2 - Alaska Family Systems/2 - Personal App/Diagram Arrangement GT/diagram-gt-3-wide-family.png) | Multiple unrelated family branches, couples from different families joining, label collision avoidance |

**Visual patterns to match**:
- Males (squares) on left, females (circles) on right in couples
- Children centered under parents when possible
- Horizontal pair bond bars connecting couples
- Vertical lines from pair bond bar down to children
- Labels positioned to avoid overlap (right, left, or above)

### Data Flow

1. Python route (`btcopilot/btcopilot/training/routes/diagrams.py`) builds `render_data` from:
   - Committed diagram data (from `Diagram.get_diagram_data()`)
   - PDP (Pending Data Pool) accumulated from statements
   - Events (Married, Bonded, Separated, Divorced)

2. Template receives `render_data` as JSON with three arrays: `people`, `pair_bonds`, `parent_child`

3. JavaScript `computeLayout()` calculates X,Y positions for each person and pair bond

4. SVG elements are rendered at those positions

---

## Data Structures

### Input Data (JSON)

```json
{
  "people": [
    {
      "id": 1,
      "name": "John",
      "gender": "male",      // "male" | "female" | "unknown"
      "deceased": false,
      "primary": false,      // Index person (double outline)
      "parents": 100         // pair_bond_id or null
    }
  ],
  "pair_bonds": [
    {
      "id": 100,
      "person_a": 1,
      "person_b": 2,
      "married": true,
      "separated": false,
      "divorced": false
    }
  ],
  "parent_child": [
    {
      "child_id": 3,
      "pair_bond_id": 100
    }
  ]
}
```

**ID Conventions**:
- Positive IDs: Committed diagram data (persisted)
- Negative IDs: PDP data (extracted from statements, not yet committed)
- ID 1: Always the "User" (primary person)
- ID 2: Reserved for "Assistant" (excluded from rendering)

### Output Layout (Internal)

```javascript
{
  people: {
    [personId]: {
      x: number,           // Horizontal position (pixels)
      y: number,           // Vertical position (pixels)
      person: object,      // Reference to input person object
      labelPosition: string // "right" | "left" | "above-right" | "above-left"
    }
  },
  pairBonds: {
    [pairBondId]: {
      x1: number,          // Left end of horizontal bar
      x2: number,          // Right end of horizontal bar
      coupleX1: number,    // Left partner's X position
      coupleX2: number,    // Right partner's X position
      y: number,           // Vertical position of horizontal bar
      pairBond: object     // Reference to input pair bond object
    }
  }
}
```

---

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `PERSON_SIZE` | 50 | Width/height of person shape (pixels) |
| `PERSON_SPACING` | 120 | Minimum horizontal gap between people |
| `GENERATION_GAP` | 110 | Vertical spacing between generations |
| `PAIR_BOND_DROP` | 23 | Distance from person bottom to pair bond bar (`PERSON_SIZE / 2.2`) |
| `NAME_OFFSET` | 10 | Label offset from person edge (`PERSON_SIZE * 0.2`) |
| `BASE_X` | 100 | Starting X position for leftmost person |
| `CANOPY_PADDING` | 60 | Extra space when expanding parents for canopy (`PERSON_SPACING / 2`) |
| `COLLISION_THRESHOLD` | 145 | Distance for label collision detection (`PERSON_SPACING + PERSON_SIZE/2`) |

---

## Coordinate System

- **Origin**: Top-left of SVG viewport
- **X-axis**: Increases rightward (positive = right)
- **Y-axis**: Increases downward (positive = down)
- **Person position**: Center of the person shape

```
(0,0) ────────────────────► X+
  │
  │    ┌───┐
  │    │ P │ ← Person at (x, y) is centered here
  │    └───┘
  │
  ▼
  Y+
```

### Generation Y Positions

```
Generation 0: y = 100
Generation 1: y = 100 + GENERATION_GAP = 210
Generation 2: y = 100 + 2*GENERATION_GAP = 320
...
Generation N: y = 100 + N*GENERATION_GAP
```

---

## Invariants (MUST NEVER BE VIOLATED)

These constraints must hold after EVERY step of the algorithm. If any step would violate an invariant, that step is WRONG and must be redesigned.

### INV-1: No Collisions
No two people may occupy overlapping positions. Minimum spacing between any two people in the same generation is `PERSON_SPACING`.

**Test**: For all pairs (A, B) in same generation: `|A.x - B.x| >= PERSON_SPACING`

### INV-2: Couple Adjacency
Partners in a pair bond must be adjacent with exactly `PERSON_SPACING` between them (or `1.5 × PERSON_SPACING` if divorced/separated).

**Test**: For all pair bonds: `|personA.x - personB.x| == expected_spacing`

### INV-3: Couple Integrity
No person may be positioned between two partners of a pair bond.

**Test**: For all pair bonds with persons at x1, x2 (x1 < x2): No other person in same generation has x where x1 < x < x2.

### INV-4: Generation Alignment
All people in the same generation have the same Y coordinate.

**Test**: For all people with same generation: `A.y == B.y`

---

## Soft Constraints (Optimize When Possible)

These are goals, not invariants. Violating them produces suboptimal but valid diagrams.

### SOFT-1: Children Under Parents
Children should be positioned horizontally within or near their parents' horizontal span. Ideal: centered under parents.

### SOFT-2: Minimal Width
The diagram should be as compact as possible without violating invariants.

### SOFT-3: Sibling Order
Siblings should be ordered by birth date (oldest left) when known.

---

## Algorithm Phases

The algorithm proceeds in discrete phases. After EACH phase, ALL invariants must be verified. If any invariant is violated, the phase implementation is buggy.

### Phase 0: Data Preparation

**Input**:
- `people[]`: List of {id, name, gender, parents (pair_bond_id or null)}
- `pair_bonds[]`: List of {id, person_a, person_b, married, divorced, separated}
- `parent_child[]`: List of {child_id, pair_bond_id}

**Output**:
- `peopleById`: Map id → person
- `pairBondsByPerson`: Map person_id → [pair_bonds]
- `childrenByPairBond`: Map pair_bond_id → [child_ids]

**Invariant Check**: N/A (no positions yet)

### Phase 1: Generation Assignment

**Goal**: Assign each person a generation number (0 = oldest, increasing downward).

**Rules**:
1. People with parents: generation = parent's generation + 1
2. People without parents:
   - If spouse has generation → use spouse's generation
   - If has children → use (min child generation) - 1
   - Otherwise → generation 0
3. Spouses must have same generation (person with parents wins)

**Output**: `generations`: Map person_id → generation_number

**Invariant Check**: N/A (no positions yet)

### Phase 2: Initial Horizontal Positioning

**Goal**: Assign initial X positions to all people.

**Approach**: Process generations top-to-bottom (0, 1, 2, ...). For each generation:

1. **Identify couples** in this generation (both partners have same generation)
2. **Build family units**: Each couple + their unmarried siblings
3. **Order family units** by parent positions from previous generation
4. **Position sequentially**:
   - Start at `currentX = BASE_X`
   - For each family unit:
     - Place left siblings
     - Place couple (person1, then person2)
     - Place right siblings
     - Add gap between units
5. **Position remaining sibling groups** (children without married siblings in this gen)
6. **Calculate pair bond positions** for this generation (needed for next generation's child positioning)

**Critical**: Children's positions are based on their parents' positions. Parents' positions must be finalized for this generation before children can be positioned.

**Invariant Check After Phase 2**:
- INV-1: Verify no collisions
- INV-2: Verify couple spacing
- INV-3: Verify no interlopers between couples
- INV-4: Verify generation alignment

### Phase 3: Compaction

**Goal**: Reduce diagram width while maintaining all invariants.

**Approach**: Process generations top-to-bottom. For each generation:

1. **Sort people by X position**
2. **For each gap between adjacent people**:
   - If they are a couple: gap MUST equal `PERSON_SPACING` (or divorced spacing)
   - Otherwise: gap should equal `PERSON_SPACING`
3. **Shift people left** to close excess gaps
4. **CRITICAL**: When shifting people, also shift ALL their descendants by the same amount

**Invariant Check After Phase 3**:
- INV-1, INV-2, INV-3, INV-4 (all must pass)

### Phase 4: Canopy Adjustment

**Goal**: Adjust parent positions so unmarried children fall within their span.

**Approach**: For each pair bond with children:

1. Find X range of unmarried children
2. If children fit within parents' current span → no change needed
3. If children extend beyond parents:
   - Calculate required expansion
   - Check for collisions with neighbors
   - Shift ENTIRE couple (maintaining spacing) if possible
   - If collision would result → skip adjustment (children outside parents is acceptable)

**Invariant Check After Phase 4**:
- INV-1, INV-2, INV-3, INV-4 (all must pass)

### Phase 5: Final Pair Bond Calculation

**Goal**: Calculate final pair bond line positions based on final person positions.

**Approach**: For each pair bond, calculate:
- x1, x2: left and right X coordinates
- y: vertical position (below the lower partner)

**Invariant Check**: N/A (pair bond positions derive from person positions)

---

## Algorithm Refinement Process

This algorithm specification is ITERATIVE. Changes must follow this process:

### Step 1: Identify Problem
Document the specific failure case:
- Input data (people, pair_bonds, parent_child)
- Expected positions
- Actual positions
- Which invariant was violated (or which soft constraint failed)

### Step 2: Root Cause Analysis
Identify which phase produced the bug:
- Add logging to show positions after each phase
- Verify invariants after each phase
- Find the FIRST phase where the problem appears

### Step 3: Propose Fix
Before implementing, document:
- What change is proposed
- Why it fixes the problem
- What other cases might be affected
- Predicted positions after the fix

### Step 4: Verify Fix
After implementing:
- Run the failing case → confirm it passes
- Run ALL existing test cases → confirm no regressions
- Manually verify invariants still hold

### Step 5: Update Specification
If the fix changes the algorithm:
- Update the relevant phase description
- Add the test case to regression suite
- Document any new edge cases discovered

---

## Test Cases

Each test case documents:
- Input data
- Expected output positions
- Which invariants/constraints it tests

### TC-1: Simple Nuclear Family
```
Input:
  people: [
    {id: 1, name: "Father", gender: "male", parents: null},
    {id: 2, name: "Mother", gender: "female", parents: null},
    {id: 3, name: "Child", gender: "male", parents: 100}
  ]
  pair_bonds: [{id: 100, person_a: 1, person_b: 2, married: true}]
  parent_child: [{child_id: 3, pair_bond_id: 100}]

Expected:
  Father: gen=0, x=100
  Mother: gen=0, x=220
  Child: gen=1, x=160 (centered under parents)

Tests: INV-1, INV-2, INV-4, SOFT-1
```

### TC-2: Two Married Couples (No Children)
```
Input:
  people: [
    {id: 1, name: "M1", gender: "male", parents: null},
    {id: 2, name: "F1", gender: "female", parents: null},
    {id: 3, name: "M2", gender: "male", parents: null},
    {id: 4, name: "F2", gender: "female", parents: null}
  ]
  pair_bonds: [
    {id: 100, person_a: 1, person_b: 2, married: true},
    {id: 101, person_a: 3, person_b: 4, married: true}
  ]
  parent_child: []

Expected:
  M1: gen=0, x=100
  F1: gen=0, x=220
  M2: gen=0, x=340
  F2: gen=0, x=460

Tests: INV-1, INV-2, INV-3
```

### TC-3: Marriage Between Families (User-Michael Scenario)
```
Input:
  people: [
    {id: -3, name: "Richard", gender: "male", parents: -100},
    {id: -1, name: "Barbara", gender: "female", parents: -101},
    {id: 1, name: "User", gender: "female", parents: -102},
    {id: -30, name: "Michael", gender: "male", parents: null}  // No parents
  ]
  pair_bonds: [
    {id: -100, person_a: -6, person_b: -7, married: true},  // Richard's parents
    {id: -101, person_a: -20, person_b: -22, married: true}, // Barbara's parents
    {id: -102, person_a: -3, person_b: -1, married: true},  // Richard-Barbara
    {id: -31, person_a: 1, person_b: -30, married: true}    // User-Michael (from event)
  ]
  parent_child: [
    {child_id: -3, pair_bond_id: -100},
    {child_id: -1, pair_bond_id: -101},
    {child_id: 1, pair_bond_id: -102}
  ]

Expected:
  - User and Michael adjacent (INV-2)
  - Michael in same generation as User (gen 2)
  - No collisions between any people (INV-1)
  - User-Michael couple not interrupted by anyone (INV-3)

Tests: INV-1, INV-2, INV-3, spouse generation assignment
```

---

## Complete Worked Example

This example shows exact input JSON and expected output coordinates for a three-generation family.

### Input

```json
{
  "people": [
    {"id": 1, "name": "Grandfather", "gender": "male", "parents": null},
    {"id": 2, "name": "Grandmother", "gender": "female", "parents": null},
    {"id": 3, "name": "Father", "gender": "male", "parents": 100},
    {"id": 4, "name": "Mother", "gender": "female", "parents": null},
    {"id": 5, "name": "Son", "gender": "male", "parents": 101},
    {"id": 6, "name": "Daughter", "gender": "female", "parents": 101}
  ],
  "pair_bonds": [
    {"id": 100, "person_a": 1, "person_b": 2, "married": true, "separated": false, "divorced": false},
    {"id": 101, "person_a": 3, "person_b": 4, "married": true, "separated": false, "divorced": false}
  ],
  "parent_child": [
    {"child_id": 3, "pair_bond_id": 100},
    {"child_id": 5, "pair_bond_id": 101},
    {"child_id": 6, "pair_bond_id": 101}
  ]
}
```

### Expected Layout Output

**Generations assigned**:
```
Grandfather (1): gen=0
Grandmother (2): gen=0
Father (3): gen=1
Mother (4): gen=1 (spouse of Father)
Son (5): gen=2
Daughter (6): gen=2
```

**Person positions**:
```
Grandfather: x=100, y=100
Grandmother: x=220, y=100   (100 + PERSON_SPACING)
Father: x=100, y=210        (gen 1 = 100 + GENERATION_GAP)
Mother: x=220, y=210
Son: x=100, y=320           (gen 2 = 100 + 2*GENERATION_GAP)
Daughter: x=220, y=320
```

**Pair bond positions**:
```
PB 100 (Grandparents): x1=100, x2=220, y=123  (100 + PERSON_SIZE/2 + PAIR_BOND_DROP)
PB 101 (Parents): x1=100, x2=220, y=233
```

### Visual Representation

```
Gen 0:    ┌───┐           ○
   y=100  │ 1 │           2
          └───┘
            │             │
            └──────┬──────┘  ← y=123 (pair bond bar)
                   │
Gen 1:    ┌───┐           ○
   y=210  │ 3 │           4
          └───┘
            │             │
            └──────┬──────┘  ← y=233 (pair bond bar)
                   │
                ───┴───
               │       │
Gen 2:    ┌───┐       ○
   y=320  │ 5 │       6
          └───┘

   x=100      x=220
```

### Invariant Verification

- **INV-1 (No Collisions)**: All people in same generation are 120px apart ✓
- **INV-2 (Couple Adjacency)**: All couples are exactly 120px apart ✓
- **INV-3 (Couple Integrity)**: No interlopers between any couples ✓
- **INV-4 (Generation Alignment)**: All same-gen people at same Y ✓
- **SOFT-1 (Children Under Parents)**: Son and Daughter are within Father-Mother span ✓

---

## Alternative Approach: Iterative Refinement

The phase-based approach above assumes we can compute correct positions in a single pass. In practice, family diagrams have complex interdependencies that make single-pass solutions fragile.

A more robust approach is **iterative refinement**, similar to how a human would arrange a diagram:

### Core Concept

1. **Initial placement**: Put people in roughly correct positions
2. **Detect violations**: Find invariant violations and constraint failures
3. **Fix one problem**: Make a small adjustment to fix one issue
4. **Repeat** until no violations remain or max iterations reached

### Advantages

- **Robust**: Handles edge cases naturally through iteration
- **Debuggable**: Each step is small and verifiable
- **Extensible**: New constraints can be added without redesigning the whole algorithm
- **AI-compatible**: Can use LLM to reason about "what adjustment would help most"

### Iterative Algorithm Sketch

```
function layoutDiagram(data):
    positions = initialPlacement(data)

    for iteration in 1..MAX_ITERATIONS:
        violations = detectViolations(positions, data)

        if violations.empty():
            return positions  # Success!

        # Pick the most important violation to fix
        violation = prioritize(violations)

        # Compute a fix (could be deterministic or AI-assisted)
        adjustment = computeAdjustment(positions, violation)

        # Apply the adjustment
        positions = applyAdjustment(positions, adjustment)

        # Verify we didn't make things worse
        newViolations = detectViolations(positions, data)
        if count(newViolations) > count(violations):
            rollback(positions, adjustment)
            # Try a different approach or give up on this violation

    return positions  # Best effort
```

### Violation Detection

Each iteration checks:
1. **Collision**: Any two people at same X in same generation
2. **Couple broken**: Partners not at expected spacing
3. **Interloper**: Someone between couple partners
4. **Misaligned generation**: People at wrong Y for their generation
5. **Children outside parents**: Unmarried children far from parents (soft)
6. **Excessive width**: Diagram wider than necessary (soft)

### Adjustment Types

Possible adjustments to fix violations:
- `SHIFT_PERSON(id, deltaX)`: Move one person left/right
- `SHIFT_GROUP(ids[], deltaX)`: Move a group together
- `SHIFT_GENERATION(gen, deltaX)`: Move entire generation
- `SWAP_POSITIONS(id1, id2)`: Exchange two people's positions
- `EXPAND_COUPLE(pb_id, amount)`: Increase spacing between partners
- `CONTRACT_COUPLE(pb_id, amount)`: Decrease spacing between partners

### Using AI for Adjustment Selection

An LLM can reason about which adjustment would best fix a violation:

```
Prompt:
  Current positions: {Father: x=100, Mother: x=220, Child: x=400, Uncle: x=300}
  Violation: Child (at x=400) is outside parents' span (100-220)

  What adjustment would fix this while minimizing disruption?

  Options:
  A) Shift Child left to x=160
  B) Expand parents: Father to x=100, Mother to x=400
  C) Shift Uncle right, then shift Child left

Response reasoning:
  Option A is simplest - move child under parents.
  Option B would create huge gap.
  Option C is complex.

  Recommended: SHIFT_PERSON(Child, -240)
```

### Convergence Guarantees

To prevent infinite loops:
1. **Max iterations**: Hard cap (e.g., 100 iterations)
2. **Monotonic progress**: Track total violation count; if it increases, rollback
3. **Violation memory**: Don't repeatedly try the same fix for the same violation
4. **Fallback**: If stuck, accept suboptimal layout with warnings

### Implementation Stages

1. **Stage 1**: Implement deterministic violation detection and simple adjustments
2. **Stage 2**: Add prioritization heuristics (which violations to fix first)
3. **Stage 3**: Add AI-assisted adjustment selection for complex cases
4. **Stage 4**: Learn from corrections (if user manually adjusts, learn the pattern)

---

## Open Questions

1. **Compaction + Descendants**: When compacting generation N, should we automatically shift generation N+1, N+2, etc.? Current spec says yes, but this adds complexity.

2. **Canopy vs Compact Interaction**: If canopy expands parents, does that affect their generation's compaction? Order of operations matters.

3. **Multiple Marriages**: How to handle a person with 3+ spouses? Visual spec says partners arrange "around" the anchor, but algorithm details unclear.

4. **AI Integration**: What's the right balance between deterministic rules and AI reasoning? Start deterministic, escalate to AI for edge cases?

---

## Self-Improvement Protocol

This specification improves incrementally through failure analysis. When a diagram renders incorrectly:

### Recording Failures

Add failures to the **Failure Log** below. Each entry includes:
- Statement ID or diagram file
- What's wrong (screenshot description or specific violation)
- Root cause hypothesis (after investigation)
- Resolution status

**DO NOT modify the algorithm description based on a single failure.** Failures accumulate in the log until patterns emerge.

### Escalation Thresholds

| Failure Count | Action |
|---------------|--------|
| 1 | Log the failure, investigate root cause, note hypothesis |
| 2 (same root cause) | Add to "Known Issues" section, propose fix |
| 3+ (same root cause) | Implement fix, update algorithm description, add test case |

This prevents thrashing from one-off edge cases while ensuring persistent problems get addressed.

### Modification Rules

When updating the algorithm description:

1. **Additive changes preferred**: Add new rules, constraints, or handling rather than replacing existing logic
2. **Mark deprecated, don't delete**: If an approach is superseded, mark it `[DEPRECATED: reason]` rather than removing it
3. **Version the changes**: Every modification gets a revision history entry with rationale
4. **Preserve test cases**: Never remove test cases; only add new ones
5. **Link to failures**: Reference the failure log entries that motivated each change

### Anti-Thrashing Safeguards

Before making ANY change to the algorithm:

1. **Check failure log**: Is this a pattern (3+ occurrences) or isolated incident?
2. **Check recent history**: Was this area modified in the last 2 revisions? If yes, pause and reconsider.
3. **Predict impact**: List which existing test cases might be affected
4. **Require verification**: Change is not complete until all test cases pass

---

## Known Issues

*Issues that have been identified but not yet resolved. Promoted from Failure Log when pattern emerges.*

| Issue ID | Description | Failure Count | Proposed Fix | Status |
|----------|-------------|---------------|--------------|--------|
| | | | | |

---

## Failure Log

*Raw log of rendering failures. Investigate and categorize, but don't immediately fix.*

### Template

```
### F-XXXX: [Brief Description]
- **Date**: YYYY-MM-DD
- **Source**: Statement ID / Diagram file / URL
- **Symptom**: What looks wrong
- **Expected**: What should happen
- **Actual**: What happened
- **Root Cause Hypothesis**: (after investigation)
- **Related Issues**: (link to Known Issues if pattern matches)
- **Resolution**: (pending / linked to Issue X / won't fix: reason)
```

### Entries

### F-0001: Kevin/Michael Label Collision
- **Date**: 2024-12-23
- **Source**: Statement 2020, `/training/diagrams/render/2020/patrick@alaskafamilysystems.com`
- **Symptom**: Kevin and Michael labels overlap, appearing as "Küchanl" in generation 2
- **Expected**: Kevin-Lisa couple should be positioned separately from User-Michael couple with clear spacing
- **Actual**: After compaction, Kevin at x=460 collides visually with Michael at x=340 (only 120px apart, labels overlap)
- **Root Cause Hypothesis**: Compaction phase reduces gaps without considering that different family units need more than minimum spacing. The gap between Michael (User's spouse) and Kevin (separate couple) was reduced to PERSON_SPACING, but these are different family units that should have FAMILY_UNIT_GAP between them.
- **Related Issues**: None yet
- **Resolution**: Pending - logged as first occurrence, need to see if pattern repeats

### F-0002: Canopy Expanding Parents Independently (INV-2 Violation)
- **Date**: 2024-12-24
- **Source**: Statement 2020, `/training/diagrams/render/2020/patrick@alaskafamilysystems.com`
- **Symptom**: Richard at x=100, Barbara at x=400 (300px gap instead of 120px)
- **Expected**: Richard-Barbara should be adjacent (120px apart) as a married couple
- **Actual**: Phase 4 canopy moved Barbara right to cover children, but left Richard in place
- **Root Cause**: `_phase4_canopy` had `rightParent.x = requiredRight` without also moving leftParent
- **Related Issues**: INV-2 violation
- **Resolution**: Fixed 2024-12-24 - Canopy now shifts ENTIRE couple as a unit to center over children

### F-0003: Compaction Ignoring Parent Positions
- **Date**: 2024-12-24
- **Source**: Statement 2020, `/training/diagrams/render/2020/patrick@alaskafamilysystems.com`
- **Symptom**: Twin 1/Twin 2 at x=100,220 while parents Kevin-Lisa at x=460,580
- **Expected**: Twins should be positioned under Kevin-Lisa (~x=460,580)
- **Actual**: Phase 3 compaction shifted Gen 3 left to BASE_X regardless of parent positions
- **Root Cause**: Compaction computed `minStartX = BASE_X` for every generation, ignoring parent positions
- **Related Issues**: SOFT-1 violation (children under parents)
- **Resolution**: Fixed 2024-12-24 - Compaction now computes minStartX based on parent pair bond positions

### F-0004: Pair Bonds Calculated Too Late
- **Date**: 2024-12-24
- **Source**: Statement 2020, `/training/diagrams/render/2020/patrick@alaskafamilysystems.com`
- **Symptom**: Children not centered under parents despite `_positionRemainingSiblings` logic
- **Expected**: Children positioned relative to parent pair bond center
- **Actual**: `ctx.layout.pairBonds` was empty during Phase 2 child positioning
- **Root Cause**: Pair bonds calculated in Phase 5, but needed during Phase 2 for child positioning
- **Related Issues**: F-0003 (same symptom, different root cause)
- **Resolution**: Fixed 2024-12-24 - Added `_updatePairBondsForGeneration()` called after each generation in Phase 2

---

## Implementation Notes

Critical timing requirements discovered during debugging:

### Pair Bond Calculation Timing
The spec says "Calculate pair bond positions for this generation (needed for next generation's child positioning)" but doesn't emphasize HOW critical this timing is. Pair bonds MUST be calculated **immediately after each generation is positioned**, not in a separate Phase 5. Otherwise:
- `_positionRemainingSiblings` can't center children under parents (uses `ctx.layout.pairBonds`)
- `_phase3_compaction` can't respect parent positions (checks `ctx.layout.pairBonds`)

Implementation: `_updatePairBondsForGeneration(ctx, data, gen)` called at end of each generation's processing in Phase 2.

### Compaction vs Descendants
The spec says "shift ALL their descendants by the same amount" but this is complex to implement correctly. An alternative approach (currently implemented): instead of shifting descendants, prevent compaction from shifting children left of their parents' span. This achieves the same goal (children stay under parents) without cascading shifts.

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2024-12-23 | Initial draft. Defines invariants, phases, refinement process. |
| 0.2 | 2024-12-23 | Added Self-Improvement Protocol with failure log, escalation thresholds, and anti-thrashing safeguards. |
| 0.3 | 2024-12-23 | Added standalone context: Implementation location, data structures, constants, coordinate system, complete worked example. Document now usable in separate thread with no prior context. |
| 0.4 | 2024-12-23 | Added "Known-Good Test Data" section with Statement 1900 test case. Updated URL format to include auditor_id parameter (required for GT data). |
| 0.5 | 2024-12-23 | Added "Reference Screenshots" section with 3 Pro app GT examples showing target layout style. |
| 0.6 | 2024-12-24 | Added F-0002 through F-0004 to Failure Log (all fixed). Added "Implementation Notes" section documenting critical pair bond timing and compaction approach. |

