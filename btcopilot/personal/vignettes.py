import hashlib
import json
import logging
from dataclasses import dataclass, field

from btcopilot.extensions import llm, LLMFunction
from btcopilot.schema import (
    Event,
    Vignette,
    VignettePattern,
    VignetteResult,
    asdict,
)

_log = logging.getLogger(__name__)

VIGNETTE_PROMPT = """You are analyzing a family therapy case timeline to identify clinically meaningful episodes (vignettes).

## SARF Theory Context

Four variables track family system dynamics:
- **S (Symptom)**: Physical/emotional dysfunction (sleep, mood, physical illness) - up=worsening, down=improving
- **A (Anxiety)**: Reactivity levels, "infectious" between people - up=more reactive
- **R (Relationship)**: Patterns like conflict, distance, toward, triangles (inside/outside positions)
- **F (Functioning)**: Differentiation of self - up=toward solid self, down=toward pseudo-self

**Clinical Hypothesis**: "S is modulated by R via A, and F is the clinical independent variable"

## Common SARF Patterns

- **anxiety_cascade**: A↑ → S↑ (anxiety leads to sleep/physical symptoms)
- **triangle_activation**: R: triangle → A↑ (positioning in triangles raises anxiety)
- **conflict_resolution**: R: conflict → processing → R: toward
- **reciprocal_disturbance**: One person's A/S triggers partner's A/S
- **functioning_gain**: Stressor → emotional processing → F↑
- **work_family_spillover**: Work A↑ cascades into family dynamics

## Events (chronological)

{events_json}

## Task

Group these events into vignettes. Events belong in the same vignette when they:
1. Occur within a short time period (typically 1-15 days, up to 3 weeks for major life events)
2. Show SARF interaction patterns (cascades, reciprocal effects)
3. Involve the same relational dynamics or stressor
4. Form a narrative arc (trigger → escalation → peak → processing → resolution)

**Vignette sizing guidelines**:
- Short (1-6 days): Single incident or brief cascade
- Medium (1-2 weeks): Conflict-resolution arc
- Long (2-3 weeks): Major life event with processing
- Isolated events (1 day) can be their own vignette if significant

**Requirements**:
- Every event MUST be assigned to exactly one vignette
- Use abstract titles (NO person names) - e.g., "Work Stress Cascade" not "Patrick's Work Stress"
- Set `pattern` to the primary SARF pattern if one is clearly dominant
- Set `dominantVariable` to "S", "A", "R", or "F" based on which is most prominent

Return a JSON object with a `vignettes` array."""


@dataclass
class VignetteListResponse:
    vignettes: list[Vignette] = field(default_factory=list)


def _enumValue(val):
    """Extract enum value or return as-is for non-enum types."""
    return val.value if hasattr(val, "value") else val


def computeCacheKey(events: list[Event]) -> str:
    event_data = []
    for e in events:
        event_data.append(
            {
                "id": e.id,
                "dateTime": e.dateTime,
                "symptom": _enumValue(e.symptom) if e.symptom else None,
                "anxiety": _enumValue(e.anxiety) if e.anxiety else None,
                "relationship": _enumValue(e.relationship) if e.relationship else None,
                "functioning": _enumValue(e.functioning) if e.functioning else None,
            }
        )
    content = json.dumps(event_data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def detectVignettes(events: list[Event]) -> VignetteResult:
    if not events:
        return VignetteResult(vignettes=[], cacheKey="empty")

    cacheKey = computeCacheKey(events)

    events_for_prompt = []
    for e in events:
        event_dict = {
            "id": e.id,
            "date": e.dateTime,
            "description": e.description or "",
        }
        if e.symptom:
            event_dict["symptom"] = _enumValue(e.symptom)
        if e.anxiety:
            event_dict["anxiety"] = _enumValue(e.anxiety)
        if e.relationship:
            event_dict["relationship"] = _enumValue(e.relationship)
        if e.functioning:
            event_dict["functioning"] = _enumValue(e.functioning)
        if e.notes:
            event_dict["notes"] = e.notes
        events_for_prompt.append(event_dict)

    events_json = json.dumps(events_for_prompt, indent=2)
    prompt = VIGNETTE_PROMPT.format(events_json=events_json)

    _log.info(f"Detecting vignettes for {len(events)} events")

    response = llm.submit_one(
        LLMFunction.Vignette,
        prompt,
        response_format=VignetteListResponse,
    )

    vignettes = response.vignettes if response else []

    for v in vignettes:
        event_dates = [e.dateTime for e in events if e.id in v.eventIds and e.dateTime]
        if event_dates:
            v.startDate = min(event_dates)
            v.endDate = max(event_dates)

    _log.info(f"Detected {len(vignettes)} vignettes")

    return VignetteResult(vignettes=vignettes, cacheKey=cacheKey)
