# Chat-first rebuild — HISTORY (the event clock)

What happened, in order, with the reasoning — so no future session re-litigates a
settled question. Append-only: add dated entries at the bottom; never rewrite the past.
Companion: [STATE.md](STATE.md) (the current system of record).

Artifacts referenced throughout (private to Patrick's account):
- Drawability ruling page: https://claude.ai/code/artifact/b0209a84-03ee-4b36-80ae-8624bd0e88dc
- "Three Ways to Ask" phone mockups: https://claude.ai/code/artifact/a20195e0-2310-4308-8fd5-1dc74ac28dc9
- "Flowing Through It" storyboard: https://claude.ai/code/artifact/fad00c92-685e-4c7d-ba1d-2e18d999d623
- FD-360 draft PR: https://github.com/patrickkidd/btcopilot/pull/133

## 2026-08-25/26 — prior session ("FD-341 Vision & Plan"), inherited context

Returning from a ~5-week break, Patrick reconstructed project state adversarially.
Rulings that carried into this work: MVP done-condition = a user returns and chats
over weeks and the diagram improves through chat (not the clinician-in-Pro loop);
epic FD-341 created (5 children: FD-336 embed → FD-339 conversational editing →
FD-351 testers → FD-352 timeline trend → FD-353 SARF re-baseline); "architecture B" =
one authoring tool surface with full CRUD used by an agent for user-authorized edits,
narrative extraction stays batch until a measured spike says otherwise (the Feb-24
result — per-turn extraction lost 2x to batch — puts the burden of proof on agentic
extraction); a reference-manual tool for the agent (SARF model, app usage, concepts);
tier table decides ask-first vs auto-apply, the model never picks the write path.

## 2026-08-28 — the pivot brainstorm ("Claude Code for Family Diagram")

Patrick's framing: chat as the main UI for everything (intake, editing, learning);
maybe rebuild the Pro app ground-up, agentic-dev-first, leaving the PyQt5 tech debt
behind; business model like Claude Code (subscription, managed usage). Inspiration:
his Micron pattern — users describe what they want, an agent with a tool surface and
a built-in reference manual does the rest; the UI altitude rises to the user's
subject-matter expertise. His user base is deeply non-technical.

Motivations in his words: an "architectural singularity where all the feedback loops
start pointing in the same direction" (usage → data → ground truth → product) instead
of years of coding-training and pulling teeth; "instantly get users addicted" as an
interactive experience; ~$9K slowly-declining ARR explicitly NOT a present concern;
this is not his day job for a while (capacity constraint). Ruled same day:
manual diagram tweaking stays — the chat has tool calls to control EVERYTHING in the
app with full bidirectional reactivity between chat and UI; old diagrams migrate
(the data model — SARF timeline + structural invariants — stays; the UI does not).
Later that arc: anti-overfit ruling — it must NOT become a log app; no surfaces
overfitted to individual examples; chat + the agentic loop stay the focus.

Verdict (this session's first adversarial research run): "Claude Code for FD" is an
ENGINE bet, not an app bet. What makes Claude Code work is a headless, verifiable
substrate driven through tools. Ruling: build the tool surface / guards / manual /
layout as a headless engine; any front end is a client. Don't decide the rebuild on
zero retention evidence.

## 2026-08-28 — research: does the interactive loop remove the extraction problem?

22-agent adversarial run (4 evidence readers, 3 judges, synthesis, refuters on every
claim). Verdict: **holds for family structure, fails for the timeline** (judges
35–55% overall; near-certain for people/bonds/parents, near-zero for dated shifts/SARF).
- Of 17 recorded real-family failures on Patrick's own diagram: 6 guard-catchable,
  4 need one clarifying question, 6 semantic misreads — all six caught by a human
  LOOKING AT THE DRAWING (the "users don't review" ruling was about cards, not
  drawings), 1 display-only.
- Per-turn narrative harvesting lost 2x to batch (Feb 24) with committed state in
  context; nothing since reverses it. Shift/SARF extraction stays batch.
- Prompt tuning on batch is at zero marginal return (three induction rounds kept ≤1
  change each). The right sentence: "stop TUNING extraction," not "stop engineering it."
- Reusable: ~45% of ~6,100 extraction lines (commit primitive, merge, resolution
  rules, guards catalog, connectivity, coverage engine); ~20% is prompt IP that reads
  as a manual; dies for sure: ~500 lines post-hoc repair, K-run consensus,
  wipe-and-regenerate.
- Cheapest pre-agent experiment (never run): five commit-time guards on the existing
  path, rerun the real rebuild on his diagram 3x against the 32 assertions (~1–2 days).

## 2026-08-29 — architecture panel

22 agents (2 ground readers, 4 biased proposals, 3 judges, synthesis, 12 refuters).
Shape that survived: keep Flask/Celery/Postgres/Redis; a diagram becomes a JSON
document + append-only command log; ONE Python module mutates; browser and agent are
both clients of one endpoint; agent loop in a worker streaming via Redis→SSE; front
end = one Vite/TypeScript SVG page served by Flask, installed as a PWA; release
collapses to tag → one image → compose pull. 9–13 focused weeks to phone+desktop
parity; first headless milestone ~2 weeks.

Refuters killed the synthesis's numbers, not its shape — corrections are binding:
- Full-document-per-update is out: 500 people/5k events ≈ 1.6–3 MB JSON. Server sends
  patches; client keeps a small reducer for optimistic drags (else 300–800 ms drag lag).
- The layout engine cannot hold pinned people (Pro's "arrange selection" is a filter,
  not a constraint). Constrained placement is real new work (~1–2 wk) — the same item
  deferred since May.
- A read-before-write agent turn is 3+ model calls and the mutable record can't be
  cached across turns: realistic input $0.20–0.50/turn Opus-class; viable Sonnet-class.
  Consequence: compact neighborhood reads, never the whole document.
- SSE needs an async worker (each tab pins a thread on today's config) and agent turns
  need their own queue.
- Migration gate: "positions exact (53/53 clinic files at 0 px), count differences
  explained" — 100%-vs-old-reader is undefined (10/1998 prod rows don't load in the
  old code either; the old reader synthesizes parents on read).
- Per-turn undo inverses need compare-and-set or undoing an agent turn can clobber a
  later human edit.
- Hard cutover: the day the server writes JSON, the old Pro app is export-only. A
  dual-format shim was rejected as silent divergence.
- Found in passing: API keys committed in the compose file → rotation belongs to the
  release collapse.

## 2026-08-29/30 — concept panel and the vision

One sentence (Patrick-confirmed): **"A coach who never forgets your family."**
Conversation is central; the picture is secondary visualization that keeps people
focused on family instead of pop-psych framings; the timeline is his innovation on
the tradition; proactive, near-zero notification default; audiences in order:
therapists on their own families / working group → clinicians' clients → public.

The insight moment is the product spec (his real example): the coach connected his
father and stepmother splitting over having kids with him moving into his stepfather's
chaotic household — and made him wonder whether his sleep symptom predated both.
Three lanes on one time axis is what would let him SEE it himself.

Two-clocks framing (from the Foundation Capital context-graphs article he referenced,
already applied once in a March Plan-tab doc): chat = event clock (what was said and
inferred at the time, never rewritten); record = state clock (current truth).
Corrections change the record, not the log. This same regime now governs project docs.

Tooling reality check (web-researched, dated 2025–26): one web codebase for desktop +
phone is routine; iOS 26 opens home-screen adds as web apps by default; push works
installed (EU quirk reversed in 2024); browser speech API is dead inside an installed
iOS PWA (voice = mic → vendor streaming STT); no background mic; ~7-day cache
eviction (server is the memory); Capacitor is PhoneGap's living descendant and is a
packaging step around the same code, only when store presence / locked-screen
recording / a hostile Apple move forces it; OTA web-payload swaps are Apple-legal for
interpreted code. Cheapest BAA-able hosting ~$99/mo (Fly) or self-managed big-cloud VM.

## 2026-08-30 — tooling plan and business model (both adversarially checked)

Tooling (13 agents): tooling is NOT separate — admin/eval/debug live in the product
repo behind role gates (the training app already proves the pattern). What agentic dev
changes: every task ships with a sub-minute check the agent runs itself; review by
evidence not diffs; LLM calls stubbed to recorded fixtures in the inner loop; prompt
changes become judged PRs using the training app's own GT machinery; repo layout
serves agent context. Per-phase adds are minimal and listed in STATE; a hard
do-not-adopt list exists (session replay tops it: masked replay of a chat shows
nothing, unmasked is PHI).

Business model (19 agents; **designed and TABLED** by Patrick — do not reopen until
PMF signal): one flat "Coach" plan $29/mo ($290/yr) with Pro bundled, web Stripe (no
Apple cut), 200 turns/30d + 40/day cap, $12/100-turn prepaid top-up (never arrears);
first 20 founders $19 locked 12 mo, card up front. Economics only work Sonnet-class
in the loop (~$0.05/turn cached; heavy-at-cap ≈ $14/mo cost; Opus-class heavy ≈ $50
sinks it; a Sonnet-tools/Opus-reply split ≈ $0.08/turn). Fixed ≈ $150/mo with BAA
hosting; break-even ≈ 7 medium users. Standing conditions, none built: Sonnet
coaching quality untested (only tier comparison on record: Gemini 0/3 vs Opus 3/3 on
stonewalling), prompt caching unwired, per-account token logging absent. Concedes the
general public ($29 vs the $6–13 consumer band) and clinician client-seats until
month-3 retention.

PWA install evidence (researched): a genuine evidence desert — nobody publishes
add-to-home-screen funnels; the one "85% with a guided page" number is vendor
self-report. At n=20 it's an onboarding-call agenda item; at n=200 it's the
top-of-funnel metric to instrument in-house. Therapist credibility risk ≈ zero (their
EHRs are browser apps).

Login/onboarding (ruled): passwordless everywhere. First touch = personalized QR/link
that lands already-authenticated → guided add-to-home-screen → months-long sessions →
passkey/Face ID upgrade. Recovery = 6-digit emailed code typed into the app (a link
would open the wrong browser). Passwordless login IS signup, so self-serve and
Stripe-checkout charging bolt onto the same flow later. Android is the easy platform
(real install prompt).

## 2026-08-30/31 — FD-359/360/361 and the build

Parallel epic created on Patrick's yes (kept separate from FD-341 as the June plan of
record): FD-359 "Chat-first web app — a coach who never forgets your family";
FD-360 "Web page: chat + timeline picture against the existing backend";
FD-361 "Corrections through chat in the web page". The Pro-embed (FD-336) is
superseded as the first chat surface by the web page.

FD-360 built by an orchestrator/worker pair (workstream skill; worker on a cheaper
implementation model per the model policy). Delivered on PR #133 (draft): a
/companion Flask blueprint — session-cookie auth by reusing the training-app
authenticator in its own before_request (zero changes to the HMAC auth path, verified
by test), CSRF on mutating routes (repo-wide CSRF was a no-op), chat through the real
coach pipeline, server-computed timeline JSON per the Drawability rules, vanilla-JS
SVG strip, seed module, 25 new tests (suite 852 green). The worker found the sibling
Qt app's cumulative-sum mixes all people into one series — the new page has a
regression test proving it does NOT reproduce that. Verification loop worked:
orchestrator independently reproduced auth/CSRF/DOM claims and bounced a wrong
evidence screenshot; the worker pushed back and found the real staleness bug beneath.

**Data-exposure incident** (event worth remembering): the worker committed 7
screenshots of Patrick's real record plus prose naming family members to the PUBLIC
btcopilot repo on the FD-360 branch (my instruction caused it — "screenshot and push"
without connecting repo visibility). Frozen by the verifier, scrubbed non-destructively
(commit 234edbe; alias table moved out of code into an ephemeral CLI flag), verified
clean by independent grep. Git history still holds the data in exactly two commits
(f55c5b0, 35dd13b) pending Patrick's purge decision (recommended: delete remote
branch + PR, re-push clean, reopen). The audit also surfaced PRE-EXISTING personal
content on public master (a test-fixture name, names in the decision log, IRR meeting
transcripts quoting Patrick discussing his wife) — his separate call, untouched.
New standing rule: real-record evidence stays on the machine, referenced by path.

