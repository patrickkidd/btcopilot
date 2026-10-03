# Job 004 — theory answers on the case report mockup, version 5

From Patrick, 2026-10-03, reviewing the case report mockup version 5: these questions are for the worker machine, on Fable, using the theory skill. This is judgement and theory work, not a build.

This branch is in a public repository. `status.md` and `report.md` quote no private material.

**Base ref and work branch:** in your clone of patrickkidd/btcopilot-sources, branch `worker/job-004-case-page-theory` from `origin/FD-367` (fetch first). Read only in patrickkidd/btcopilot.

**Coordinate first.** If the session "FD-367 Case Page" on your machine is running (ListAgents), send it one message: what this job is and the branch name. Ask it whether it already holds answers to any of the six questions below. Use what it says; do not ask it again. If it is not running, go on.

**What to read:**
- The mockup: `mailbox/FD-367/gallery-v5.html` on btcopilot-sources branch `origin/worker-mailbox` (open it in a browser; the cards named below are on it).
- The research behind it, on `origin/FD-367`: `fd-corpus/design/fd336/research/MENTAL_MODEL.md`, `research/SYNTHESIS-v2.md`, `research/PLAY-BY-PLAY-DESKTOP.md`, `fd-corpus/design/fd336/verdict.md`, and the case files under `fd-corpus/design/fd336/cases/`.
- The coverage review from job 003, on branch `origin/worker/job-003-basic-data-coverage`: `fd-corpus/private/basic-data-coverage/review.md`. Patrick has not yet given his critique of it.
- The theory skill at `claude-user/skills/theory/SKILL.md`, used for all the judgement. Rulings the files cite, in `private/oracle/` in btcopilot. Never write a ruling; a proposed one is labelled "for Patrick to rule".

**Patrick's questions, in his words:**
1. "'What brought Patrick' card is very good. How will it scale to more events?"
2. "'The couple since they met' card will feel like it applies only when there is a marriage. I bet that phrase came from Bowen which was a thumbnail from the ideal family case perspective. This app is aimed at the general population. Others will be single for example, or even polyamorous. How should we deal with that?"
3. "You created a new visual convention for the timeline with the vertical bars in a horizontal bar. Is that intended to show coverage? If we are just reading out data to be tapped and interacted with then we should keep the existing timeline component and collapse/expand it as necessary for the intended UX. If you are trying to show some kind of coverage then it is good to make it obvious where there is little coverage so that people take the gaps or small data sample into consideration, where they need to take it into consideration. But we also need to carefully consider the dimensions of coverage that are being used, which is a theory question. It looks like this horizontal bar with vertical bars is meant to show coverage in a given year? I'm confused. And if so then I'm not sure that is a legitimate dimension of coverage. But you tell me. And also, you tell me if we need to wait on the coverage measurement question for this which is awaiting my critique." (Related: the row of boxes labelled "The record covers", with the lines "8 of 36 people: something happened to them" and "4 open questions, none on these facts". Patrick finds both lines cryptic. Say whether this row is the same convention, and what it should say or be replaced by.)
4. "The 'All of it on one timeline' is going to need to scale to more events, and what is shown is going to need to make sense in the overall thread between the cards as the amount of data scales. Maybe what you have is sufficient, I'm not sure. But I just wanted to make sure you weren't happy-pathing the UI on the limited data we have so far."
5. "In the 'The reading, for the therapist' card: I don't understand what 'Left off this page: it says what caused what'. I also don't understand 'Not enough in the record to choose a reading' - what 'reading'? Again, all of this needs to be self-explanatory to a non-technical person, to the average person on the street. Then you show chips under 'Rests on, in the record', but tapping them doesn't do anything."
6. "In 'Where there was a choice' and 'What to work on, what to expect' card, clicking the event chips does nothing or makes the event title show in grey at the bottom of the card. That is disjointed and will feel confusing to the user. There needs to be a single, simple UI connection between a tapped chip and how its corresponding UI element is shown. There is no timeline in those cards or global timeline overlay for those cards, so there is nothing really to show. Showing the title for the chip's event as more detail is not bad, but also not great."

**Do (Fable for judgement; Opus sub-agents for reading; an independent Opus verifier for every quote and line cited):**
- For each question: the answer in plain words a person on the street can read; the sources (verbatim passage with reference, or ruling id, or "no source"); what changes on the page, described as what the reader sees and taps; and whether it must wait on Patrick's critique of the job 003 coverage review (yes or no, and why).
- Questions 1 and 4: test the card against a made-up family with ten times the events (fictional; say how many people, events and clusters) and say what breaks and what to do.
- Question 2: propose a title and contents that hold for a person who is single, divorced, widowed, in several relationships, or in a same-sex couple, grounded in the theory; say what the theory treats as the unit when there is no couple.
- Questions 5 and 6: propose one tap rule for chips that holds on every card, and the exact plain words to replace the cryptic lines.
- Never coin a term. Use Patrick's terms (PDP, clusters, pair-bonds, events) and common words. A word the mockup or research invented is translated into common words.

**Write** the result to `fd-corpus/design/fd336/theory-answers-v5.md` on the work branch: one section per question, the answer first in at most three sentences, then the detail. Commit by pathspec and push the work branch. If the push is refused, write `question: cannot push btcopilot-sources` and wait.

**Do not:** write code or change anything in patrickkidd/btcopilot; change theory files (propose changes in the answers file instead); run tests; write a ruling; merge, open a pull request or push `master`; touch production, Jira or the real-model keys.

**Done means:** the work branch holds the answers file. `report.md` gives the branch, its last commit, for each question one line on whether it waits on the coverage critique, whether the case page session answered, and the model the judgement ran on.
