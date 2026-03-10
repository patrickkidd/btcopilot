> **Archived 2026-03-10.** Deferred post-MVP. Plan tab feature not yet prioritized. Kept for historical reference.

# Plan Tab Vision: Insights for Family Diagram - Personal

## Overview

The Plan tab helps users discover patterns in their family relationships and track how those patterns affect their lives. It surfaces insights the user might not see on their own.

## Core Concept

The app already collects:
- **Timeline events** — relationship shifts, family gatherings, conflicts, distances
- **Chat conversations** — where users describe their experiences and symptoms

The Plan tab synthesizes this into:
- **Observations** — "You reported sleep trouble during the holiday visit"
- **Patterns** — "Sleep disruption has occurred 3 times during high-stress family events"
- **Hypotheses** — "Your symptoms may be connected to anxiety around [relationship]"
- **Outcomes** — Track whether a hypothesis holds up over time

## User Experience

### Observations (What you've reported)

Simple list of key observations extracted from chat:
- "Dec 26: Sleep disruption during family visit"
- "Dec 28: Noted [person] interactions were stressful"
- "Jan 2: Sleep normalized after returning home"

User can add observations manually or they're extracted from chat.

### Patterns (What we're noticing)

When the app detects correlations:
> "We've noticed that sleep trouble tends to occur during visits with extended family. This has happened 3 times in your history."

Patterns are surfaced with:
- How many times observed
- Confidence level (tentative vs. established)
- Option to dismiss if not meaningful

### Hypotheses (Ideas to track)

Proposed connections for the user to consider:
> **Hypothesis:** Your symptoms last longer after high-stress family events than after routine stress.
>
> **What to watch for:** Track recovery time after your next family visit vs. after work stress.
>
> **Status:** Tracking

User can:
- Accept (start tracking)
- Dismiss (not relevant)
- Add their own hypothesis

### Outcomes (What we've learned)

When enough data accumulates:
> **Supported:** Post-visit recovery takes 5-7 days (observed 3 times)
>
> **Refuted:** Originally thought morning coffee affected sleep — testing showed no correlation

## Connection to Bowen Theory

The app's reference knowledge includes Bowen family systems concepts:
- Anxiety transmission in relationship systems
- Triangles and conflict patterns
- Differentiation and emotional reactivity
- Cutoff and distance patterns

When patterns emerge, the app can connect them to Bowen concepts:
> "This pattern is consistent with Bowen's concept of 'anxiety transmission' — stress in one part of a family system can affect other members, even at a distance."

This provides educational context without requiring the user to know the theory.

## Example: Insomnia Use Case

**User's situation:**
- Chronic sleep issues
- Uses app to track family relationships and symptoms
- Notices sleep problems during certain family interactions

**What the Plan tab shows:**

```
OBSERVATIONS
• Dec 26: "Didn't sleep well for 3 nights during family visit"
• Dec 28: "Some family dynamics were stressful"
• Jan 3: "Sleep back to normal"

PATTERNS
⚡ Sleep disruption correlates with extended family visits (3 occurrences)
   Confidence: Moderate

HYPOTHESES
📊 Tracking: Post-visit recovery time is longer than typical stress recovery
   Prediction: 5+ days to normalize after family events

💡 Proposed: Your inflammatory sensitivity may amplify relationship stress effects
   Based on: Your health history + pattern timing

OUTCOMES
✓ Confirmed: Sleep normalizes within 5-7 days post-visit (3 observations)
```

## Future Enhancements

- Integration with health apps (sleep trackers) for automatic observation capture
- Export insights to external tools for deeper analysis
- Sharing anonymized patterns for research (with consent)

---

## Architecture Reference

See [PLAN_TAB_ARCHITECTURE.md](PLAN_TAB_ARCHITECTURE.md) for underlying technical principles including decision traces, the two-clock model, and implementation approach.
