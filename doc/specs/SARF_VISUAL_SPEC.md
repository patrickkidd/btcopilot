# SARF Visual Language Spec

Authoritative source: `training/templates/components/sarf_editor.html`

All views rendering SARF data (SARF editor, IRR review, calibration cards, timeline diff) must follow these rules.

## Badge Format

Each SARF variable is a `<span class="shift-indicator {color-class}">{letter}:{value}</span>`.

| Variable | Letter | Values | Color class |
|----------|--------|--------|-------------|
| Symptom | S | up, down, same | `shift-{value}` |
| Anxiety | A | up, down, same | `shift-{value}` |
| Functioning | F | up, down, same | `shift-functioning-{value}` |
| Relationship | R | distance, conflict, overfunctioning, etc. | `shift-relationship` (always) |

Functioning uses `shift-functioning-up`/`shift-functioning-down` because its clinical semantics are inverted: functioning up = good (green), functioning down = bad (red).

**Badge order**: S, A, F, R. Spacing: `ml-1` between badges.

## Colors

Defined in `sarf_editor.html` (overrides base.html):

| Class | Color | Meaning |
|-------|-------|---------|
| `shift-up` | `#e74c3c` (red) | Bad — symptom/anxiety increased |
| `shift-down` | `#27ae60` (green) | Good — symptom/anxiety decreased |
| `shift-same` | `#f0ad4e` (yellow) | Neutral — no change |
| `shift-functioning-up` | `#27ae60` (green) | Good — functioning improved |
| `shift-functioning-down` | `#e74c3c` (red) | Bad — functioning declined |
| `shift-relationship` | `var(--color-attention-emphasis)` | Amber — relationship pattern |

White text on all badges.

## Dates

Display format: `mm/dd/yyyy`. Convert from ISO `yyyy-mm-dd` via `formatDateDisplay()` (JS) or Jinja filter.

Jinja equivalent for server-rendered dates:
```jinja
{{ date[5:7] }}/{{ date[8:10] }}/{{ date[:4] }}
```

## Disagreement Badges (Diff Views)

When two coders disagree on a SARF field, show paired badges with a red border:

```html
<span style="display: inline-flex; gap: 1px; border: 2px solid var(--color-danger-emphasis); border-radius: 4px;">
    <span class="shift-indicator {class_a}" style="border-radius: 2px 0 0 2px; margin: 0;">{L}:{val_a or '-'}</span>
    <span class="shift-indicator {class_b}" style="border-radius: 0 2px 2px 0; margin: 0;">{L}:{val_b or '-'}</span>
</span>
```

## Consumers

| View | File | Status |
|------|------|--------|
| SARF Editor | `components/sarf_editor.html` | Authoritative |
| Calibration Card | `components/calibration_card.html` | Missing F inversion |
| IRR Review | `training/irr_review.html` | Missing F inversion |
| Timeline Diff | `training/timeline.html` | Compliant (stoplight colors, F inversion, mm/dd/yyyy) |
