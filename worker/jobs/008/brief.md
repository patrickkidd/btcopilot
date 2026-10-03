# Job 008 — the case report's last three cards: the person's own part, the choice, what to work on and what to expect

From Patrick, 2026-10-03, reviewing the case report proposal: "that is most certainly a theory question". He confirmed this job. Model: Fable for the theory and design judgement, using the theory skill; Opus sub-agents for reading; an independent Opus verifier for every quote and line cited. This is judgement, not a build.

This branch is in a public repository. `status.md` and `report.md` quote no private material.

**Base ref and work branch:** in your clone of patrickkidd/btcopilot-sources, branch `worker/job-008-own-part` from `origin/FD-367` (fetch first). Read only in patrickkidd/btcopilot.

**What to read:**
- The proposal as Patrick saw it: `mailbox/FD-367/proposal-2026-10-03.html` on btcopilot-sources branch `origin/worker-mailbox` (open it in a browser at 393 by 852; the three cards are "Patrick's own part", "Where there was a choice", "What to work on, what to expect").
- What is ruled about the page, in Patrick's words: `doc/handoffs/FD-367-2026-10-03-design-freeze.md` on btcopilot branch `origin/FD-367`. Every answer must fit those rulings. The ones that bind most here: a coach's guess is drawn as the coach's chat bubble with the facts it rests on as chips under it; the page writes no words of its own about certainty; nothing folds; no inline component that repeats what the pinned timeline gives; trim wherever possible ("this thing is already very busy"); and the coach's wording rule (says what came first and how close in time, names the facts it rests on, never says one thing caused another, claims no more than the facts hold, and often says plainly that this is its own view).
- The research behind the ten levels, on `origin/FD-367`: `fd-corpus/design/fd336/research/MENTAL_MODEL.md`, `research/SYNTHESIS-v2.md`, the case files under `fd-corpus/design/fd336/cases/`; and job 004's answers on `origin/worker/job-004-case-page-theory`: `fd-corpus/design/fd336/theory-answers-v5.md`.
- The theory skill at `claude-user/skills/theory/SKILL.md` and the theory corpus it points to; the rulings these cite, in `private/oracle/` in btcopilot. Never write a ruling; a proposed one is labelled "for Patrick to rule".
- What the app stores today that these cards could draw on (read only, btcopilot `origin/master`): the coach's stored guesses, the person's own statements, events and clusters, open questions. Say plainly where a card would need something not stored today; a new table or column is Patrick's call and is only named, never designed.

**Patrick's questions, in his words:**
1. On the card "Patrick's own part": "it says `PATRICK'S OWN PART` which is a crucial component of this thing but the content chosen to go in that card does not draw a clear connection in what `Patrick's own part` exactly is."
2. On the card "Where there was a choice": "Keep a loose question as to whether card 9 `Where there was a choice` might overlap or cover the previous `Patrick's own part` card?"
3. On the card "What to work on, what to expect": "what makes the coach think that is what the user needs to work on and what to expect? Like, why *that* choice? In the example given that is just what I said myself, not an inference from the coach. Is the coach simply agreeing with me? If so, that is not obvious as presented here. And it doesn't say anything about what to expect. For example, in some cases you have to expect the 'change back moves' from the others when you try to do something different. There are many other examples".

**Do:**
- For each card: what the sources mean by it (the person's own part in the family problem; a point where the person could have acted differently; the effort to change and what follows it), with verbatim passages and references, or "no source". Check the theory reference's list of off-theory readings first (blame against responsibility, words against action, announcing a change, and the like).
- Question 1: say what in a record shows a person's own part, in plain words a person on the street can read, and what the card should hold so the connection is plain at a glance. Use Patrick's record as the worked example and one made-up person as a second.
- Question 2: say whether the two cards are one thing or two by the sources, and recommend: keep both, merge into one, or drop one. Say what each would hold if both stay, so they do not repeat each other.
- Question 3: (a) what the card may rest on: the person's own stated aim, the coach's guess, or both, and how the page shows which is which under the ruled look (the person's words against the coach's bubble); (b) what the sources say a person should expect when they act differently, including others pushing them to change back, with the passages; which of those the coach may say for a particular person from their record, and which are general and belong in the book drawer only; (c) what the card shows when the record holds no stated aim and no basis for one.
- For every recommendation give what the reader sees and taps, in the ruled look, concretely enough for a builder to draw it at 393 by 852 without asking. Where there is a real fork, give at most three options with one recommended, each as: its short title, one plain line (what you see, what you give up), and its exact contents on Patrick's record.
- Never coin a term. Use Patrick's terms (clusters, events, pair-bonds, the coach's guess, chip, timeline, family picture) and common words; theory words never appear in what a user would read.

**Write** `fd-corpus/design/fd336/theory-answers-own-part.md` on the work branch, at most 150 lines: first a list "For Patrick to rule" of at most four items, each self-contained with its options; then one section per question with the answer in at most three sentences, the drawable contents, and the passages (verbatim, with reference) that would go in that card's book drawer. Commit by pathspec and push the work branch. If the push is refused, write `question: cannot push btcopilot-sources` and wait.

**Do not:** write code or change anything in patrickkidd/btcopilot; change theory files (propose changes in the answers file); run tests; write a ruling; merge, open a pull request or push `master`; touch production, Jira or the real-model keys.

**Done means:** the work branch holds the answers file. `report.md` gives the branch, its last commit, the number of items for Patrick to rule, the recommendation on question 2 in one line, and the model the judgement ran on.
