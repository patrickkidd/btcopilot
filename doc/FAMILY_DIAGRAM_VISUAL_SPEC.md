# The Bowen Family Diagram

## Visual Conventions for Mapping Family Emotional Process

**Version**: 1.0
**Status**: Draft

This document describes the visual conventions for drawing a Bowen family diagram—a tool for mapping the multigenerational emotional processes in a family system. While related to McGoldrick's genogram, the Bowen family diagram emphasizes the emotional system and intergenerational patterns central to Bowen theory.

This guide is intended for clinicians, researchers, students, and anyone learning to construct or read family diagrams. It is detailed enough to serve as a reference for software implementations.

---

## Overview

A family diagram maps biological and emotional relationships across generations. The diagram flows from older generations at the top to younger generations at the bottom. Relationships are indicated exclusively by connecting lines—never by proximity or position alone.

**Core principle**: Only infer family relationships from connecting lines, not from position or size.

---

## 1. Representing Individuals

### Basic Shapes

Each person is represented by a geometric shape:

- **Male**: Square
- **Female**: Circle
- **Unknown gender**: Rounded rectangle with "?" displayed inside
- **Pregnancy loss** (miscarriage or abortion): Downward-pointing triangle

All shapes use the same base dimensions (a square and its inscribed circle have equal bounding boxes).

### The Index Person (Client)

The person(s) at the center of the clinical focus are drawn with a **double outline**—a shape within a shape. The outer shape is approximately 10% larger than the inner shape. Multiple index persons are permitted (e.g., a couple constructing their diagram together).

### Deceased Individuals

A deceased person is indicated by an **"X" drawn through** their shape—two diagonal lines connecting opposite corners. When age is displayed inside the shape, the X lines are shortened at the corners to keep the age legible.

### Age Display

A person's current age (or age at death) is displayed **centered inside** their shape as a number.

### Size for Emphasis

Persons may be drawn at different sizes to indicate their centrality to the diagram:

