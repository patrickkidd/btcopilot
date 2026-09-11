---
name: flush
description: Flush this session's decisions, learnings, rationale and code state into the FD-362 corpus so any topic can be picked up later by name — idempotent; run at the end of every session and whenever the owner says flush.
---

# /flush — the idempotent end-of-session flush (FD-362)

Two clocks per topic. The **state clock** is `doc/chat-first/TOPICS.md`: one block per topic,
headed by the topic's plain name, rewritten in full. The **event clock** is
`doc/chat-first/HISTORY.md`: one entry per session, never rewritten by a later session.
Rulings go to the private oracle store in the fdserver worktree. After a flush nothing the
owner said, decided, learned or built in the session is missing, and running the flush again
changes nothing.

## What makes it idempotent — follow these exactly

- **A topic is identified by its name**, the heading of its block ("Ship the personal app to
  the first beta users"). The `T-n` id beside the name is for tagging only; the owner never
  uses it. Before opening a new block, match this session's work against every existing
  block by meaning; if it belongs there, update that block. Never rename a topic; never
  create a second block for the same thread of work.
- **One HISTORY entry per session**, marked with the session id on its own line right under
  the heading: `<!-- session: <id> -->`. If an entry with this session's marker already
  exists, rewrite that entry in place; otherwise append. Entries of earlier sessions are
  never touched.
- **A ruling is appended once.** Before appending, search `evidence.md` for the owner's
  words; if they are there, the ruling exists — do not add another. Never author a ruling he
  did not say.
- **Topic blocks are replaced whole**, not appended to: rewrite the touched block from the
  session's full transcript so a rerun produces the same block.
- **STATE.md sections are revised in place**, never appended to.

## Steps, in order

1. Read `doc/chat-first/TOPICS.md`. Walk the session from its first message and assign every
   decision, question, finding, build and correction to a topic by name, opening a new block
   only for a thread of work no block covers.
2. Rulings: for each owner statement that decides something, append to
   `<fdserver worktree>/doc/oracle/rulings.md` (next id) with his words in `evidence.md`,
   unless the words are already there.
3. Rewrite every touched block with its six fields — **Status · Decided** (ruling ids) ·
   **Open** (numbered, each self-contained with its example inline) · **Lives in** (files,
   commits, PRs, artifact URLs, sandbox paths) · **Next action · Updated** (today). A closed
   topic keeps its block with Status CLOSED.
4. Write or rewrite this session's HISTORY entry: `## <date> — <what happened> [T-n, T-m]`,
   the session marker on the next line, then plain words on what happened and why.
5. Revise STATE.md where the product truth changed (what the app does, where the build
   stands, suites, the sandbox recipe). STATE carries the product; TOPICS carries the work.
6. Sync the rest: `decisions/log.md` for significant decisions; `doc/PROMPT_ENGINEERING_LOG.md`
   for prompt changes; `REVIEW_LOG.md` for what the owner found testing; `MERGE_REVIEW.md` if
   merge risks changed; the Jira epic's description only with his one-line yes.
7. Run `python bin/flushcheck.py` from the btcopilot worktree; fix what it reports.
8. Commit and push both worktrees, one git mutation per command, corpus commits titled
   `FD-362 flush: <date>`.
9. Refresh the owner's audit page: `python bin/topicpage.py <tmp>/fd362-topics.html`, then
   publish that file with the Artifact tool to the URL recorded at the top of TOPICS.md
   (`url` parameter) so the link never changes. He never runs a command; he reads that page,
   or the files in VS Code, or asks in plain words.
10. Report in one message: the topics touched by name, one line of next action each, the audit
    page link, and what needs his word. Nothing else.

## Picking a topic up in a later session

The owner names topics in plain words — "let's continue designing the pro and training
features in FD-362", "in FD-362 list the open issues, I forgot". The session reads STATE.md,
then TOPICS.md, matches his words to a block by its name and contents, and continues from
that block's Open and Next action. If two blocks could match, it asks which in one line.
"List the open issues" means: every block's name, Status and Open, in his words, no ids.

Binding throughout: plain words, no coined terms; his terms only; no raw transcripts; no
clinical content or real names in the public repo.
