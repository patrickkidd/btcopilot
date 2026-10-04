# Job 010: ask early which periods of life stand out most

Base ref: origin/master of patrickkidd/btcopilot. Work branch: `worker/salient-periods` (create from the base, push it; never master).

## Goal
Early in coaching, the coach asks the person which periods of their life stand out most, to get quick coverage of the most intense stretches of emotional process. Reason: people remember what was emotionally salient, so those were the more intense times.
Caveat the product owner confirmed: what people recall is mostly when their symptoms or other things were up, not the whole picture. Quieter wider-family shifts (for example a death or a move before the person could notice) can be missed. So the question opens the history and does not replace it.

## Read first (all pushed)
In btcopilot master: `doc/COVERAGE.md`, `doc/CLUSTERS.md`, `doc/specs/BOWEN_THEORY.md`, `CONTEXT.md`, `btcopilot/tests/live/README.md` and `btcopilot/tests/live/test_coachturn.py`, `test_repeats.py`, `criterion.py` (eval style), public prompt fragments in `btcopilot/prompty/fragments/`: `coach_story_shape.md`, `coach_notes.md`, `coach_reference.md`, `follow_up.md`, `open_questions.md`.
In btcopilot-sources master (private repo you have cloned): `bowentheory/FE Chapters/` (chapters 5, 8, 9, 10 first), `bowentheory/FTiCP Chapters/15 - Family Reaction to Death.md`, `bowentheory/Basic-Series/` (5 and 6), `bowentheory/Gilbert (2006) - The Eight Concepts of Bowen Theory.md`. Use `git pull` there first.
You have no sops key: this job needs neither the encrypted prompts nor the rulings store. Work only from the files above.

## Work
Judgement on theory runs on Fable sub-agents; mechanics (writing files, patch, checks) on Opus sub-agents. Write these in `doc/proposals/salient-periods/`:
a. `theory.md`: from the sources, what the question should get at, and its risks (recall bias toward symptom periods, missed quiet wider-family shifts, telescoping of dates).
b. `phrasings.md`: 5 to 8 candidate phrasings in plain words a person would answer, ranked. Each with the theory reason and an example fictional answer.
c. `placement.md`: where it sits in the coverage order of `doc/COVERAGE.md`, and how the coach follows up on each named period (dates, who, what changed) without turning into a questionnaire. Include how it later checks the gaps between named periods and the wider family.
d. `fragments.patch`: proposed edits to the PUBLIC prompt fragments only, as a unified diff against origin/master. Do not edit the fragments themselves.
e. `evals.md`: 2 to 4 live-eval case drafts in the style of `btcopilot/tests/live`, fictional inputs only, each with a deterministic pass criterion (a check on the record, or k of n runs). Drafts only; do not run them.
f. `decide.md`: a ranked top list of what a reviewer must decide, each with sources and an example; the rest at one line each. Plain words, no coined terms; use "cluster" and "event", never "stretch" or "moment".

## Rules
Files you may touch: only new files under `doc/proposals/salient-periods/`. Fictional people only; no real names, no quotes of real records (this repository is public). Tests to run: none. No exclamation points in any proposed user-facing text.
Do not: touch production, sandboxes, Jira, secrets, `.env`, the encrypted prompts or rulings store; merge, open PRs, push master, run the full suite, make real model API calls, edit the fragments themselves.
Done: `report.md` of at most 10 lines (ranked top decisions first), the work branch pushed.
