# Diagram Viewing & Data Sync Analysis

**Date:** 2026-02-20

## Pro App Diagram Loading
- Entry point: `familydiagram/pkdiagram/scene/scene.py:1049` — `Scene.read(data, byId)`
- Format: Python pickle serialized DiagramData (binary blob)
- Two-phase loading: Phase 1 creates objects with IDs, Phase 2 resolves cross-references
- Critical flag: `isInitializing=True` during bulk add (defers pair-bond validation)

## Known Crashes

### CRASH: Version Conflict Pickle TypeError
```
TypeError: a bytes-like object is required, not 'DiagramData'
File: familydiagram/pkdiagram/server_types.py:295
```
- `getDiagramData()` expects `self.data` to be bytes, receives DiagramData object
- Trigger: Version conflict dialog → user clicks action → save fails

### CRASH: emotionalunit.py on PDP Accept
```
AttributeError: 'NoneType' object has no attribute 'id'
File: familydiagram/pkdiagram/scene/emotionalunit.py:34
```
- Trigger: Adding PDP item with parent references
- Chain: scene.py:433 `_do_addItem()` → `item.parents().emotionalUnit().update()`
- Root cause: Layer `_layer` is None

### CRASH: _log Not Defined
- Trigger: Re-opening diagram after deleting views with people
- Related to layer reference cleanup

## Data Sync Issues

### FR-2 Violation (DATA LOSS RISK)
- Pro app `applyChange` callback replaces entire DiagramData on conflict retry
- Destroys PDP and cluster data from Personal app
- File: `familydiagram/pkdiagram/server_types.py`
- Fix: Pro app must merge scene fields into incoming DiagramData, not replace

### Chat Response Race Condition
- `_sendStatement()` is async; server responds with updated PDP
- If local mutation happens between send/receive, `setDiagramData()` overwrites it
- Fix: Sequence numbers or merge strategy for PDP deltas

### Undo Does Not Persist
- `HandlePDPItem` restores snapshot locally via `setDiagramData()`
- Does NOT push to server — undo lost on app restart

### Deserialization Duplication
- Logic duplicated between server (`pro/models/diagram.py:83-91`) and client (`server_types.py:294-300`)
- Must stay in sync manually

## Domain Partitioning
| Partition | Authoritative | Fields |
|-----------|---------------|--------|
| Scene collections | Pro (or Personal standalone) | people, events, pair_bonds, emotions, layers |
| PDP | Personal | pdp |
| Clusters | Personal | clusters, clusterCacheKey |
| Metadata | Both | lastItemId, version, name |

## Event Cluster Detection
- File: `btcopilot/personal/clusters.py:98-140`
- Method: LLM-based (Gemini 2.0 Flash) with SHA256 cache key
- Patterns detected: anxiety_cascade, triangle_activation, conflict_resolution, reciprocal_disturbance, functioning_gain, work_family_spillover
- Caches per diagram in `clusters_{diagramId}.json`
- Works but results are inconsistent across calls (LLM variability)

## Key Files
| Component | File |
|-----------|------|
| Scene loading | `familydiagram/pkdiagram/scene/scene.py:1049` |
| Diagram save | `familydiagram/pkdiagram/server_types.py:205-292` |
| Server diagram model | `btcopilot/pro/models/diagram.py` |
| Data sync spec | `familydiagram/doc/specs/DATA_SYNC_FLOW.md` |
| Cluster detection | `btcopilot/personal/clusters.py` |
| Personal app controller | `familydiagram/pkdiagram/personal/personalappcontroller.py` |
