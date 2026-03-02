# Auto-Arrange Feature Analysis

**Date:** 2026-02-20

## Current State: Non-Functional (LLM-Based Prototype)

The auto-arrange feature exists as a Gemini 2.5 Flash-powered layout suggestion system. It is not a deterministic algorithm and is unreliable for real diagrams.

## Architecture

1. User selects people on diagram
2. Frontend serializes selected people with layout info (positions, sizes, relationships)
3. POSTs to `/arrange` endpoint
4. Backend sends Gemini structured output request with layout rules prompt
5. Gemini returns suggested positions
6. Frontend updates positions via undoable commands

### Key Files
- Frontend trigger: `familydiagram/pkdiagram/documentview/documentcontroller.py:869-940`
- Backend route: `btcopilot/pro/routes.py:923-1032`
- Data structures: `btcopilot/arrange.py` (58 lines — models only, no algorithm)
- Event-based positioning: `familydiagram/pkdiagram/views/eventform.py:837-919`

## What Works
- Gemini integration with JSON schema (`gemini_structured()`)
- Frontend undo/redo integration
- Simple 3-person positioning during Birth event creation (`_arrange_parents()`)

## Why It Fails
- Gemini can't reliably execute multi-step constraint satisfaction
- LLM struggles with: graph traversal, numerical collision detection, consistency across large diagrams
- Prompt is ~1100 lines, too verbose, uses fuzzy language
- No fallback on failure — user sees Flask 500 or silent error
- `_onError()` callback only logs to console (documentcontroller.py:927)
- No validation that output matches PersonDelta schema

## What Functional Auto-Arrange Needs

### MVP Algorithm Requirements
1. **Generation detection**: Parse parent-child graph to assign Y-coordinates per generation
2. **Horizontal spacing**: Group siblings, position within generation, birth-order sorting
3. **Overlap prevention**: 2D bounding box collision detection and resolution
4. **Partner adjacency**: Horizontally adjacent at same Y
5. **Parent-child centering**: Children centered below parents

### Effort Estimate: LARGE (2-3 weeks)
| Component | Effort |
|-----------|--------|
| Replace Gemini with deterministic algorithm | 1-2 weeks |
| Generation detection (DFS) | 2-3 days |
| Overlap detection/resolution | 3-4 days |
| Horizontal spacing | 2-3 days |
| Error handling + UI feedback | 1 day |
| Test coverage | 3-5 days |

### Possible Simplification
Instead of full constraint solver, implement just:
1. Generational Y-alignment (consistent Y per generation)
2. Basic horizontal spacing (left-to-right sibling ordering)
3. Partner adjacency (horizontal neighbors)

This would get ~70% of the value in ~1 week and handle the MVP cases (3-generation families with <20 people).

## Bugs
- No error handling in arrange route (routes.py:1032) — Gemini failure = 500
- Frontend `_onError()` is silent (documentcontroller.py:927)
- No test coverage for `/arrange` endpoint or multi-person arrangement
