# Open topics — the state clock, one block per topic

This file is rewritten in full by the flush at the end of every session (`/flush`). Each block
is the current truth for one topic and stands on its own: what is decided (ruling ids in the
private oracle store), what is open, where the work lives, and the next action. The event
clock is [HISTORY.md](HISTORY.md), whose entries are tagged with the topic ids below. A topic
is never deleted; when it closes its status says CLOSED and the block stays.

Fields every block carries: **Status · Decided · Open · Lives in · Next action · Updated.**

---

## T-1 · Ship the personal app to the first beta users

**Status:** ready for the owner's review before merge; deploying on the existing production
server, merge-first (his direction 2026-09-10).
**Decided:** one server for Pro, training and the chat app; old Pro diagrams stay pickle and
new rows are JSON in the same column [Oracle: R-0241]; the beta users are the app working
group of three clinicians [R-0079]; sign-in is passwordless with Face ID on a capable phone;
the sandbox is https at turin:8891 with a dev CA the phone trusts once.
**Open:** (1) his code review of the branch, and of the coach's prompt section (see T-2);
(2) continuous integration is red — ten web unit tests written before rounds 2–4, screenshot
goldens recorded only on macOS, nine older extraction tests that fail only when the whole
backend suite runs in one process; (3) Android never opened; (4) passkeys never tried on a
real https domain; (5) cluster quality on anyone else's record is unmeasured (T-6).
**Lives in:** btcopilot PR #136, fdserver PR #30; merge-risk review with the seven fixes
landed: doc/chat-first/MERGE_REVIEW.md (fix commit 9f1707a); review log
doc/chat-first/REVIEW_LOG.md; sandbox scripts /Users/patrick/worktrees/fd362-sandbox/.
**Next action:** the owner reviews; then merge, deploy, invite the three.
**Updated:** 2026-09-11.

## T-2 · The coach knows the clinical definitions, and we can measure it

