# Personal App Beta Readiness Analysis

**Date:** 2026-02-20

## Overall Assessment: 40% Beta-Ready

Core AI chat works. Visualization and guidance layers are missing or incomplete. A first-time user will be confused.

## Chat Flow: Functional

### What Works
- Clean iOS-style chat bubbles (blue user, gray AI)
- Message history display
- Text input expands with content
- Copy to clipboard on long-press
- Text-to-speech with play/pause
- Journal note import (paste >20 chars triggers import dialog)
- PDP drawer integration (signals for accept/reject/edit)

### Missing
- No loading indicator while awaiting AI response
- No empty state guidance ("no chat" label is generic, no action button)
- No conversation titles (defaults to "Discussion")
- No scroll-to-bottom on submit
- Chat window height not optimized

### Key Files
- Chat UI: `familydiagram/pkdiagram/resources/qml/Personal/DiscussView.qml`
- Chat orchestration: `btcopilot/personal/chat.py`
- HTTP routes: `btcopilot/personal/routes/discussions.py`

## PDP Drawer: Built, UX Gaps

### What Works
- Bottom drawer with SwipeView + PageIndicator
- PDPEventCard shows event kind badges with color coding
- PDPPersonCard shows name, last name, parents
- SARF variables show directional coloring (green up, red down, gray same)
- Accept/Reject buttons
- Tutorial overlay (swipe left/right) on 2+ items
- Edit overlay for inline field modification

### Missing
- No SARF variable legend (user sees colored boxes with no explanation)
- Tutorial only shows on 2+ items
- No timeline context (just a stack of cards, no chronology)
- No insights ("Shift events detected: 3" is all guidance given)
- Edit overlay is a modal-within-drawer (confusing nesting)

### Key Files
- `familydiagram/pkdiagram/resources/qml/Personal/PDPSheet.qml`
- `familydiagram/pkdiagram/resources/qml/Personal/PDPEventCard.qml`
- `familydiagram/pkdiagram/resources/qml/Personal/PDPPersonCard.qml`

## Timeline/Cluster Visualization: Partially Implemented

### What Works
- Mini timeline graph showing event distribution
- Cluster detection with pattern labels (Anxiety Cascade, Triangle Activation, etc.)
- Hero animation for cluster focus
- Dominant variable tracking
- Zoom/pan controls
- Backend: SARFGraphModel builds event data, ClusterModel detects clusters

### Issues
- Cluster graph text overlaps (makes timeline unreadable)
- No selection indication when clicking event
- Lots of empty space to right of clusters
- SARF variable display confusing (should show "Symptom: Up" not raw coding)

### Key Files
- `familydiagram/pkdiagram/resources/qml/Personal/LearnView.qml`
- `familydiagram/pkdiagram/personal/sarfgraphmodel.py`
- `familydiagram/pkdiagram/personal/clustermodel.py`

## PlanView: Empty Placeholder

- Shows "Guidance, action items go here"
- No content generation
- No action items based on patterns
- Third tab is dead weight for beta testers

### Key File
- `familydiagram/pkdiagram/resources/qml/Personal/PlanView.qml`

## First-Time User Experience: Undefined

A new user sees:
1. Empty chat view with no guidance
2. Three tabs (Discuss, Learn, Plan) with no explanation
3. After chatting: PDP drawer with colored badges and S/A/F abbreviations (no legend)
4. Learn tab with timeline (no explanation of clusters or patterns)
5. Plan tab is empty

### Critical UX Gaps for Beta
| Gap | Severity |
|-----|----------|
| No onboarding or first-use guidance | Critical |
| SARF variable meanings undefined for users | High |
| Timeline patterns unexplained | High |
| PlanView empty | High |
| No sending indicator | Medium |
| No conversation titles | Low |

## Recommendations for Beta
1. Add welcome/onboarding overlay explaining the three tabs
2. Add SARF variable legend (S=Symptom, A=Anxiety, F=Functioning, R=Relationship with directional arrows)
3. Fix cluster text overlap (highest-impact timeline fix)
4. Either populate PlanView with generated insights or hide the tab
5. Add loading spinner during AI response
6. Rename User→Client, Assistant→Coach
