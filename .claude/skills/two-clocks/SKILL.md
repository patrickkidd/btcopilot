---
name: two-clocks
description: Flush this session's decisions, learnings, rationale and code state into the FD-362 corpus so any topic can be picked up later by name — idempotent; run at the end of every session and whenever Patrick says flush.
---

# /two-clocks — the idempotent end-of-session flush (FD-362)

Two clocks per topic. The **state clock** is `doc/chat-first/TOPICS.md`: one block per topic,
headed by the topic's plain name, rewritten in full. The **event clock** is
`doc/chat-first/HISTORY.md`: one entry per session, never rewritten by a later session.
Rulings go to the private oracle store in the fdserver worktree. After a flush nothing the
owner said, decided, learned or built in the session is missing, and running the flush again
changes nothing.

## What makes it idempotent — follow these exactly

- **A topic is identified by its name**, the heading of its block ("Ship the personal app to
  the first beta users"). The `T-n` id beside the name is for tagging only; Patrick never
  uses it. Before opening a new block, match this session's work against every existing
  block by meaning; if it belongs there, update that block. Never rename a topic; never
  create a second block for the same thread of work.
- **One HISTORY entry per session**, marked with the session id and the time of the last flush on its own line right under
  the heading: `<!-- session: <id> · flushed: <ISO time> -->`. If an entry with this session's marker already
  exists, rewrite that entry in place; otherwise append. Entries of earlier sessions are
  never touched.
- **A ruling is appended once.** Before appending, search `evidence.md` for Patrick's
  words; if they are there, the ruling exists — do not add another. Never author a ruling he
  did not say.
- **Topic blocks are replaced whole**, not appended to: rewrite the touched block from the
  session's full transcript so a rerun produces the same block.
- **STATE.md sections are revised in place**, never appended to.

## Mid-session flushes — the same skill, incremental

The owner calls `/two-clocks` whenever he likes, not only at the end. To keep a repeat
run from rewording what an earlier run already captured:

- The session's HISTORY entry carries `<!-- session: <id> · flushed: <ISO time> -->`. A
  flush reads that time and works only from the owner's statements after it (the trace
  holds each statement's time); earlier statements were already captured. A topic block
  is touched only if a statement since then belongs to it — otherwise it is left
  byte-for-byte as it was.
- Rows in trace.json already named by a session (`named_by: "session"`) keep their name and
  summary; a flush names only script-named rows from this session.
- A ruling is appended only if no row in `evidence.md` already carries those words, and
  no ruling id already cited in the topic's Decided field states the same decision. When
  the owner restates a ruling in new words, note the restatement under the existing id
  in evidence.md rather than adding a second ruling.
- The HISTORY entry for this session is rewritten as a whole from all of the session's
  statements, so a later flush in the same session extends it; its marker's time moves
  forward; earlier sessions' entries are never touched.
- Pages are regenerated from the files, so running twice with nothing new republishes an
  identical page.

## Steps, in order

1. Read `doc/chat-first/TOPICS.md`. Walk the session from its first message and assign every
   decision, question, finding, build and correction to a topic by name, opening a new block
   only for a thread of work no block covers.
2. Rulings: for each owner statement that decides something, append to
   `<fdserver worktree>/doc/oracle/rulings.md` (next id) with his words in `evidence.md`,
   unless the words are already there.
3. Rewrite every touched block with its six fields — **Status · Decided** (ruling ids) ·
   **Open** (numbered, each self-contained with its example inline) · **Lives in** (files,
   commits, PRs, artifact URLs, sandbox paths) · **Next action · Updated** (today). Every
   numbered Open item starts with one of four tags — `[ruling]` needs Patrick's word,
   `[build]` is work not yet done, `[verify]` is built but unchecked or unmeasured, `[waiting]`
   is blocked on something outside the topic — and an item that mixes two is split in two. A
   closed topic keeps its block with Status CLOSED.
4. Write or rewrite this session's HISTORY entry: `## <date> — <what happened> [T-n, T-m]`,
   the session marker on the next line, then plain words on what happened and why.
5. Revise STATE.md where the product truth changed (what the app does, where the build
   stands, suites, the sandbox recipe). STATE carries the product; TOPICS carries the work.
6. Sync the rest: `decisions/log.md` for significant decisions; `doc/PROMPT_ENGINEERING_LOG.md`
   for prompt changes; `REVIEW_LOG.md` for what Patrick found testing; `MERGE_REVIEW.md` if
   merge risks changed; the Jira epic's description only with his one-line yes.
7. Run `python bin/flushcheck.py` from the btcopilot worktree; fix what it reports.
8. Commit and push both worktrees, one git mutation per command, corpus commits titled
   `FD-362 flush: <date>`.
9. Refresh Patrick's two pages, same links every time (URLs at the top of TOPICS.md, passed
   to the Artifact tool as `url`), in this order:
   a. `python bin/ledger.py` — rewrites doc/chat-first/events.json from every dated source
      (history, rulings, decision log, review log, commits in both worktrees, artifacts).
   b. `python bin/trace.py` — mines Patrick's own statements out of the local transcripts
      into doc/chat-first/trace.json, one row per thing he typed, in order. It writes nothing
      but his words.
   c. **The judgement step, and it is this session's job, not the script's.** trace.py gives
      every new row a mechanical short name and a one-line summary and marks it `named_by`
      "script". Before rendering, rewrite this session's own rows in trace.json — the name in
      3–5 plain words for what he asked for, the summary in one line under 90 characters, the
      piece of work corrected if the word match put it in the wrong one — and set `named_by`
      to "session" on each row you rewrite. Rows marked "session" are never recomputed, so a
      row left as "script" reads as a machine guess on his page.
   d. `python bin/tracepage.py <tmp>/fd362-clocks.html` (the dashboard: his one line of thought,
      each piece of work a horizontal line, and a second view of where every piece stands) and
      `python bin/topicpage.py <tmp>/fd362-topics.html` (the topic register as a page).
   Commit events.json and trace.json with the corpus. Records the ledger could not assign to a
   topic land in the audit lane; assign them by adding the missing words to the topic block or
   the ledger's word list — never by hand-editing events.json. He never runs a command; he
   reads the pages, or the files in VS Code, or asks in plain words.
