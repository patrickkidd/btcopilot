# Claude Code for Family Diagram (brainstorm, 2026-08-29)

Status: **concept ruled 2026-08-29.** Parallel epic to FD-341 (created 2026-08-30). Business model designed and **tabled** (numbers below stand until re-opened). Sessions: "FD-341 Vision & Plan" (Aug 25–26) and "Claude Code for Family Diagram" (Aug 28–30).

## 1. Vision (Patrick-confirmed)

**A coach who never forgets your family.** You talk (voice or text) the way you'd talk to someone trained in Bowen theory; it asks what a trained coach asks; the family record — structure + SARF timeline — is its memory: visible, touchable, growing for years. Conversation is central; the diagram is secondary visualization that keeps people focused on family instead of pop-psych framings; the timeline is the innovation on the tradition. Proactive (it notices and prompts) — defaulting to near zero notifications. Audience order: therapists on their own families / working group → clinicians' clients → general public. Chat has tool calls controlling everything in the app, NEXT TO a conventional UI users can tweak by hand; bidirectional reactivity.

**The insight moment (the product spec, Patrick's real example):** the coach connected dad+stepmom splitting over having kids with him moving into stepdad's chaotic household, which made him wonder whether his sleep symptom predated both. Three lanes on one time axis — a relationship, a household upheaval, his own symptom — is what would have let him see it himself. "It's so hard to get objective about your own functioning when you're in a wave."

## 2. Concept (ruled)

- **Chat + one picture above it.** Phone home = the conversation; a timeline picture pinned on top. Tap a reference in a coach message → picture slides to that period/lane. Tap-and-hold a point → edit. No tabs, no log mode, no extra surfaces.
- **Two clocks** (Foundation Capital context-graphs article; Koratana): chat = event clock (what was said and inferred at the time, right or wrong — never rewritten); record = state clock (current truth). Corrections change the record, not the log. Cards/pictures render from current state.
- **Picture = multi-lane timeline**: lanes keyed ONLY by person / couple / household (family-focus rule); per-person step line for one variable from that person's own up/down deltas (the existing cumulative sum, split by person — today it mixes everyone); stamped markers for relationship/move events; approximate dates drawn as bands (dateCertainty exists, never rendered); coach can place a shaded span. "What else was happening within N weeks on any lane" becomes a deterministic query/tool (the Aug-25 coach noticing worked only because the whole transcript was in context; Havstad 4–12wk lag > cluster prompt's 3wk window).
- **No diagram drawn at first.** Structure still recorded (people F1 ~0.92). Diagram returns later (triangles need a visual — extraction knows triangles, the coach's questions don't yet). Learn tab's inferred trends are dead; real dated points via chat replace them.
- **Encoding note:** "split positions" = away moves on the bond (+ Defined-self on his stepmother's side; his father capitulates) until a better coding exists. Patrick's sleep-shift was speculation, not an identified shift; his journal file (months of dated entries) is the real data source for the first picture — run through extraction into a COPY of 1924.

## 3. What the record says about the pivot (adversarially checked, 22-agent run)

Holds for **structure**, fails for the **timeline**: of 17 real-family failures — 6 guard-catchable, 4 need one question, 6 semantic misreads all caught by a human *looking at the drawing* (the "users don't review" ruling was about cards, not drawings), 1 display. Per-turn narrative harvesting still loses 2× (Feb 24); shift/SARF extraction stays batch, unimproved ("stop TUNING extraction," not "stop engineering it"). ~45% of ~6.1k extraction lines reusable as tools/guards/manual; ~20% is prompt IP = the manual; ~500 lines post-hoc repair + K-run consensus + wipe-and-regenerate die. Cheapest pre-agent test: 5 commit-time guards on the existing path, rerun real rebuild on 1924 ×3 vs the 32 assertions (~1–2 days, <$5). Caveat: Jul-21 dup findings possibly contaminated, never re-run clean; Jun real-rebuild failures stand.

## 4. Architecture (panel verdict, corrected by refuters)

Keep Flask/Celery/Postgres/Redis. Diagram = JSON document + append-only command log; ONE Python module mutates; browser and agent are both clients of one endpoint. Agent loop in a worker, streams via Redis→SSE. Front end = one Vite/TS SVG page, PWA. Release = tag → one image → compose pull. Refuter corrections: **patches not full-doc** (500p/5k-event diagram = 1.6–3MB JSON, not 200KB) + small client reducer for optimistic drags; **layout engine cannot hold pinned people** (filter, not constraint — constrained placement is ~1–2wk new work, the May-4 deferral again); per-turn cost 4–10× naive estimate unless neighborhood reads + caching; SSE needs an async worker + a dedicated queue; migration gate = "positions exact (53/53 clinic files at 0px), count differences explained" (10/1998 prod rows unloadable in old code too; Scene.read synthesizes parents). Undo inverses need compare-and-set. Hard cutover: Pro goes export-only on migration day. Secrets committed in compose → rotate. 9–13 focused wk to phone+desktop parity; first headless milestone ~2wk.

**2026 tooling (sourced):** routine — one web codebase desktop+phone, iOS 26 installs home-screen web apps by default, push (not EU), vendor streaming STT, git-push deploy. NOT ironed out — browser speech API dead in installed iOS PWA (mic→vendor STT socket), no background mic/audio, iOS evicts cache after 7d (server is the memory), Capacitor shell = Xcode+review+4.2 risk (only when EU-push/store needed), agents blind to visual/touch QA (screenshot loop + human thumbs stay). PhoneGap's descendant = Capacitor; not needed yet.

## 5. PMF path (ruled)

1. Patrick talks to the existing Personal app now (return loop never lived by anyone); journal file → extraction → copy of 1924 → data for the picture.
2. **First build: new web page** (chat bottom, picture top) against EXISTING backend endpoints — second client, no migration/command-log/agent required. Auth wrinkle: personal/* uses HMAC; page uses browser session (≈1 day). Seed of the new app; nothing thrown away; old apps untouched.
3. Corrections through chat land in the same page (~3–5wk; independent of picture, but picture drives what gets noticed → corrected).
4. Working group after the return path is fenced.

## 6. Business model (designed, TABLED 2026-08-30 — do not re-open until PMF signal)

One flat plan $29/mo ($290/yr), Pro bundled ("Pro + $9"), web Stripe (no Apple cut), 200 turns/30d + 40/day cap, $12/100-turn prepaid top-up (never arrears). Founders: first 20 @ $19 locked 12mo, card up front. Sonnet-class in the loop ($0.05/turn cached; heavy-at-cap ~$14/mo cost) — Opus-class sinks it (heavy ~$50); a Sonnet-tools/Opus-reply split ≈ $0.08/turn. Fixed w/ BAA hosting ~$150/mo; break-even 7 medium users. Conditions (none exist): Sonnet coaching quality untested (only tier comparison on record: Gemini 0/3 vs Opus 3/3 stonewalling); prompt caching unwired; per-account token logging absent. Concedes: general public ($29 vs $6–13 consumer band; Woebot D2C died) and clinician client-seats (~$59+$8/seat, only after month-3 retention). Comps + prices as of 2026-08-29 in session record.

## 7. Open questions

- Sonnet-class as the coaching voice: test before any pricing/build commitment.
- Does 1924 contain the example's events as dated items? (Never checked; journal import answers it.)
- Live vs frozen old cards (lean: live). EU push / store presence year one? (forces Capacitor now).
- Coach elicitation of dated shifts + triangles (done-rule omits both; unmeasured) — queued topic.
- Migration/cutover timing; drag = override vs constraint; feedback-loop "singularity" — queued topics.
