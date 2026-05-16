# 2026-05-05 — FD-325/326 returning-user coach: behavioral validation

## What changed

Conversational-flow prompt (`_CONVERSATION_FLOW_CORE` + Opus/Gemini addenda) rewritten so returning-user awareness and the current-events/intake balance are expressed as guidelines, not rules. Committed family data is now summarized into the system instruction so the coach references known people by name and does not re-ask answered structural questions. A dedicated 4-dimension LLM judge (`fd326_eval`) replaces `QualityEvaluator` entropy for measuring coach quality.

## Why

Returning users were getting re-interrogated on family structure already on file, or the coach followed the user so passively that intake never progressed. Rule/turn-count phrasing produces a robotic coach — the explicit FD-326 anti-goal.

## Psychological rationale

- **Returning-user awareness**: a real coach who has met you before does not re-ask your sister's name; they say "Have you talked to Sarah?" Naming known people is the behavioral signal that the relationship has continuity.
- **Stay-present under stonewalling**: when a client cycles ("I dunno", "it is what it is"), a competent coach stays present and keeps gently probing rather than mechanically switching to a data-collection agenda. Pivoting on a stonewalling client reads as the coach abandoning them to run a checklist. Accepted as correct behavior (Patrick, 2026-05-16) — stonewalling is not a solvable problem.
- **Entropy is the wrong metric here**: a coach doing consistent acknowledge+question turns is behaving correctly; response-type entropy penalizes that consistency. Entropy measures synthetic-*client* realism, not coach quality. Reusing it produced false negatives.

## Results (3× e2e smoke, 6 conversations/run, Opus + Gemini Flash)

- 17/18 judge verdicts PASS.
- Pattern (a) opening-current-events: 6/6, stable both models.
- Pattern (c) long-session, returning user, intake far from complete: 6/6, stable both models — coach engages current events and opportunistically deepens one missing category rather than surfacing many shallowly.
- Pattern (b) shallow-cycling/stonewalling: Opus 3/3 PASS; Gemini 1–2/3. Every Gemini failure = judge flags the stock phrase "Sounds like" as a therapy cliché (`no_theory_pitch`); `no_premature_pivot=True` throughout. Behavior is correct (stays present); the failure is judge variance on a stock phrase, not a coaching defect.

## Open / watch

- Gemini's "Sounds like" reflex trips the cliché dimension intermittently. Not fixed (out of FD-326 scope per the pattern-(b) accept decision); note for future Gemini-addendum tuning if the cliché judge is kept strict.
