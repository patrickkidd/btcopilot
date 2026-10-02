# Job 003 — measuring how much of a family evaluation's basic data the coach has gathered

From Patrick, 2026-10-02: go hard and be creative. This is a theory-heavy job and you may change the theory files. Results feed the FD-369 pull request, where measuring basic-data coverage is one of the two headline additions.

This branch is in a public repository. `status.md` and `report.md` quote no private material.

**Base ref and work branch:** in your clone of patrickkidd/btcopilot-sources, branch `worker/job-003-basic-data-coverage` from `origin/master` (pull first). Read only in patrickkidd/btcopilot (`origin/master`).

**Coordinate first.** Patrick runs an interactive Claude Code session named "FD-367 Case Page" on your machine, designing the case page. Before you start, find it with ListAgents. Send it one message saying what this job is, which files you will change, and the branch name. Ask whether the case page will show what is known or unknown about each person, and if so what it needs from coverage. Put its answer in the review (step 4). That session writes no theory files, but if it says it is about to touch one you change, agree an order with it before going on. If you cannot reach it, say so in the review and go on.

**What exists (read these):**
- Theory, in btcopilot-sources: `theory/notes/basic-data.md`; `theory/REFERENCE.md` section 6f; `theory/OPEN_QUESTIONS.md` items 19 and 37 to 39, and any others about basic data; the theory skill at `claude-user/skills/theory/SKILL.md`, used for all the judgement here.
- Built, in btcopilot: `doc/COVERAGE.md` and `btcopilot/coverage.py`. These hold the checklist, its five states (known, asked, said unknown, declined, not asked), the depth rules, and the dashboard measures. Also the coach's block "WHAT IS STILL UNKNOWN" in `fd-corpus/private/prompts/agent.prompty`.
- Rulings: read the ones these files cite, in the sops rulings store (`private/oracle/` in btcopilot). Never write a ruling. A proposed one is labelled "for Patrick to rule".

**Do (Fable for judgement; Opus sub-agents for reading):**
1. Answer each open question (19: where work, school, health and places are stored; 37: the partner's family when the person comes alone; 38: how deep to go into the extended family; 39: whether a declined item is asked again). Give what the sources say, with source and line, and one proposed answer for Patrick to rule.
2. Judge the depth rules and the partner's-family test now in code against the sources: hold, change (to what), or no source either way.
3. Say whether the nuclear family's history by life stage and the events in the extended family should become checklist items, and how each would be counted, with a worked example on a made-up family.
4. Go hard and be creative on how to measure basic-data coverage. Start from the four measures `doc/COVERAGE.md` lists as not built (facts per evaluation question, free coverage on coaching turns, engagement after a question, ask density against return within a week). Find others in the sources (for example, which missing facts matter most for reading the family), and things the sources argue against measuring.
   - Give up to 15 ranked measures. For each: its source and line, what it shows Patrick, how it is computed from what is stored today, or what it would need stored, and a worked example.
   - Then any number of further ideas, one line each, with "no source" where there is none.
5. Update the theory files the findings change (the basic-data note, REFERENCE 6f, OPEN_QUESTIONS, COVERAGE, LEDGER and any others), following the theory skill's own procedures.
6. Write the whole result to `fd-corpus/private/basic-data-coverage/review.md`: steps 1 to 4, the case page session's answer, and a list of the theory files changed and why. Commit by pathspec and push the work branch. If the push is refused, write `question: cannot push btcopilot-sources` and wait.

**Do not:** write code or change anything in patrickkidd/btcopilot; run tests; write a ruling; merge, open a pull request or push `master`; touch production, Jira or the real-model keys.

**Done means:** the work branch holds the review and the theory changes. `report.md` gives the branch, its last commit, the number of open questions answered, the number of measures ranked, whether the case page session answered, and the model the judgement ran on.