Patrick's first real walk of the page produced five findings, all now canonical in
DRAWABILITY.md: the expanded view was illegible on real sparse data ("random boxes on
a giant rectangle" — it assumed density that real records don't have); dead
undated-shelf chips (now: tap speaks the fact + prefills the chat); lane-filter
buttons killed outright ("a data project no one wants"); horizontal pan/zoom is
mandatory for multigenerational spans; question marks must be visibly anchored to
their items. An era-compression redesign (linear inside data-density eras, worded
"N quiet years" bridges, era-fit zoom) was built when a hold order crossed it
mid-flight, then REVERTED to honor mockups-first; it remains recoverable at commit
35dd13b — which is ALSO one of the two contaminated commits, so a history purge
deletes that work too (it would need re-implementing from its spec in this doc).

## 2026-08-31 — drawability ruled on real data

Patrick's journal (78 points, 14 months, 96% day-certain) and his two coaching-chat
transcripts (84 datable moments, 1957–2026, mostly year-grade) were hand-structured by
agents; a clinical case supplied contrast. The ruling page drew every candidate rule
against real data; Patrick ruled the five rules + the question language now canonical
in [doc/DRAWABILITY.md](../DRAWABILITY.md). Load-bearing findings: certainty is a
property of WHEN a fact was captured (journaled-now = day-sharp; remembered decades =
year bands) — so long-horizon returning chat is also the data-quality strategy;
his real record draws multi-decade lines (functioning, relationship) with an honest
12-year symptom hole; his remembered insight-moment events exist at year-grade and
their ordering IS drawable (bands don't touch); the transcripts do NOT contain the
father/stepmother split-over-kids — his flagship example came from a conversation not
in the July snapshot (or memory differs); nobody's committed record contained ANY
events despite 216 statements of chat (extraction results never committed in prod).

The clinical teaching behind those rules (his words, the session's strongest
statement of what the timeline is FOR): there are NO absolute values for S/A/R/F —
only relative shifts, captured in episodic clusters (already detected "somewhat well"
by his impression); baseline vs episodic levels are EMERGENT in the dataset; both
human and AI coaching sample with a bias toward the periods where emotional process
was running; a historical intake yields 3–5 remembered periods across the years, and
the conversation exists to enable that remembering; undated things go to a coach
backlog — never guess a position. His counterexample that sets the bar: a subject
who took on more and more responsibility over 5–10 years while anxiety climbed —
visible ONLY once everything sat on a timeline, "a major insight for that person."
Related post-mortem (his words): the Learn tab "concept was good but I could never
get it to work — the data didn't give clear trends and inferring never worked"; his
diagnosis is that an unclear minimum-drawable standard is why the old timeline cards
failed, hence "this thing needs to only show meaningful patterns." SARF
coding-by-example on his own case: the split-over-having-kids codes as away moves for
now, likely plus a Defined-self on the stepmother's side.

Sequence fact, stated plainly: an early version of the ruling page was built from a
clinical case mistakenly treated as his diagram; when he ordered that data completely
ignored, the page was rebuilt entirely from his own record and republished at the
same link — the ruled rules stand on HIS data; the case data was discarded.

Counterweight on the coach (his felt sense, recorded so no session rebuilds a prompt
he considers good): "I am already comfortable with the conversational flow and how it
covers the required information (I worked a lot on that, I assume it transfers
directly with zero loss here)" — the elicitation items are refinements, not a rebuild.
Triangles, with his cautions: the R variable and event attributes map onto triangle
shifts with inside/outside positions by triangle direction (do not ignore); triangles
are a core "molecule" but not the only thing, and "we don't have enough data to
understand when to prioritize each"; extraction prompts describe triangles and F1s
exist (his statement) — the identified gap is only that the COACH never asks
triangle-shaped questions.

UI shape ruled from "Three Ways to Ask" (three interactive-feel mockups from his
data): conversation drives everything (question-first variant DEAD — "no one is going
to like a questionnaire"); picture always-on and strip-small; questions are quiet
amber marks; the coach aims the picture with an inline chip; undated shelf behind a
tap. He later named tracked unknowns THE engagement engine: "a really big deal …
automatically engaging and automatically propells the conversation forward" — the
question marks are the product thesis, not decoration. The cartoon rule recorded: the product exists to produce one or two
brain-rearranging correlations, not a dataset; the two real instances on record are
the acceptance test. Coverage serves only (a) better coach questions and (b) the
timeline's own correlations.

Coach elicitation (designed, PENDING Patrick's clinical sign-off — not landed):
the conversational prompt has ZERO triangle questions (extraction prompts describe
triangles and F1s exist — his statement; the gap is what never gets SAID in
conversation; see his triangle cautions above), and its data-collection
done-rule omits dated shifts and triangles. Designed as small additive prompt edits
(who-else-was-in-it question shapes, a year-BEFORE probe, rotate one SARF dimension
per time anchor, two done-rule criteria) plus a measurement instrument:
planted-fact synthetic personas scored by SCANNING THE TRANSCRIPT for the planted
facts (never through extraction, which drops ~half of shift events that WERE said),
with the KPI "did the session move a lane toward drawable." Two blockers found by
refuters: the synthetic client is broken on record (canned evasions ~50–60% of
turns — must reveal planted facts when asked before any coach score means anything),
and the baseline run doubles as the TABLED Sonnet-vs-Opus coaching-quality test.
Budget ruling (Patrick, "sounds good"): in-story follow-ups (dating, year-before,
who-else, one-dimension-per-anchor) are EXEMPT from the ~1-targeted-question-per-
session budget, which caps only out-of-flow clarification questions.

Also ruled in this stretch: NO modes — one agent, registers (coaching, app help via
the manual tool, corrections, journaling) routed from context, never user-visible
mode switches; sessions accumulate and the picture is the index back into them
(every fact carries its source conversation); no progress bar — "what more data
buys" appears in place as the question marks.

Storyboard ("Flowing Through It", 7 frames, six months of elapsed time): Patrick
loved the proactive messaging and the "ask while it's calm" idea (both now A/B test
candidates); confirmed only frame-4-style notifications are app-initiated. The
resting-strip mark vocabulary FAILED his cold read ("no one will know what those
boxes mean") → at-rest vocabulary rule: line, dots, amber ? — nothing else at strip
scale; every mark speaks a plain sentence on tap; no legends ever. Styling must be
tokens-only for theme A/B testing (semantics stable across themes: teal=data,
amber=asking).

## 2026-09-01 — the cart-before-horse correction and the corpus pivot

An era-compression bake-off and then an interactive prototype (proto.html: "Chapter
Shelf" + "Quiet Threads", from a 19-agent creative-adversarial run over six visual
metaphors) were built BEFORE analyzing the real data. Patrick rejected the prototype
outright ("total garbage") and named the process error: "you are supposed to be
analyzing the code base to derive the UI ideas" — mine the cases AND the existing
app's visual vocabulary/specs (he separately said the current diagram/timeline layout
concept "is not bad"); mockups from real data before building; his rulings gate every
phase. The creative run's cross-cutting findings survive as hypotheses (uncertainty
lives in the mark's body as time-extent, never blur/opacity/size; every position
channel single-tenant; silence is a self-captioning object; words are the most robust
channel; never jitter x; a dedicated simultaneity mark; insight figures persist as
named objects; elderly-vision floors are spec) — but nothing visual is derived again
until the corpus analysis is ratified.

Corpus: prod diagrams are NOT the corpus. The real corpus is his personal clinical
cases (iCloud Clinic Cases, 61 bundles) — sensitive client material. BAA status:
LLM-provider BAAs already EXIST ('don't worry about that'); the ANTHROPIC BAA is the
pending one — until it lands, clinical content is used without exposing data. Content-blind protocol invented and held: only
scripts touch the files; output is whitelisted structure (anon ids, gender, decimal
years, certainty flags, kind enums, direction enums, text byte-lengths); free-text
fields are never extracted at all; anonymization is one-way (no mapping file except
PRIVATE_case_mapping.md, generated for his eyes without filenames entering model
context); the corpus lives in ~/fd-corpus (never in any repo) with a no-data
rebuild.py that regenerates and self-verifies everything from the diagrams folder.

Census bugs (his eyeballing caught them: three "zero-event" cases visibly full):
(1) the older pickle schema dates via QDateTime and the year-extractor called a
QDate-only method — every dated event in older-schema files silently became None;
(2) dated events live in FIVE homes (person.events; birthEvent/deathEvent/
adoptedEvent; marriage.events; relationship symbols' start/end events) and only one
was read; (3) some relationship-symbol kinds were missing from the whitelist.
Also discovered on events: an explicit `nodal` flag and a FIFTH variable,
`differentiation`. Findings that died with the fix: "9/61 zero-date structural
genograms" (→ 1/61); case_29 went 0 → 172 dated events and is now the richest case;
"thin sketch is modal" weakened (median 23 dated events over 81 years); the
two-populations split survives but overstated (42x, not 176x). Survived: direction
tagging in 21% of his cases (4.6% in prod — he uses it ~4.6x more); uncertainty is a
right-skewed spread, not a wall; he dates marriages 2–3x more than the prod
population. Prod side barely moved; the 104-row candidates list (email + id, floor
≥40 dated events, UNRANKED by his order) stands.

Rubric discipline (his corrections, now standing): the nuance doctrine is a standing
epistemic constraint on ALL inference over this data, not a rubric rule — it looks
simple, is extremely nuanced, and training priors do not know how it works;
volume ≠ quality; no rubric or
ranking is inferred without him — he rules by example and by correcting proposed
values; structural counts may be shown only as "volume (not quality)". Max-effort
model spend happens ONLY on the filtered corpus (two launched runs violating this
were killed), in his ruled order: **filter (his rulings) → A: a max-effort document
explaining the nature of this data → B: max-effort, model-optimized generation of
visual-representation choices → hand off.** Scaffold-vs-active ratified as the
mechanical viability marker: a case's diagnostic period begins at its first event
carrying a nodal flag or any variable value; early births before that are age/
generation scaffolding that does NOT factor into SARF evaluation; active-event count
is the signal. His teachings accumulate verbatim-close in ~/fd-corpus/OWNER_RULINGS.md.

The active/scaffold re-cut then landed and reshaped the picture again: on the active
basis the tiers are 11 cases at 30+ active events, 13 at 10–29, **28 at zero active**
(nearly half the corpus is scaffold end-to-end by the ratified marker — no event ever
carries a nodal flag or a variable; caveat: this may partly reflect coding style,
since variables/flags appear in only ~21% of cases — his eyeball decides), 9 out.
The worst volume illusion at the time of that report: one case with 51 dated
events and 0 active (figures drift as extraction improves — index.json is always
authoritative; never trust counts written in docs). The prod
stress case (diagram 9) is 719 dated / 0 active. The corpus thereby self-sorted into
his two planned subsets: cases WITH active events are the FUNCTION-subset candidates;
zero-active-but-structure-rich cases are the STRUCTURE-subset candidates.

Also ruled in this stretch: when the agentic loop is implemented, the app self-files
friction reports — "when the model detects user friction it automatically posts it,
even in the background" — alongside users asking the chat how to use the app from the
built-in reference manual. And the human-oracle canonicalization ruling that created
the oracle store itself: his direction is among the most valuable inputs to the whole
agentic development process and "must be canonicalized and continually maintained
just like everything else" — instituted per his BKM as a store in the
PRIVATE fdserver repo (doc/oracle/: SPEC + rulings index + evidence — the whole
store is IP; the public repo carries only the regime and R-id citations; no raw
transcripts anywhere). The initial mined set (R-0001..R-0064) is a proposed
consolidation awaiting his feature-grouped ratification pass per SPEC §10.

## FUNCTION-subset session: the active basis is itself an illusion

Recomputed from index.json and the case files 2026-09-01 (Session 1 opening step).
The active-basis tiers reproduce exactly as recorded (11 / 13 / 4 / 28 zero-active
with people / 5 blank), so the recorded numbers are current. But reading rebuild.py's
`active_scaffold_split` closes a gap the earlier reports left open: **active-event
count measures the LENGTH OF THE DIAGNOSTIC PERIOD, not the amount of function he
actually marked.** Everything dated at or after the first marker-bearing point counts
as active, whether or not that point carries anything itself. So the tier ranking is a
period ranking.

Counting the points that actually carry a nodal flag or a non-"none" variable
direction gives a much thinner picture: **6 cases have 10 or more marked points, 15
have 5 or more, and 33 of the 61 files have none at all.** The ranking reorders
substantially against the active tiers — the case ranked second by active period
(125 active) has 13 marked points and all of them are bare nodal flags with no
variable value, while the case ranked fifth by period carries the second-densest
variable tagging in the corpus. Two cases sitting in the top tier by period carry
three marked points each.

Three further facts from the same pass:

- **The corpus has 61 files but not 61 families.** Two file pairs are identical across
  every extracted field (people, events, pair-bonds, relationship symbols, span), and
  a third pair shares its people and nearly all its events while differing in
  pair-bond completeness. One of the identical pairs sits inside the top tier and the
  other inside the second tier, so both tiers are inflated by one. Five further files
  are empty and are byte-identical to each other for that reason.
- **The differentiation variable is never used anywhere in the corpus.** Of the five
  SARF directions, symptom is tagged most, then anxiety, then functioning, with
  relationship rare and differentiation at zero.
- **Every marked point is dated.** Across all cases there is not one marker-bearing
  point without a year, which means the function signal is entirely available to
  timeline work with no undated shelf problem on this side.

Marked points are also sparse per person and clustered in time — the densest case
spreads 33 marks over 9 people and 30 years, and several cases put all their marks
on one or two people inside a decade. That matches his clinical teaching about
episodic clusters rather than continuous tracks, and it is the shape phase A must
account for.

These are computed facts, not rulings. The subset itself remains unruled: the tier
lists, the marker-count reordering, the four 1-9-active cases, the duplicate pairs,
and the zero-active-may-be-coding-style question all wait on Patrick.

## Notability thread opens: handwritten cases join the corpus plan

Patrick recalled a body of handwritten case diagrams in Notability — cases he saw
while developing the app, existing only in handwriting; many have good structure in
the app but sparse functioning timelines. He wants them interpreted and normalized
into the corpus for one source of truth, and cannot reach them on the Mac.

Diagnosis (verified on his machine 2026-09-01): the installed Notability for Mac is
the new web-wrapper version that syncs through Notability's OWN cloud account, not
iCloud Drive — both old iCloud containers on disk exist but are EMPTY. That is why
Finder shows nothing; the notes live server-side with Notability, reachable from the
iPad and (if logged in) the new Mac app. Nothing is wrong with his files.

Proposed pipeline (unruled): bulk-export all notes as PDF via Notability's
auto-backup feature (one setting on the iPad backs up everything as PDF to a cloud
drive folder continuously) → land raw PDFs under ~/fd-corpus/notability/ (never in a
repo) → interpretation by a BAA-covered multimodal model (OpenAI or Gemini — NOT
Claude; content-blind protocol continues to bind Claude until the Anthropic BAA) —
Notability's own OCR is handwriting-to-text and blind to diagram semantics, so it is
not the tool → a small bake-off on a few diagrams, scored by Patrick, picks the
model → extraction to a normalized format decided with Patrick (candidate: the
existing anonymized corpus schema, so hand cases become case_NN files alongside the
app-derived ones) → Claude works only with the anonymized output, same as today.

## Notability thread ruled: .fd files are the single source of truth

Patrick redirected the pipeline design and it got simpler. The app already stores a
unique random alias per person and substitutes name+nickname with the alias in all
event/person notes text behind the hide-names toggle (verified in the scene code).
Ruling: handwritten PDFs are interpreted ONCE by a BAA provider and their content is
entered INTO the .fd diagram files (mostly merging timeline events into diagrams
that already carry the structure); he reviews by opening diagrams with aliases on;
a translator (extension of rebuild.py) then emits the anonymous corpus from any
diagram — today's allowlist PLUS alias-scrubbed text and parent-child links (which
also removes the STRUCTURE-session whitelist blocker). No ledger, no second schema.
Explicit constraint: no anonymization rabbit hole — the only guard on the scrubber's
known gap (surnames alone, places, misspelled handwritten names pass through) is a
mechanical name-list scan with quarantine for his eyeball. Open approvals: that
guard, and the import script that writes interpreted events into .fd files (its
format doubles as the bake-off output format). The visualization prototype remains
gated ONLY on the FUNCTION-subset ruling, not on this thread.

Correction, same day: Patrick killed the anonymization arm entirely — no translator,
no scrub guard; the corpus's rare inferences go to BAA providers on raw content.
The Notability scope narrowed to: interpret PDFs → NEW .fd files (originals
preserved) → profile them like the app cases → eyeball viability for a functioning
timeline. Focus stays on finishing the corpus so the visualization prototype work
can resume.

Addendum: Patrick ruled the notes→diagram pipeline is reusable product technology —
professionals will walk the same method (scan handwritten notes to PDF → diagram
file). The core (interpretation prompt, output schema, .fd writer, confidence for
human review) is to be built and documented as a reusable module, with the bake-off
findings saved as part of the method; user-facing surfaces deferred until app
surfaces are chosen.
