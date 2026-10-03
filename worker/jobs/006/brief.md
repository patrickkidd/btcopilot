# Job 006 — FD-370 part 2: animation and technology, and drawn options

Model: Fable, extra high effort, for theory and design judgement. Opus sub-agents for reading and for drawing the page.

## Bases
- btcopilot: `origin/master`, read only.
- btcopilot-sources: continue on work branch `FD-370-diagram-eval` (from 6376bad). Write under `fd-corpus/private/fd370/` (force-add).

## Settled
Patrick accepted the split verdict of job 005 (your recommendation.md section 1): no whole-family diagram as a view that claims how the family works; yes to one still picture of who is in the record, built from pieces the layout already draws; patterns across generations are shown by the coach setting small pictures side by side as its claim on the record.

## New question (Patrick's words, paraphrased)
Bowen worked before computers. The aim of the app is to push past what was possible then, while keeping his wisdom. Bowen always wanted a way to show the family animated, which was not possible in his time; the app already does this to some degree (the play-by-play, the timeline, the coach driving diagram pieces). Review the sources for:
1. What Bowen and Kerr said about showing the family over time, in motion, or beyond the static diagram (search all of bowentheory/ and theory/ for this; quote it).
2. Which theory principles an animated or technology-driven view must keep (e.g. the family as one emotional unit, process over content, facts of functioning, dates), and which it may freely go beyond.
3. How the split verdict changes, if at all, once animation is allowed: e.g. the picture of who is in the record changing over time (births, deaths, cutoffs as dated events); the side-by-side pictures played together on one timeline.
Label each claim as from a source (quoted, with file and line) or as your inference.

## Deliver
- `animation.md`: answers 1-3, verdict first, at most 200 lines.
- `options.html`: a self-contained phone-width page of up to four drawn options (inline SVG, family diagram style: squares men, circles women, marriage lines, children below; for animation, two or three frames in a row with their dates). Each frame has a unique id (G1, G2, ...), one caption sentence: what is on screen, what the user taps, what it tells them about their own life. One numbered list of at most 3 decisions for Patrick, each with its own concrete example. Plain common words; Patrick's terms only: cluster, event, PDP, pair-bond, play-by-play. No coined terms. Fictional names only. CSS colours as tokens on :root with a dark mode under prefers-color-scheme; no external resources; no horizontal scroll at 390px. Links (if any) target="_blank" rel="noopener".

## Must not
No btcopilot code changes, no new tables, no secrets, no Jira.

## Done
Branch pushed; report.md (≤10 lines, no private content) names the commit.
