# 2026-05-05 — FD-325/326 returning-user coach: behavioral validation

## What changed

Conversational-flow prompt (`_CONVERSATION_FLOW_CORE` + Opus/Gemini addenda) rewritten so returning-user awareness and the current-events/intake balance are expressed as guidelines, not rules. Committed family data is now summarized into the system instruction so the coach references known people by name and does not re-ask answered structural questions. A dedicated 4-dimension LLM judge (`fd326_eval`) replaces `QualityEvaluator` entropy for measuring coach quality.

## Why

Returning users were getting re-interrogated on family structure already on file, or the coach followed the user so passively that intake never progressed. Rule/turn-count phrasing produces a robotic coach — the explicit FD-326 anti-goal.

## Psychological rationale

- **Returning-user awareness**: a real coach who has met you before does not re-ask your sister's name; they say "Have you talked to Sarah?" Naming known people is the behavioral signal that the relationship has continuity.
- **Stay-present under stonewalling**: when a client cycles ("I dunno", "it is what it is"), a competent coach stays present and keeps gently probing rather than mechanically switching to a data-collection agenda. Pivoting on a stonewalling client reads as the coach abandoning them to run a checklist. On the valid harness, Opus does this correctly; Gemini does not reliably (see Results).
- **Entropy is the wrong metric here**: a coach doing consistent acknowledge+question turns is behaving correctly; response-type entropy penalizes that consistency. Entropy measures synthetic-*client* realism, not coach quality. Reusing it produced false negatives.

## Harness bug — first results RETRACTED

The first multi-turn results (17/18; "(b)-Gemini opener tic"; "stay-present accepted"; a measured/reverted prompt-reframe; "skip") are void. Root cause: `ask()` does not persist turns — it relies on the caller committing each turn (the production HTTP route does, per request). The REPL and the smoke's `_multi_turn` looped `ask()` with no commit between turns, so the coach had **no within-session memory across turns**. Every multi-turn (b)/(c) conclusion from that run is invalid. Single-turn (a) and name-usage (committed_state, re-derived each call) were unaffected.

Fixed: commit each turn in both harnesses; also switched Claude `thinking` enabled→adaptive (Anthropic states adaptive improves performance — changes model behavior under test).

## Results — valid harness + adaptive thinking (3× e2e, 6/run): 15/18

- (a) opening-current-events: Opus + Gemini 3/3 — solid.
- (c) long-session, returning user, intake far from complete: Opus + Gemini 3/3 — solid; engages current events and deepens one missing category rather than surfacing many shallowly.
- (b) shallow-cycling/stonewalling: **Opus 3/3 PASS; Gemini 0/3.** Two failures canned-empathy clichés; one the cardinal failure — Gemini pivoted to family-history interrogation while the user was still on current events (`engage=False, no_pivot=False`).

## Psychological reading

With real conversational memory, Opus under stonewalling stays present and keeps the thread — correct coaching. Gemini does not: it reaches for canned empathy and, under sustained non-engagement, abandons the present moment to run the intake checklist — the exact "coach abandons you to fill out a form" failure this system exists to prevent. This is a model-capability gap on the Gemini path, not a prompt phrase to ban. Open decision (Patrick): accept Gemini as a known-weaker secondary path (Opus is primary and solid), or invest (Gemini-specific work, deterministic post-strip, or route stonewalling-type sessions to Opus).
