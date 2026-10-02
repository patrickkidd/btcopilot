# Job 002 — check the coach's planned reply checks against the theory

From Patrick, 2026-10-02, in his words: "it is perfectly fine to use my own thread anywhere ... The worker can certainly see the rulings, as I said it has the private repo in ~/btcopilot/btcopilot-sources and the SOPS key, just like you."

This branch is in a public repository. Everything you write here must stay free of private material: no quotes from rulings, the thread, the prompts or the theory corpus in `status.md` or `report.md`. The review itself goes to the private repo (step 4).

**Base ref and work branch:** in your clone of patrickkidd/btcopilot-sources, branch `worker/job-002-theory-review` from `origin/master`. No change to patrickkidd/btcopilot.

**Do:**
0. Your local notes say you have no key for the rulings store or the encrypted prompts. Patrick's words above correct that. Update your local notes to say you have the key and may read both when a brief asks you to. Also note that Patrick's own thread may be used anywhere.
1. Pull btcopilot-sources first. If `theory/OPEN_QUESTIONS.md` on `origin/master` was last changed in commit d650aa8 or earlier, write `question: theory files not pushed yet` in `status.md`, then wait. Patrick is pushing newer theory files from the other machine.
2. Read `fd-corpus/private/eval-suite/eval-suite-plan.md`, the two lists "First dozen rule checks" and "First dozen expected behaviours on known messages", 24 items in all. For each ruling id an item cites, read the ruling in the encrypted rulings store (`private/oracle/` in the btcopilot repo, sops).
3. Use the theory skill (`claude-user/skills/theory/SKILL.md` in btcopilot-sources; it finds the corpus from its own location). Run the judgement on Fable; Opus sub-agents may do the reading. For each of the 24 items, give:
   - one verdict: Supported (a source backs it), Contradicted (a source argues against it), Silent (the sources do not speak to it), or Patrick only (it rests on his ruling alone, which binds; say so and move on);
   - the source and line for Supported or Contradicted;
   - one example of a reply a Bowen-trained coach would give that the check would wrongly fail, or "none found" (example: a reply that quotes the user saying "because my father left" fails the "no cause words" check);
   - at most 3 lines per item.
   Then go hard and be creative: Patrick wants this job to move the needle on how the coach's conversation quality is measured. Mine the whole theory corpus (concepts, cases, coaching transcripts, corrections, open questions) for what a good Bowen-trained coach does and avoids in a conversation, and turn it into new checks:
   - **Up to 15 new checks, ranked** by how much each would tell Patrick about quality. Give each one a source and line, one reply that passes and one that fails, and how it is measured. Group them by measurement:
     - (a) free, on the reply's words, like "no cause words";
     - (b) free, on what the coach wrote into the record that turn, like "a brother already on record is not added again";
     - (c) free, on the shape of the conversation across turns, such as what the user does next;
     - (d) needs a model reading the reply.
   - **Beyond those 15:** any number of further checks, and any new way of measuring conversation quality that is not a per-reply check. One line each, with its source if it has one. Ideas without a source are welcome if they are labelled "no source".
   Patrick's votes will decide which checks join. A check joins only if it flags the replies he voted not acceptable. So say which checks his votes could test soonest.
4. Write the result to `fd-corpus/private/eval-suite/theory-review.md` on the work branch, commit only that file, and push the work branch. If the push is refused, write `question: cannot push btcopilot-sources` and wait.

**Do not:** edit the theory corpus, the plan, the rulings or any other file (put proposed corpus changes in the review instead); write code; run tests; touch production, Jira or the real-model keys; merge or open a pull request.

**Done means:** the work branch holds `theory-review.md` with 24 verdicts, the ranked new checks and the further ideas. `report.md` gives the branch, its last commit, the counts per verdict and the model the judgement ran on. It quotes no private material.