| Size | Relative Scale | Use |
|------|----------------|-----|
| Large | 1.25× | Default; central figures |
| Medium | 0.80× | Moderate emphasis |
| Small | 0.40× | Peripheral figures |
| Micro | 0.16× | Very peripheral (e.g., in-laws' parents) |
| Nano | 0.06× | Minimal presence |

Smaller symbols still represent real people with full relationship connections. Pregnancy losses always use triangle shapes regardless of size.

---

## 2. Representing Pair Bonds

A **pair bond** is a romantic or reproductive partnership between two persons.

### Visual Form

The pair bond is drawn as a **squared "U" shape** connecting both partners:

1. A vertical line descends from the bottom center of Person A
2. A horizontal line extends across to Person B's position
3. A vertical line rises to the bottom center of Person B

All corners are right angles (90°). The horizontal bar sits below both persons at a distance of approximately 45% of the person's height (or more precisely, height ÷ 2.2).

When partners are at different vertical positions, the horizontal bar aligns with the **lower** person's level plus the drop distance.

### Positioning Convention

By convention:
- **Males are placed on the left**, females on the right
- For same-gender couples: the older person is placed on the left
- If ages are unknown: placement is at the user's discretion

### Relationship Status

The style of the horizontal line indicates the relationship status:

| Status | Line Style |
|--------|------------|
| Married | Solid line |
| Bonded (not married) | Dashed line |
| Separated | One diagonal slash through the line |
| Divorced | Two parallel diagonal slashes through the line |

When custody is relevant following separation or divorce, the slashes slant toward the custodial parent.

### Dates on Pair Bonds

Relationship dates appear near the horizontal bar (above, below, or beside it):
- "b." followed by date = Bonded date
- "m." followed by date = Marriage date
- "s." followed by date = Separation date
- "d." followed by date = Divorce date

---

## 3. Representing Parent-Child Relationships

Children connect to their parents via a line from the **top center** of the child's symbol to the parents' pair bond horizontal bar.

### Line Attachment Rules

- **Vertical line**: When the child is positioned within the horizontal span of the parents' bar, the line drops straight down to the bar.
- **Diagonal line**: When the child is positioned outside the horizontal span of the parents' bar, the line angles toward the **nearest corner** (left or right end) of the bar.

The attachment point is always on the parents' horizontal bar, never on the vertical portions of the pair bond.

### Biological vs. Adopted

- **Biological children**: Solid line
- **Adopted children**: Dashed line

### Multiple Births (Twins, Triplets, etc.)

Siblings born together are connected by a shared structure:

1. A **horizontal "jig" line** connects all the multiple-birth siblings at their top centers
2. A **single vertical line** descends from the center of this jig to the parents' pair bond bar

The jig is positioned at the **vertical midpoint** between the children's connection points and the parents' horizontal bar.

Each individual child's line (from their top to the jig) remains solid for biological children and dashed for adopted children, even within a multiple birth group.

---

## 4. Generational Layout

### Vertical Organization

Generations are arranged in horizontal rows:
- **Older generations** appear **higher** on the diagram
- **Younger generations** appear **lower**

Ideally, all persons in the same generation share the same vertical level.

### Vertical Spacing

The recommended gap between generations is approximately **twice the height** of a person symbol. This provides adequate room for the pair bond connectors and child lines.

### Exceptions

In complex diagrams:
- A person with many descendants may be positioned lower than their siblings to accommodate their family branch
- Siblings may be staggered (alternating vertical positions) when horizontal space is limited
- Visual clarity takes priority over strict alignment

---

## 5. Horizontal Arrangement

### Birth Order

Siblings are arranged left-to-right from **oldest to youngest** when birth dates are known. When birth order is unknown, arrangement is at the user's discretion—there is no automatic ordering.

### Spacing

Recommended minimum spacing:
- Between siblings: 2× person width
- Between unrelated persons in the same row: 1.5× person width

**Proportional spacing**: Siblings with descendants receive more horizontal space to accommodate their family branches. The space allocation accounts for the width of the entire subtree below that person.

### Multiple Partnerships

When a person has had multiple partners (remarriage, serial relationships):
- Partners are arranged on the **opposite side** from the person's biological family
- Partners are ordered **earlier to later** from left to right
- The "anchor" person (more biologically connected to the index person) remains fixed; partners arrange around them
- Partners may share the same vertical level as the anchor, or be offset vertically if space requires

**Determining the anchor**: The person more closely related to the index person is the anchor.

**Example**: If the index person's sister has had three husbands, the sister is the anchor (she is biologically related to the index person). Her husbands appear to her left, ordered from first to most recent.

**Example**: If the index person's uncle has had three wives, the uncle is the anchor. His wives appear to his right, ordered from first to most recent.

---

## 6. Labels and Details

### Name Labels

Names appear adjacent to the person's symbol:
- **Default position**: To the right of the shape, aligned with the top
- **Offset**: Approximately 20% of the person's width to the right of the shape's edge
- **Alternative**: To the left, when placing it on the right would overlap with other elements
- **Nicknames**: Shown in parentheses after the given name, e.g., "Gerald (Jerry)"

Labels typically include:
- First line: Name
- Second line: Birth date (prefixed with "b.")

### Smart Label Placement (Collision Avoidance)

Labels should be automatically positioned to avoid overlaps and minimize diagram footprint:

1. **Collision threshold**: Define a threshold distance (e.g., PERSON_SPACING + half person width). If a neighbor exists within this threshold on the right, place the label on the left instead.

2. **Footprint optimization**: For the rightmost person in a row (no neighbor on right), prefer placing the label on the left if there's a neighbor on the left that is far enough to not cause collision but close enough to benefit from compaction (between 1× and 2× the collision threshold). This reduces the diagram's total width without causing overlaps.

3. **Above placement**: When a person has neighbors on both sides within tight spacing AND has parents, the label may be placed above the person—nestled in the corner between the person symbol and the child-of line. This leverages the empty space created by the line going up to parents.

4. **Default**: Labels appear to the right of the person when none of the above conditions apply.

### Date Abbreviations

| Abbreviation | Meaning |
|--------------|---------|
| b. | Birth date (on person) or Bonded date (on pair bond) |
| m. | Marriage date |
| s. | Separation date |
| d. | Death date (on person) or Divorce date (on pair bond) |
| a. | Adoption date |

Context determines meaning: "b." next to a person means birth; "b." on a pair bond means bonded.

---

## 7. Step-Relationships and Blended Families

### Step-Parents

Step-parent relationships are **implied**, not explicitly drawn. A step-child connects only to their biological parents. The step-parent relationship is evident from the step-parent's pair bond with the biological parent.

### Half-Siblings

Half-siblings share one biological parent:
- Each child connects to their own biological parents' pair bond
- The shared parent appears in multiple pair bonds
- Divorce/separation indicators show relationship history

### No Duplicate Persons

Each person appears **exactly once** on the diagram. Lines may cross to maintain this principle. There are no duplicate symbols connected by dotted lines.

---

## 8. Layout Guidelines

### Core Layout Principles

**These rules are mandatory and take priority over aesthetics:**

1. **Same-generation rule**: All people in the same generation appear on the same horizontal row, unless space constraints require an exception.

2. **Spouse proximity**: Partners in a pair bond must be positioned adjacent to each other horizontally. No other people should be placed between them.

3. **Children under parents**: Children should be positioned horizontally beneath their parents' pair bond bar. The diagram does NOT need to be symmetrical—prioritize placing children under their parents over centering the diagram.

4. **Unconnected people**: People with no family connections (friends, acquaintances) should be:
   - Placed on the same row as their associated family member if that association is known
   - Otherwise, positioned near the vertical middle on the perimeter of the family diagram
   - May be placed randomly if no association can be determined

### Spacing Summary

| Element Pair | Recommended Minimum Spacing |
|--------------|----------------------------|
| Between siblings | 2× person width |
| Between unrelated persons (same row) | 1.5× person width |
| Between generations (vertical) | 2× person height |
| Between pair bond partners | Minimal (adjacent positioning) |
| Between divorced/separated ex-spouses | 1.5× person width (treat as unrelated) |

### Visual Priorities

When arranging elements, prioritize in this order:
1. **Correctness**: Children under parents, spouses adjacent
2. **Clarity**: No overlapping elements
3. **Compactness**: Minimal wasted space
4. **Aesthetics**: Pleasing proportions (lowest priority)

**Note**: The diagram does NOT need to be symmetrical. Family structure takes priority over visual balance.

### Large Families

For families with many siblings (10+):
- A single horizontal row is preferred
- Staggering (alternating vertical positions) is permitted when horizontal space is limited
- Persons with descendants may be positioned lower to accommodate their branches

### Collision Resolution

When elements would overlap:
1. First: Expand horizontal spacing between siblings
2. Second: Move labels to alternate positions (left instead of right)
3. Third: Stagger vertical positions within a generation
4. Last resort: Accept some visual complexity in dense areas

---

## 9. Relationship Lines Summary

| Relationship | Line Style | Connection Points |
|--------------|------------|-------------------|
| Married pair bond | Solid | Bottom center of both persons to horizontal bar |
| Bonded (unmarried) pair bond | Dashed | Bottom center of both persons to horizontal bar |
| Biological child | Solid | Top center of child to parents' horizontal bar |
| Adopted child | Dashed | Top center of child to parents' horizontal bar |
| Multiple birth siblings | Solid | Children to horizontal jig, jig center to parents' bar |

---

## 10. Future Extensions

Future versions of this specification may include:

- **Clinical indicators**: Anxiety levels (jagged outlines), functioning shifts (bolt symbols), symptom tracking
- **Relationship patterns**: Conflict, distance, cutoff, fusion, triangles
- **Timeline features**: Temporal animation showing changes over time
- **Selective visibility**: Showing or hiding portions of the diagram by layer

---

## Glossary

| Term | Definition |
|------|------------|
| Index Person | The primary person(s) at the center of clinical focus, drawn with double outline |
| Generation | A horizontal tier of persons at the same generational level |
| Pair Bond | A romantic or reproductive partnership between two persons |
| Jig | The horizontal line connecting multiple-birth siblings before the vertical line to parents |
| Anchor | In multiple partnerships, the person who remains fixed while partners arrange around them |

---

## Example Diagrams

### Nuclear Family

```
      ┌───┐                  ○
      │   │                  │
      └───┘                  │
        │                    │
        └────┬────┬────┬─────┘
             │    │    │
           ┌───┐┌───┐  ○
           │   ││   │  
           └───┘└───┘
```

A married couple (square = male, circle = female) with three children (two sons, one daughter). The U-shaped connector with right angles forms the pair bond: vertical lines descend from each person's bottom center to the horizontal bar. Each child connects via a single vertical line from their top center up to the parents' horizontal bar.

### Divorced and Remarried

```
        ○              ┌───┐                ○
        │              │   │                │
        │              └───┘                │
        │                │                  │
        └────//──────────┴───────┬─────┬────┘
                                 │     │
                               ┌───┐   ○
                               │   │   
                               └───┘
```

A man (center) with two pair bonds: divorced from his first wife (left, indicated by double slashes on the horizontal bar) and married to his second wife (right). The U-shape connects all three, with the divorce indicator on the left segment. Each child connects via a single vertical line to the parents' horizontal bar.

---

## 11. Implementation Notes

### HTML5/SVG Renderer (Training App)

The training app includes an HTML5/SVG renderer for visualizing PDP (Pending Data Pool) extractions. This renderer implements a subset of the full specification for quick visualization during SARF coding.

**Endpoint**: `/training/diagrams/render/<statement_id>`

**Supported Features**:
- Person symbols (unknown gender shown as rounded rectangles with "?")
- Name labels positioned to the right of each person
- ID labels for debugging (negative IDs indicate PDP items)
- Pair bond U-shapes with solid/dashed lines
- Child connections (vertical/diagonal lines to parent bars)
- Dark/light mode adaptation via CSS custom properties

**Not Yet Implemented**:
- Gender-specific shapes (requires gender field in PDP schema)
- Deceased indicators (X through shape)
- Primary/index person double outline
- Separation/divorce slashes on pair bonds
- Multiple birth jig lines
- Age display inside person symbols

**CSS Color Variables**:
The renderer uses CSS custom properties for theme adaptation:
- `--color-fg-default`: Primary stroke and text color
- `--color-fg-muted`: Secondary text (IDs, labels)
- `--color-canvas-default`: Background color

**Layout Algorithm**:
1. Determine generations via parent-child relationships
2. Assign root generation (0) to people without parents
3. Assign spouses the same generation as their partner
4. Position people horizontally within each generation using "family units":
   - **Couples take priority over sibling groups**: When a sibling from one family marries a sibling from another family, the couple is positioned together
   - A "family unit" = left-siblings + couple + right-siblings
   - Left siblings are from the spouse whose parents are further left
   - Right siblings are from the spouse whose parents are further right
   - Unmarried siblings without couple connections are positioned separately
5. **Position parents to encompass children** (canopy effect):
   - When a couple has children, the parents' X positions should be adjusted outward so that children fall between them
   - Add padding (e.g., half of PERSON_SPACING) beyond the outermost children's positions
   - This creates a "canopy" effect by expanding the couple's positions, NOT by extending lines
   - The U-shape pair bond naturally becomes wider because the parents are further apart
   - This breaks the grid-like appearance and emphasizes the parent-child hierarchy
   - **Exceptions**: Do NOT apply canopy positioning when:
     - There isn't enough horizontal space (would cause overlap with adjacent elements)
     - There are too many children to reasonably fit under the parents
   - In exception cases, children may extend beyond the parents' positions
6. **Compaction pass** (footprint optimization):
   - After initial positioning, compact each generation leftward to minimize diagram width
   - Shift entire generations left while respecting parent-child alignment constraints
   - Reduce all gaps to minimum required spacing (PERSON_SPACING)
   - Respect divorced/separated couple extra spacing (1.5× standard)
   - Re-run canopy adjustment after compaction to ensure parents still encompass children
7. **Unconnected people on perimeter**: People with no family connections (no parents, no spouse, no children) are positioned AFTER compaction on the right edge of the diagram at the vertical middle. Position them with a small gap (1.5× PERSON_SPACING) from the rightmost connected person.
8. **Draw pair bond U-shape**:
   - The horizontal bar goes strictly from person A's X to person B's X (per Section 2)
   - Vertical lines descend from each partner's bottom center to the horizontal bar
   - NO extensions beyond the couple's positions - the canopy effect comes from positioning, not line extension
9. **Connect children to parent pair bonds**:
   - Children attach to the horizontal bar between the parents
   - Vertical line if child is within couple span, diagonal to nearest corner if outside

---

*This specification describes the Bowen family diagram as implemented in the Family Diagram application.*
