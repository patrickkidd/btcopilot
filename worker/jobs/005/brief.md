# Job 005 — FD-370: does the app need a full family diagram view?

Model: Fable, extra high effort, for all theory judgement and the recommendation. Opus sub-agents only for inventorying code and docs. This question has been attacked from many angles with Opus before without a satisfying answer; go deep and be creative.

## Bases
- btcopilot: `origin/master`. Read only. No code changes.
- btcopilot-sources: `origin/HEAD`. Work branch `FD-370-diagram-eval`; write results there under `fd-corpus/private/fd370/` (force-add if ignored). Nothing private goes on this mailbox branch.

## The question
The coach can now drive segments of the family diagram, and the chat has the play-by-play. Is what exists plus what the case report feature plans enough for the user to get the total picture of their extended family system? Or does the app need a complete or larger family diagram view, or a composed way of building the total picture piece by piece?

## Read
1. What exists: btcopilot `doc/SCREENS.md`, `doc/UI_SPEC.md`, `doc/CLUSTERS.md`, `doc/DRAWABILITY.md`, `doc/FAMILY_DIAGRAM_VISUAL_SPEC.md`, `doc/STATE.md`, and the page code they point to.
2. What is planned (case report): btcopilot-sources `fd-corpus/design/fd336/` (gallery-v5.html and siblings) and the case report passages in `fd-corpus/private/PATRICK_STATEMENTS.md`.
3. Theory: `bowentheory/` (Kerr & Bowen "Family Evaluation" chapters, esp. 7, 8, 10; Bowen basic series; FTiCP), `theory/notes/seminar-2024-26.md`, and anything else in `theory/`.

## Framing the theory review must test, not assume
Not genealogy. The family as a biological, emotional unit, and how it shapes the functioning of its members, above all the user, in their own life today. Derive from the sources what the picture is *for* (e.g. seeing the emotional process across generations, functioning positions, cutoff, multigenerational transmission, where anxiety lands), then judge each option by that.

## Deliver (in fd-corpus/private/fd370/)
- `recommendation.md`: verdict first (enough as is / full diagram view / composed piece-by-piece view / other), then the top 3–5 findings ranked, each with source citations (file + passage) and a concrete example of what the user would see. Rejected options one line each with why.
- Gaps: what the segments + play-by-play + case report cannot show that the theory says matters.
- Up to three option sketches described in plain words (what is on screen, what the user taps, what it shows them about their own life). No new terms; use "cluster", "event", "PDP", "pair-bond".

## Must not
No code edits on btcopilot, no new tables, no Jira, no secrets, no real-model API calls beyond your own session. Questions only for real blockers.

## Done
Work branch pushed; `report.md` here (≤10 lines, no private content) names the branch and commit.
