# Job 006 — a formal definition of the minimum data for a family evaluation, and of coverage

From Patrick, 2026-10-03, in his words: "This is a big and mission critical concept. For the first time in this field of clinical practice we have an opportunity to test out a formal definition of both A) the minimum required information to conduct a family evaluation, and B) the degree of coverage in a given family (including relative coverage like what stones are still unturned in a given family, versus coverage compared to the minimum required data to conduct a family evaluation). The job should certainly be optimized for token burn and wall clock execution time (i.e. don't waste tokens or time needlessly) but *without sacrificing quality*."

This branch is in a public repository. `status.md` and `report.md` quote no private material.

**Base ref and work branch:** in btcopilot-sources, branch `worker/job-006-evaluation-minimum` from `origin/worker/job-003-basic-data-coverage` (your own job 003 work, not yet merged). Pull first. Read-only in patrickkidd/btcopilot (`origin/master`). You have the sops key; read the rulings you need.

**Start from job 003, do not redo it.** Your review `fd-corpus/private/basic-data-coverage/review.md` and your theory edits are the base. An independent check on the other machine opened 58 of its citations, and 57 held. Make these corrections first:
- R-0496 was cited as the reason to gather nothing more on the partner's family until the talk reaches them. It only says which facts the questions tab shows. Drop that citation; say the floor has no source.
- "Every per-period measure rests on the schema question" overstates it. Covered or not can be counted from the record alone; only asked against never asked needs the schema change.
- Some code line numbers were read from an older master. Re-check them against `origin/master`.

**Patrick's rulings since job 003 (2026-10-03):**
1. A fact question may name a span of years or a death, not only a person or a couple. Example: "what was home like between your parents' wedding in 1984 and your birth in 1987?" can be stored as asked. His words: "if this adds a 'second way of cutting time beside clusters' then that is good from a data engine perspective but also keep in mind that this can quickly rack up too much business in the UI. So as always we must be very thoughtful of where we represent such data for our non-technical audience". UI questions go through mockups, not this job.
2. Words: "side" is accepted. For "stage", "sweep of a side", "floor" and "Kerr's minimum", he asks for each to be explained from the sources: what Bowen or Kerr actually said, quoted with source and line, and what exactly it bounds. Your earlier text only called "stage" a span and did not qualify "span". He wants the minimum-data concept named objectively, in the language of good clinical practice, not after one author. Propose that name and two alternatives.
3. For the case report (a page the person shows peers; it must ship by 2026-10-09), Patrick has already ruled: no band of years, no row of people squares. Coverage shows as one line under each coach guess, like "Rests on 6 dated facts · 1994–2011 · Patrick". Your job 003 section on the case page's answer is out of date; replace it.

**Do (Fable for every judgement; Opus sub-agents only for reading and for one verification pass):**
A. **The minimum data for a family evaluation, as a formal definition.** Give the items, the people they cover, what counts as having an item (known, said unknown, declined), and the threshold at which an evaluation can be conducted. Every element needs a source and line, or "no source" with the reason it is still proposed. Say where the sources disagree.
B. **Coverage of a given family, as a formal definition, in two senses:**
   - (i) against the minimum in A;
   - (ii) relative: which stones are still unturned in this family, given what its own record already shows (for example, a death with nothing on the months after it, a sibling with no life course, a side with one generation).
   For each measure: its source, how it is computed from the record (with ruling 1 above), and a worked made-up family.
C. **The case report's three questions:**
   - Is coverage one measure or several? Name each dimension the theory supports for one person's record, with its source or "no source". Candidates: items per person, per stage of a couple's life, per side and generation, the trouble's course from its start to seeking help, the months after a death, what each coach guess rests on.
   - Which of those belong on a case report a person shows peers, as opposed to the coach or the quality dashboard?
   - For each that does: one place or spread across the cards it applies to, and what the reader sees (a mark on the family picture, a line under a guess, a line under a stage). Hold to ruling 3, and to ruling 1's caution about crowding the screen.
D. **The words in ruling 2,** each explained from the sources, plus the objective name for the minimum.
E. Update the theory files the findings change, following the theory skill's procedures.

**Efficiency, as Patrick asked.** Reuse job 003's reading and its verified citations rather than re-reading the corpus. Open new sources only for what A to D need that job 003 did not cover. Run one verification pass at the end on the new citations only, not the job 003 ones already checked. Do not rewrite unchanged sections of the review.

**Write** the result to `fd-corpus/private/basic-data-coverage/evaluation-minimum.md`. Put a summary of at most 40 lines at the top, in plain words, then A to E. Commit by pathspec and push the work branch. A different Claude session on the other machine (the case report) will read it; it does not need to be messaged.

**Do not:** write code or change patrickkidd/btcopilot; run tests; write a ruling; merge, open a pull request or push `master`; touch production, Jira or the real-model keys.

**Done means:** the work branch holds `evaluation-minimum.md` and the theory changes. `report.md` gives the branch, its last commit, the counts of items in A and measures in B, the name proposed in D, wall-clock time, and the model the judgement ran on.
