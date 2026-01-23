# Plan: Fix SARF Line Graph in Focused Mode

## Context
The SARF graph in Learn tab should visualize **trajectory accumulation** - how Symptom, Anxiety, and Functioning shift up/down over time as step line graphs. This supports pattern intelligence (see PATTERN_INTELLIGENCE_VISION.md) and addresses the core problem from LEARN_TAB_EVALUATION.md: "Raw timeline data is overwhelming. Events stack on single pixels."

**Current state**: The graph draws Symptom and Anxiety as step lines, but:
1. Cumulative data uses integer `year` while focused mode uses `yearFrac` → lines cluster together
2. Functioning is tracked but not rendered
3. In focused mode, the trajectory isn't visible because lines don't spread

## Solution

### 1. Add `yearFrac` to cumulative data

**File**: `familydiagram/pkdiagram/personal/sarfgraphmodel.py`

In `_calculateCumulative()`, add `yearFrac` from each event:

```python
self._cumulative.append({
    "year": event["year"],
    "yearFrac": event["yearFrac"],  # ADD
    "symptom": cs,
    "anxiety": ca,
    "functioning": cf,
    "relationship": event.get("relationship"),
})
```

### 2. Update Canvas to draw lines using `yearFrac`

**File**: `familydiagram/pkdiagram/resources/qml/Personal/LearnView.qml`

In `graphCanvas.onPaint`:

**a) Use `yearFrac` for x-positioning:**
```qml
// Use yearFrac for precise positioning
var xVal = filteredData[i].yearFrac
ctx.lineTo(xPos(xVal), yPosMini(filteredData[i].symptom))
```

**b) Draw all four variables:**
- **Symptom (red)**: Step line using `filteredData[i].symptom`
- **Anxiety (green)**: Step line using `filteredData[i].anxiety`
- **Functioning (grey)**: Step line using `filteredData[i].functioning`
- **Relationship (blue)**: Vertical line at event's x-position; if event has date range (end date), draw as shaded span between start and end yearFrac

**c) Filter using yearFrac in focused mode:**
```qml
if (cumulative[k].yearFrac < drawYearStart) {
    prevSymptom = cumulative[k].symptom
    // ...track boundary values
} else if (cumulative[k].yearFrac <= drawYearEnd) {
    filteredData.push(cumulative[k])
}
```

### 3. Event dots remain as clickable markers
Dots stay spread evenly by index so users can click them. The step lines show the trajectory; dots show interaction points.

## Files to Modify

| File | Changes |
|------|---------|
| `sarfgraphmodel.py` | Add `yearFrac` to cumulative entries |
| `LearnView.qml` | Use `yearFrac` for line x-positions; draw S/A/F as step lines; draw R as vertical lines (or spans for date ranges); filter by `yearFrac` |

## Verification

1. Launch Personal app with a diagram containing SARF events
2. Learn tab: See S (red), A (green), F (grey) step lines moving up/down
3. Relationship shifts: Blue vertical lines (or shaded spans for date ranges)
4. Focus a vignette: Lines spread across graph, showing trajectory
5. Events on same day: Single x-position with vertical steps
6. Navigate between vignettes: Lines animate smoothly
