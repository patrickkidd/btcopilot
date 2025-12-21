# Family Diagram Arrangement Specification

**Version**: 1.0
**Status**: Draft
**Purpose**: A platform-independent specification for arranging and rendering family diagrams (Bowen theory family diagrams, distinct from McGoldrick genograms).

This specification is intended to be:
- Human-readable for clinicians, academics, and family systems enthusiasts
- Machine-readable for implementing layout algorithms in any programming language
- Implementation-agnostic (no code, no framework dependencies)

---

## 1. Core Concepts

### 1.1 Person

A **Person** is an individual represented on the diagram.

**Visual representation**:
- **Male**: Square (rectangle with equal width and height)
- **Female**: Circle (ellipse with equal width and height)
- **Unknown gender**: Rounded rectangle with "?" displayed inside
- **Pregnancy loss**: Downward-pointing triangle
  - Abortion and miscarriage use the same triangle shape
  - Distinguished by label text if needed

**Primary/Client Person(s)**:
- The index person(s) are the central focus of the diagram
- Drawn with a **double outline** (inner shape plus outer shape with margin)
- The double-line margin is approximately 10% of the shape's size
- **Multiple primary persons are allowed** (e.g., a couple working on their diagram together)

**Deceased indicator**:
- An "X" drawn through the shape (diagonal lines from corners)
- When age is displayed inside, the X lines are shortened to avoid obscuring the age number

### 1.2 PairBond (Marriage/Partnership)

A **PairBond** represents a romantic or reproductive relationship between two persons.

**Visual representation**:
- A "U"-shaped connector with right angles (no curves)
- Path construction:
  1. Vertical line down from Person A's bottom-center
  2. Horizontal line across to Person B's x-coordinate
  3. Vertical line up to Person B's bottom-center

**Positioning conventions**:
- **Male on left**: By convention, males are positioned to the left of females
- **Same gender pairs**: Older person on the left
- **Unknown genders**: Older person on the left; if ages unknown, by entry order

**Horizontal bar positioning**:
- The horizontal bar sits at the y-level of the **lower** person's bottom plus a drop distance
- Drop distance = person height / 2.2 (approximately 45% of person height)

**Relationship status indicators**:
- **Bonded (not married)**: Dashed horizontal line
- **Married**: Solid horizontal line
- **Separated**: One diagonal slash through the horizontal bar
- **Divorced**: Two parallel diagonal slashes through the horizontal bar
- **Custody indicator**: Slashes slant toward the custodial parent

**Marriage date label**:
- Displayed near the horizontal bar (above, below, or to the side)
- Format: "m. MM/DD/YYYY"

### 1.3 ChildOf (Parent-Child Relationship)

A **ChildOf** relationship connects a child to their parents' PairBond.

**Visual representation**:
- A line from the child's top-center to the parents' PairBond horizontal bar
- **Vertical line**: When child is positioned within the horizontal span of the PairBond bar
- **Diagonal line**: When child is positioned outside the bar's horizontal span
  - Attaches to the **nearest corner** (left or right) of the horizontal bar

**Adopted indicator**:
- Adopted children use a **dashed line** for their ChildOf connection
- Solid line indicates biological relationship

### 1.4 MultipleBirth (Twins/Triplets/etc.)

A **MultipleBirth** groups siblings who share the same birth event.

**Visual representation**:
- A horizontal "jig" line connecting all siblings in the multiple birth
- A single vertical line from the jig's center to the parents' PairBond bar
- Individual lines from each sibling down to the jig

**Jig positioning**:
- Positioned at the **vertical midpoint** between the children's connection points and the PairBond bar

---

## 2. Generational Layout

### 2.1 Generation Rows

Persons are organized into horizontal rows by generation:
- **Older generations** are positioned **higher** on the diagram (smaller y-values)
- **Younger generations** are positioned **lower** on the diagram (larger y-values)
- All persons in the same generation should ideally share the same y-coordinate

### 2.2 Vertical Spacing

The ideal vertical gap between generations equals **2x the person symbol height**.

Example: If persons are 100 units tall, the vertical gap between a parent row and child row should be approximately 200 units.

### 2.3 Generation Exceptions

In complex diagrams, exceptions are allowed:
- A person with many descendants may be positioned lower than their siblings to accommodate their subtree
- Staggering (alternating y-values among siblings) is permitted when horizontal space is constrained
- Priority: visual clarity over strict alignment

---

## 3. Horizontal Arrangement

### 3.1 Birth Order

Siblings are arranged left-to-right from **oldest to youngest**:
- Birth order is inferred from birth dates when available
- When birth order is unknown, positions are **user-specified** (no automatic ordering)

### 3.2 Sibling Spacing

**Proportional spacing**:
- Siblings with descendants receive more horizontal space than childless siblings
- The space allocated accounts for the width of their family subtree
- Minimum spacing between siblings = 2x person width

