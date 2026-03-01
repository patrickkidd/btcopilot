# Server API & Data Model Analysis

**Date:** 2026-02-20

## Data Model Summary

### DiagramData (btcopilot/schema.py)
Top-level container with 40+ fields. Serialized as pickle blob in `diagrams.data`.

### Entity Models
- **Person**: id, name, last_name, gender, parents (PairBond ID), confidence
- **Event**: id, kind (EventKind enum), person, spouse, child, description, dateTime, dateCertainty, symptom/anxiety/functioning (VariableShift), relationship (RelationshipKind), relationshipTargets, relationshipTriangles, confidence
- **PairBond**: id, person_a, person_b, confidence
- **PDP**: people[], events[], pair_bonds[] (all with negative IDs)
- **PDPDeltas**: people[], events[], pair_bonds[], delete[] (per-statement change set)

### ID Convention
- Positive integers (1+): committed diagram items
- Negative integers (-1, -2, ...): uncommitted PDP items
- IDs 1, 2 reserved for chat participants (User, Assistant)
- Single namespace across Person, Event, PairBond

## API Endpoints

### Pro App (`/v1` prefix, pickle transport)
| Endpoint | Purpose |
|----------|---------|
| GET/POST `/v1/diagrams` | List, create |
| GET/PATCH/PUT/DELETE `/v1/diagrams/{id}` | Fetch, update (version check), delete |
| POST `/v1/arrange` | Auto-layout diagram |
| POST `/v1/copilot/chat` | Pro app copilot |
| POST/GET/DELETE `/v1/sessions` | Auth |
| Various `/v1/licenses/*`, `/v1/users/*` | Licensing, user management |

### Personal App (JSON transport, base64 for binary)
| Endpoint | Purpose |
|----------|---------|
| POST/GET `/diagrams/` | Create, list |
| GET/PUT `/diagrams/{id}` | Fetch (with data), update (version check → 409 on conflict) |
| POST `/diagrams/{id}/import-text` | Journal text → PDPDeltas |
| POST `/diagrams/{id}/clusters` | Detect event clusters |
| POST/GET `/discussions/` | Create (with optional first statement), list |
| POST `/discussions/{id}/statements` | Send message + get AI response + PDP |

## Validation Layer (btcopilot/pdp.py)

`validate_pdp_deltas()` checks:
1. ID collisions across entity types
2. Duplicate dyads in pair_bonds
3. All negative IDs exist in PDP, all positive IDs exist in committed diagram
4. isPairBond() events (except Moved/Birth/Adopted) require spouse
5. person_a and person_b non-null on pair bonds
6. Person.parents references valid PairBond
7. Event relationshipTriangles reference valid people

Raises `PDPValidationError` with full error list.

## Data Integrity Issues

### Silent ID Reassignment
- `reassign_delta_ids()` (pdp.py:38-122) fixes LLM ID collisions without user notification
- User may see different IDs in UI than LLM response

### Orphaned PairBond Cleanup
- `cleanup_pair_bonds()` removes pair bonds with missing person references
- Aggressively prunes pair bonds not referenced by Person.parents (but events may reference them)
- Decision logged 2026-02-14: fix to keep pair bonds referenced by events

### Duplicate Dyad Collapse
- On commit, if PDP pair bond dyad matches committed pair bond, ID mapping reuses existing
- Remarriage scenario: two separate pair bonds with same dyad collapse into one

## Concurrency Model

Optimistic locking with functional mutations:
1. Client fetches diagram with version
2. Client applies mutation locally
3. PUT with `expected_version`
4. 200 → success; 409 → server returns latest, client replays mutation, retries

Domain partitioning prevents merge conflicts — but Pro app violates this (FR-2 issue).

## Key Files
| Component | File |
|-----------|------|
| Schema + commit logic | `btcopilot/schema.py` |
| Validation + extraction | `btcopilot/pdp.py` |
| Diagram model | `btcopilot/pro/models/diagram.py` |
| Pro routes | `btcopilot/pro/routes.py` |
| Personal diagram routes | `btcopilot/personal/routes/diagrams.py` |
| Personal discussion routes | `btcopilot/personal/routes/discussions.py` |
| Data sync spec | `familydiagram/doc/specs/DATA_SYNC_FLOW.md` |
| Data model spec | `btcopilot/doc/specs/DATA_MODEL.md` |
