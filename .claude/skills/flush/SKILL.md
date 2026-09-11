---
name: flush
description: Flush this session's decisions, learnings, rationale and code state into the FD-362 corpus so any topic can be picked up by a later session — idempotent; run at the end of every session and whenever the owner says flush.
---

# /flush — the idempotent end-of-session flush (FD-362)

Two clocks, per topic: the **state clock** is `doc/chat-first/TOPICS.md` (one block per topic,
rewritten in full); the **event clock** is `doc/chat-first/HISTORY.md` (append only, entries
tagged with topic ids). Rulings go to the private oracle store in the fdserver worktree.
Nothing the owner said, decided, learned or built in the session may be missing afterwards.

Do these steps in order. Each is safe to repeat.

1. **List the topics this session touched.** Read `doc/chat-first/TOPICS.md`. Walk the whole
   session transcript from its first message and assign every decision, question, finding,
   build and correction to an existing topic id, or open a new `T-n` block. A topic is a
   thread of work the owner could name ("get the beta deployed", "the IRR review"), not a
   file or a commit.
2. **Rulings first.** For every statement of the owner that decides something, append a
   ruling row to `<fdserver worktree>/doc/oracle/rulings.md` (next id, his words quoted in
   `evidence.md`), unless it is already there. Never author a ruling he did not say.
3. **Rewrite every touched topic block** in TOPICS.md with all six fields: Status · Decided
   (ruling ids) · Open (numbered, each self-contained) · Lives in (files, commits, PRs,
   artifact URLs, sandbox paths) · Next action · Updated (today). Keep blocks for untouched
   topics as they are. A closed topic keeps its block with Status CLOSED.
4. **Append one HISTORY.md entry** for the session (or one per distinct piece of work if the
   day had several), dated, tagged `[T-n, T-m]`, saying what happened and why in plain words.
   Never rewrite earlier entries.
5. **Revise STATE.md** where the product truth changed (what the app does, where the build
   stands, suites, sandbox recipe). STATE carries the product; TOPICS carries the open work.
6. **Sync the rest**: `decisions/log.md` for significant decisions; `doc/PROMPT_ENGINEERING_LOG.md`
   for any prompt change; `REVIEW_LOG.md` rows for anything the owner found while testing;
   `MERGE_REVIEW.md` if merge risks changed; the Jira epic FD-362 description only with his
   one-line yes.
7. **Check**: run `python bin/flushcheck.py` from the btcopilot worktree. It fails if a topic
   block lacks a field, a HISTORY tag names an unknown topic, or the newest HISTORY entry is
   not dated today.
8. **Commit and push both worktrees**, one git mutation per command, the corpus commits
   titled `FD-362 flush: <date>`.
9. **Report** to the owner in one message: the topics touched, the one-line next action for
   each, and anything that needs his word. Nothing else.

Rules that bind the flush: plain words, no coined terms; his terms only; every open question
self-contained with its example inline; no raw transcripts anywhere; no clinical content or
real names in the public repo.
