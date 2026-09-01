# Chat-first rebuild — kickoff briefs for the next sessions

Each brief is self-contained. Both sessions start from this worktree
(/Users/patrick/worktrees/fall-2026-direction/btcopilot, branch `fall-2026-direction`),
read [STATE.md](STATE.md) FIRST, and obey the standing
rules below. Patrick starts them; they do not start themselves.

## Standing rules that bind both sessions

1. **Patrick's warning is law**: this data looks simple and is extremely nuanced;
   general genogram/therapy priors do not apply. Propose; he corrects. Never present
   an inferred ranking or rubric as settled. **The human oracle is the binding input to all agentic development**: the store
   (SPEC + rulings + evidence) lives in the PRIVATE fdserver repo at doc/oracle/;
   cite rulings by id; capture his new statements there immediately; newest wins
   via SUPERSEDED chains.
2. **Content-blind protocol** until the Anthropic BAA exists: only whitelisted
   structure from ~/fd-corpus/clinic/ enters model context; free text never; the
   corpus never enters a repo; PRIVATE_case_mapping.md is for his eyes only and its
   filenames never enter model context.
3. **Max effort only on the filtered set**, after his tier rulings. Ruled order:
   filter → A (nature-of-data document) → B (visual choices) → build. Nothing visual
   before A is ratified.
4. Communication: plain words, his terms, no invented vocabulary; decision questions
   self-contained in ONE numbered list with inline examples; no interim sub-agent
   chatter — one consolidated delivery per work unit; TLDR first.
5. **PII rule**: real user emails (prod_candidates.csv), case filenames, prod
   identifiers, and corpus values never appear in repo docs or commits; reference
   cases as case_NN only. Corpus numbers are never trusted from docs — recompute from
   ~/fd-corpus/clinic/index.json.
6. Two-clocks upkeep: append what happens to HISTORY.md, revise STATE.md, and add
   his new teachings to OWNER_RULINGS.md as they occur.

## Session 1 — corpus subset for FUNCTION

**Goal**: needle through the anonymized corpus with Patrick to define the subset
useful for timeline-data inference toward visualizing biological family-system
FUNCTION (the SARF process over time), then run phase A on it.

**Inputs**: ~/fd-corpus/clinic/index.json (volume + active/scaffold columns) and
case files; ~/fd-corpus/PRIVATE_case_mapping.md (he opens diagrams in his app from
it); the oracle store (fdserver doc/oracle/); doc/DRAWABILITY.md; doc/chat-first/STATE.md;
optionally ~/fd-corpus/design/prod_candidates.csv (other users' diagrams he may
admit after eyeballing).

**Where it starts**: the active-basis cut already exists — 11 cases ≥30 active
events, 13 at 10–29 (recompute from index.json — doc numbers are never authoritative).
Candidates are the active-bearing cases. ALSO unruled: the four cases at 1–9 active
(case_01/10/28/42) — ask, don't infer. Present him the tier lists with per-case
one-line shape profiles; he eyeballs via the mapping file and rules in/out (he
accepts the marker may miss 1–3 pertinent events per case). Watch for his correction on
zero-active cases that are actually worked-but-unflagged (coding style) — those may
re-enter.

**Then phase A (max effort, filtered set only)**: produce the document explaining
the nature of this data — what a worked case is, how scaffold and active material
relate, what the SARF variables + nodal flags + relationship moves actually encode
across HIS cases, where uncertainty lives and why, with calibrated confidence and
one-line questions wherever inference runs out. He corrects the document; only the
ratified version feeds phase B (visual choices for function).

**Outputs**: the ratified nature-of-data document (location: this doc/chat-first/
package, name it NATURE_OF_THE_DATA.md); the ruled FUNCTION subset recorded in
the oracle store (fdserver doc/oracle/rulings.md); HISTORY/STATE updated.

**First concrete step**: read STATE.md, verify ~/fd-corpus/clinic/index.json has
active_events columns, present the tier lists + the five worst volume-vs-active
illusions, and ask for his in/out rulings. Nothing else until they arrive.

## Session 2 — corpus subset for STRUCTURE

**Goal**: define the subset good for diagram STRUCTURE work (biological family-system
structure: people, pair-bonds, parent-child depth, generations, relationship
symbols), toward structure-side inference and eventually the diagram picture.

**Inputs**: same as session 1.

**KNOWN BLOCKER (fix first)**: the anonymized corpus has NO parent-child links — the
whitelist never extracted childOf/parents, and birth events name only the child, so
generational dated depth, parent-child completeness, and marriage-to-birth sequencing
are currently UNCOMPUTABLE from the corpus. Fix path: extend rebuild.py's whitelist
with parent-child person-id PAIRS (anonymous ids only — content-blind-compatible),
regenerate. That whitelist extension needs Patrick's protocol authorization: it is
this session's FIRST question to him, before anything else.

**Where it starts**: candidates are the zero-active-but-structure-rich cases (28
zero-active; the richly-structured ones among them — people count, relationship
symbols, marriage events, generational span) PLUS the structural layer of the
function-rich cases. Key inversion to keep straight: scaffold births are
diagnostically inert for FUNCTION but are first-class SIGNAL for structure (they
establish generations); the active/scaffold split serves opposite roles here.

**Process**: propose the structure-relevant signal set as QUESTIONS for Patrick
before any scoring (candidate signals: generational dated depth, parent-child
completeness, relationship-symbol coverage and kinds, marriage sequencing —
all hypotheses until he corrects). Then the same loop: tier lists → his eyeball →
in-list → max-effort structure-side analysis feeding the same NATURE_OF_THE_DATA.md
(structure chapter) → his corrections.

**Outputs**: ruled STRUCTURE subset in the oracle; structure chapter of the
nature document; HISTORY/STATE updated.

**First concrete step**: read STATE.md, then present the proposed structure-signal
questions (one numbered list, inline examples from anonymized cases) — no scoring
before he answers.