**Status:** built on the sandbox, unreviewed by the owner, unmeasured.
**Decided:** the agent loop is the only writer and must carry the data model and clinical
definitions [R-0236]; placement rule — a rule the computer can test becomes a refusal in the
record's commit function, a field's meaning goes on the tool parameter, judgement goes in the
system prompt; the owner's own prompt-improvement process does not change: Claude Code is the
entry point and finds the instructions itself [R-0239]; IRR compares final records, not
per-statement deltas [R-0242].
**Open:** (1) the owner's review of the 168-line "What goes in the record" section in the
private prompt file (`git -C ~/theapp/fdserver/.claude/worktrees/FD-362 show HEAD~3 --
prompts/private_prompts.py` or the file's section by that title) — it is his clinical
content rewritten for the loop; the author's list of what was dropped is the newest entry in
doc/PROMPT_ENGINEERING_LOG.md; (2) the first measurement: the replay harness
(btcopilot/training/run_agent_f1.py) has nothing to score against until his two
conversations are coded as ground truth; (3) the induction instructions
(btcopilot/training/prompts/induction_agent.md, doc/PROMPT_OPTIMIZATION.md, the strategy doc)
have NOT yet been retargeted at the agent path — that is unbuilt; (4) whether the coach should
code SARF variables itself in conversation or leave them to a review pass — not ruled.
**Lives in:** btcopilot/personal/{record.py,toolbox.py,timeline.py}, training/run_agent_f1.py,
the private prompt section; his sandbox record re-coded once by the loop (session "Living
With Chronic Insomnia (re-coded)").
**Next action:** his prompt review; code his two conversations (T-3's coding mode, or by hand
in the editor); run the harness once.
**Updated:** 2026-09-11.

## T-3 · One app: Pro and Training as thin layers on the chat

**Status:** designed and ruled; nothing built yet.
**Decided:** one Vite app, features by licence, role and view; coding is documenting a case,
Pro on desktop; training is auditor/admin features on top [R-0237]; never a new view where an
existing surface can carry the addition [R-0243]; Pro adds cases (= the family switcher on the
account page), sessions (= the sessions sheet + "upload a recording" with a speaker-mapping
sheet), notes, and a wider desktop layout with the drawer pinned; coding is a read-only session
whose composer bar becomes "select a line, type an instruction, a cheap scribe records it"
(option D) with Done; coding protocol: no assignments, any coder any time, each Done joins the
pool and recomputes agreement, results visible only to contributors, blind until your own Done
[R-0242]; the coach's replay is one coding among others; the upload/speaker-mapping sheet is
approved as drawn.
**Open:** (1) the IRR review surface for five codings — four concepts await his pick
(https://claude.ai/code/artifact/a7637a73-8ebc-4166-8b5b-c6a3269aa973: A stave, B tally list,
C deck, D moderator; recommended B+C); (2) build order once picked: codings + scores tables,
endpoints, replay as a task, export of finished codings to the ground-truth files, the session
menu items, the coding mode, the pool statistics, the compare view; (3) the old SARF coding
page becomes a legacy link, deleted after re-coding [R-0238]; (4) desktop-first, phone later.
**Lives in:** plan https://claude.ai/code/artifact/7a033173-bff2-41ca-bbde-39385d4ab7f3;
layers https://claude.ai/code/artifact/daeb8856-4a5b-42d4-ab62-4c14bc3784b4; new surfaces
https://claude.ai/code/artifact/c5040b6a-75e3-47de-aba7-54aabbda69f4; mockups are drawn with
web/src/theme.css and the app's markup from here on (his rule 2026-09-10).
**Next action:** he picks the IRR review concept; then build in this PR.
**Updated:** 2026-09-11.

## T-4 · Existing records and conversations in the new app; wipe and re-code

**Status:** understood; one part fixed, the feature unbuilt.
**Decided:** previously released Personal app versions do not matter; existing diagrams and
discussions must work in the new app; colleagues' earlier sessions must be migrated in; "wipe
all coding and re-run the agent loop over the conversation" is a feature to build, like the
old training app's clear-and-re-extract.
**Open:** (1) old training transcripts are now kept out of the session list (fix landed) but
not yet importable on purpose — that is the upload/speaker-mapping path in T-3; (2) diagrams
carried over have no stored clusters until a turn writes an event; every diagram that ever had
a chat carries an "Assistant" person; items extracted but never committed on old diagrams are
unreachable (MERGE_REVIEW.md §4, should-fix); (3) after a wipe, chips in the old thread point
at deleted events and read as plain words — the re-code could re-link matches on kind, date
and people; (4) the by-hand re-code script is /Users/patrick/.claude/jobs/33d688bb/tmp/recode.py
(ephemeral) — the feature needs the same as a session-menu item.
**Lives in:** MERGE_REVIEW.md §4; run_agent_f1.replay.
**Next action:** build "re-code with the coach" in the session menu (T-3 build).
**Updated:** 2026-09-11.

## T-5 · Picture and interface rulings still open

**Status:** waiting on the owner; none block the beta.
**Decided:** the picked-moment words on the timeline (option A) [R-0235]; the about page
behind an i, ✕ in the arrow's place; one icon-button size [R-0234]; the card slides the whole
region; who·what words [T-2].
**Open:** (1) does the three-event cluster floor bind a grouping the user made himself
(review-log row 54); (2) the nodal ring on a dot, keep or drop; (3) thirteen NEEDS-OWNER rows
in UI_GAP.md; (4) the event editor's relationship fields and kind-based hiding, unbuilt;
(5) the felt call on the moves board.
**Lives in:** doc/chat-first/UI_GAP.md, REVIEW_LOG.md, STATE.md.
**Next action:** his rulings, in any order.
**Updated:** 2026-09-11.

## T-6 · Clusters by example

**Status:** waiting on examples he marks.
**Decided:** the rules make the candidates, the model names them and gives a reason
[R-0193, R-0194]; the floor is three events, enforced at the commit; user groupings under the
old floor are grandfathered.
**Open:** he has marked no examples yet; cluster quality on anyone else's record is unmeasured
until the coding loop (T-3) produces numbers.
**Lives in:** btcopilot/personal/clusters.py; the cluster prompt in the private prompt file.
**Next action:** none until T-3 yields coded conversations.
**Updated:** 2026-09-11.

## T-7 · The drawn family and auto-arrange

**Status:** off the path, on the list [R-0240].
**Decided:** family-structure data from the agent loop comes first; the drawn family arrives
later as one more picture level, auto-arranged first, hand layout after.
**Open:** whether auto-arrange works well enough on agent-loop data — untested.
**Lives in:** btcopilot/arrange/, the training app's SVG renderer, familydiagram plan doc
2026-05-02--auto-arrange-layout.md.
**Next action:** none until T-3 produces structure data.
**Updated:** 2026-09-11.

## T-8 · Isolation of the Personal package (option A)

**Status:** ruled, not built [R-0233].
**Decided:** a package boundary inside btcopilot — one adapter module is the only importer of
Pro code and the shared schema, held by a lint rule; a second service later; never a separate
repository.
**Open:** unbuilt; one to two days when scheduled.
**Lives in:** doc/chat-first/ISOLATION_OPTIONS.md.
**Next action:** after the beta is up.
**Updated:** 2026-09-11.

## T-9 · How sessions run (process)

**Status:** binding; extended 2026-09-09/10.
**Decided:** everything in doc/chat-first/HOW_THIS_PROJECT_WORKS.md plus: never coin a term;
estimate the work not the validation; build only on an explicit go — a question about an
estimate or a plan is part of the brainstorm; one place for content (artifact or message, not
both); mockups are drawn with the app's own stylesheet; sub-agents are token- and
model-optimised (judgement on Opus, mechanics on Sonnet/Haiku, smallest file set); the flush at
session end is `/flush` and is idempotent.
**Open:** none.
**Lives in:** doc/chat-first/HOW_THIS_PROJECT_WORKS.md; btcopilot/CLAUDE.md (owner corrections);
.claude/skills/flush/SKILL.md; bin/flushcheck.py.
**Next action:** none.
**Updated:** 2026-09-11.