10. Report in one message: the topics touched by name, one line of next action each, the audit
    page link, and what needs his word. Nothing else.

## Picking a topic up in a later session

Patrick names topics in plain words — "let's continue designing the pro and training
features in FD-362", "in FD-362 list the open issues, I forgot". The session reads STATE.md,
then TOPICS.md, matches his words to a block by its name and contents, and continues from
that block's Open and Next action. If two blocks could match, it asks which in one line.
"List the open issues" means: every block's name, Status and Open, in his words, no ids.

Binding throughout: plain words, no coined terms; his terms only; no raw transcripts; no
clinical content or real names in the public repo.

## The spec sheet for beta users (added 2026-09-11, Patrick's ask)
`doc/chat-first/SCREENS.md` is the state clock of every screen's behaviour in plain words, one
sentence per item tagged `[built]`, `[drawn]` or `[open]` with ruling ids in braces, written for
the beta users. Every flush revises its items for the session's rulings (an `[open]` item whose
choice landed becomes `[drawn]` or `[built]` with its id; a new ruled behaviour gets a new item),
sets its `Updated:` line to today, re-renders its pictures with `python bin/screenshots.py` (every mockup frame in doc/chat-first/mockups/ and the built views' goldens into doc/chat-first/screens/), renders the catalogue with `python bin/screenspage.py <tmp>/fd362-screens.html`, publishes it with the `screens/*.png` files alongside (Artifact `files`, `root` doc/chat-first)
and republishes it to the same link every time — **https://claude.ai/code/artifact/4d218257-5aac-4196-b8ca-c76b159a95ba**.
`bin/flushcheck.py` fails if it is not updated today or an item lacks a tag.