### 3.3 Multiple PairBonds

When a person has multiple partnerships (remarriage, serial relationships):
- Partners are arranged on the **opposite side** from the person's biological family
- Ordered left-to-right from **earlier to later** in time
- The "anchor" person (more connected to the diagram's focus) stays fixed; partners arrange around them
- Partners may be at the **same y-level** as the anchor person, or offset vertically if space requires

**Determining the anchor**:
- The person more biologically related to the primary/client person is the anchor
- Example: Client's sister with three ex-husbands → sister is anchor, husbands arranged to her left
- Example: Client's uncle with three ex-wives → uncle is anchor, wives arranged to his right

### 3.4 Center of PairBond

When partners have different sizes (scaling):
- The visual center accounts for size differences
- The horizontal bar is positioned to appear balanced between the two shapes

---

## 4. Connector Geometry

### 4.1 PairBond Path

Given two persons A and B:
```
A.connectionPoint = A.bottom_center
B.connectionPoint = B.bottom_center
drop = max(A.height, B.height) / 2.2
y_bar = max(A.connectionPoint.y, B.connectionPoint.y) + drop

Path:
  moveTo(A.connectionPoint)
  lineTo(A.connectionPoint.x, y_bar)
  lineTo(B.connectionPoint.x, y_bar)
  lineTo(B.connectionPoint)
```

### 4.2 ChildOf Path

Given a child C and parents' PairBond P:
```
C.connectionPoint = C.top_center
P.bar_left = P.horizontal_bar.left_x
P.bar_right = P.horizontal_bar.right_x
P.bar_y = P.horizontal_bar.y

If C.connectionPoint.x >= P.bar_left AND C.connectionPoint.x <= P.bar_right:
  # Vertical line
  attach_x = C.connectionPoint.x
Else:
  # Diagonal line to nearest corner
  If C.connectionPoint.x < P.bar_left:
    attach_x = P.bar_left
  Else:
    attach_x = P.bar_right

Path:
  moveTo(C.connectionPoint)
  lineTo(attach_x, P.bar_y)
```

### 4.3 MultipleBirth Path

Given children [C1, C2, ...] and parents' PairBond P:
```
# Sort children left to right
children_sorted = sort_by_x(children)
x_min = min(child.connectionPoint.x for child in children_sorted)
x_max = max(child.connectionPoint.x for child in children_sorted)

# Calculate jig y-position (midpoint)
children_top_y = min(child.connectionPoint.y for child in children_sorted)
jig_y = (children_top_y + P.bar_y) / 2

# Horizontal jig line
Path:
  moveTo(x_min, jig_y)
  lineTo(x_max, jig_y)

# Vertical line to parents
jig_center_x = (x_min + x_max) / 2
# Clamp to PairBond bar bounds
attach_x = clamp(jig_center_x, P.bar_left, P.bar_right)

Path (continued):
  moveTo(jig_center_x, jig_y)
  lineTo(attach_x, P.bar_y)
```

---

## 5. Person Symbols

### 5.1 Base Dimensions

The base person symbol is a 100x100 unit square (or circle inscribed within).

### 5.2 Scaling

Persons can be scaled to different sizes for visual emphasis or de-emphasis:

| Size Name | Scale Factor | Dimensions |
|-----------|--------------|------------|
| Large     | 1.25         | 125x125    |
| Medium    | 0.80         | 80x80      |
| Small     | 0.40         | 40x40      |
| Micro     | 0.16         | 16x16      |
| Nano      | 0.064        | 6.4x6.4    |

Default size is Large (scale 1.25).

**Usage of smaller sizes**:
- Micro/Nano sizes are used to **de-emphasize** persons who are less central to the diagram's focus
- Common use: Parents of peripheral family members (e.g., in-laws' parents)
- Small symbols are still **real people** with full PairBonds and ChildOf connections
- Pregnancy losses use **triangle shapes**, not small squares/circles

### 5.3 Shape Coordinates

Person shapes are centered at (0, 0) in their local coordinate system:
- Bounding box: (-width/2, -height/2) to (width/2, height/2)
- Connection point for PairBond: (0, height/2) → bottom center
- Connection point for ChildOf: (0, -height/2) → top center

---

## 6. Labels and Details

### 6.1 Name Label Positioning

- Default position: **Right** of the person symbol, aligned with the top of the shape
- Offset: Approximately 20% of person width to the right of the top-right corner
- **Collision avoidance**: If the label would overlap another element, move it to the left side
- Labels include name on first line, birth date (prefixed with "b.") on second line
- Marriage dates ("m.") appear on or near the PairBond horizontal bar
- **Nicknames**: Displayed in parentheses after the given name, e.g., "Gerald (Geralooooo)"

### 6.2 Age Display

- Age is displayed **centered inside** the person symbol
- Calculated from birth date to current diagram date (or death date if deceased)
- Unknown gender shows "?" instead of age

### 6.3 Date Display

Standard date abbreviations:
- "b." = birth date (for Person) OR bonded date (for PairBond)
- "d." = death date
- "a." = adoption date
- "m." = marriage date
- "s." = separation date

Context determines meaning: "b." on a Person label means birth; "b." on a PairBond label means bonded.

---

## 7. Step Relationships and Blended Families

### 7.1 Step-Parents

Step-parent relationships are **implied**, not explicitly drawn:
- A step-child connects only to their biological parents
- The step-parent relationship is indicated by the step-parent's PairBond with the biological parent

### 7.2 Half-Siblings

Half-siblings share one biological parent:
- Each connects to their own biological parents' PairBond
- The shared parent appears in both PairBonds
- Separation/divorce indicators show relationship history

### 7.3 No Duplicate Persons

Each person appears exactly **once** on the diagram:
- Lines may cross to connect relationships
- No duplicate symbols with connecting lines

---

## 8. Spacing and Layout Guidelines

### 8.1 Minimum Spacing

- Between siblings: 2x person width
- Between unrelated persons in same row: 1.5x person width
- Between generations: 2x person height

### 8.2 Space Efficiency

The layout should balance:
- Visual clarity (no overlapping elements)
- Compact arrangement (minimal wasted space)
- Aesthetic appeal (pleasing proportions)

### 8.3 Large Families

For families with 10+ siblings:
- Single horizontal row is preferred
- Staggering (alternating y-levels) is permitted if horizontal space is constrained
- Persons with descendants may be positioned lower to accommodate their subtrees

---

## 9. Algorithm Considerations

This section provides guidance for implementing layout algorithms.

### 9.1 Layout Order

Recommended processing order:
1. Identify the oldest generation (root ancestors)
2. Process each generation top-to-bottom
3. Within each generation, process by family unit (PairBond + children)
4. Position children relative to their parents' PairBond center

### 9.2 Collision Resolution

When elements would overlap:
1. First priority: Expand horizontal spacing between siblings
2. Second priority: Move labels to alternate positions
3. Third priority: Stagger y-positions within a generation
4. Last resort: Accept some visual complexity in dense areas

### 9.3 Incremental Layout

When adding a new person to an existing diagram:
1. Identify their generation level
2. Find their anchor point (parents or partner)
3. Position relative to existing family members
4. Adjust spacing of existing elements as needed

---

## 10. Relationship Lines Summary

| Relationship Type | Line Style | Attachment Points |
|-------------------|------------|-------------------|
| PairBond (married) | Solid | Bottom-center of both persons |
| PairBond (bonded) | Dashed | Bottom-center of both persons |
| ChildOf (biological) | Solid | Child top-center to PairBond bar |
| ChildOf (adopted) | Dashed | Child top-center to PairBond bar |
| MultipleBirth | Solid | Children to jig, jig to PairBond bar |

---

## 11. Future Extensions

The following elements are planned for future specification versions:

- **SARF indicators**: Anxiety (jagged outline), functioning (bolt symbols), symptom levels
- **Relationship emotions**: Conflict, distance, cutoff, fusion, triangle indicators
- **Timeline integration**: Temporal animation of relationship changes
- **Layer visibility**: Show/hide subsets of the diagram

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| Client | The primary person (index person) of the diagram, typically the person creating or studying the diagram |
| Generation | A horizontal tier of persons at approximately the same generational level (grandparents, parents, children) |
| PairBond | A romantic or reproductive partnership between two persons |
| ChildOf | The parent-child relationship connecting a person to their parents |
| MultipleBirth | A grouping of siblings born together (twins, triplets, etc.) |
| Jig | The horizontal line connecting multiple birth siblings before the vertical line to parents |

---

## Appendix B: Coordinate System

The diagram uses a standard 2D coordinate system:
- **X-axis**: Horizontal, positive values to the right
- **Y-axis**: Vertical, positive values downward (older generations have smaller y-values)
- **Origin**: Typically at the center of the primary/client person or the center of the viewport

---

## Appendix C: Example Layouts

### C.1 Nuclear Family

```
      [Father]—————[Mother]
           |
     ——————+——————
     |     |     |
  [Child1][Child2][Child3]
```

### C.2 Three Generations

```
[GF]—[GM]            [GF]—[GM]
    |                    |
    +————————————————————+
         |         |
      [Father]—[Mother]
           |
     ——————+——————
     |     |     |
  [Child1][Child2][Child3]
```

### C.3 Multiple PairBonds

```
[Ex1]—[Ex2]—[Person]—[Current Partner]
                |
          ——————+——————
          |          |
       [Child1]   [Child2]
```

(Note: These are simplified ASCII representations. Actual diagrams use geometric shapes.)
