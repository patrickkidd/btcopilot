# Drawability

When the timeline picture may draw something, and when it must show a question instead.
Ruled by Patrick 2026-08-31 against his own record (discussions 55/58 on diagram 1924 +
14 months of journal) and a hand-coded clinical case. Visual reference:
https://claude.ai/code/artifact/b0209a84-03ee-4b36-80ae-8624bd0e88dc
Every surface inherits this: the picture refuses to draw below these bars; the coach's
elicitation is scored by whether sessions move lanes toward drawable.

## The five rules

1. **A line needs 3 directed points.** Below 3: dots. A two-point line invents a trend.
   The line spans only where points exist — no extension to "now" or back to birth.
   Lanes without direction data render as marks; marks are facts, lines are claims.

2. **Date-guessed points count** toward the 3 — otherwise remembered history never draws
   (57 of 84 chat dates are year-grade or coarser; everything before Patrick's 2024
   wedding is bands). Guessed dates render as bands (~±1 month for month-grade, ±1 year
   for year-grade, wider for decade guesses) so they are noticeable and correctable.

3. **A gap is dotted, a recorded "no change" is a solid flat mark.** Dotted = no data
   yet; never let silence read as stability (the 12-year symptom silence 1998–2010 is
   disproven by 10 functioning moments in the same years). Applies at every zoom
   (6-week journal silences too).

4. **Order is shown only when the two guess-ranges do not touch.** Move 1994±1 vs
   insomnia onset 1996±1: ranges never touch → "move came first" draws. Returned-home
   vs arguing-began, both "1992": total overlap → drawn side by side, no order implied.

5. **Open-ended states fade after their last confirmation; death hard-stops everything
   about a person.** Insomnia since 1996 with 2022–26 confirmations: solid to the last
   confirmation, then fade. A 1957 cutoff may not outlive the man (d. ~2009).

## The question language

One visual treatment for "the record has a question here," used in exactly three places:

- **Unknown order that matters**: a "?" between a symptom/anxiety/functioning point and
  a family event whose guess-ranges touch. Found deterministically (a query, not a
  model call: variable point on one lane, family event within touching range on
  another). All other same-era pairs silently follow rule 4.
- **Unconfirmed open state**: the fade itself ("is that still how it is?").
- **The undated shelf**: facts with no date at all sit below the lanes, never
  positioned ("exists, undated"). In Patrick's record 4 of 6 shelf items are family
  sleep facts — the history of the presenting problem lives on the shelf.

The coach picks questions from this set in conversation (the model chooses which and
phrases it; nothing queued, no background calls). Each answer sharpens the record and
removes its question mark. This replaces any progress bar: what more data buys is shown
in place, as specific answerable questions. There is no notion of "finished."

## Consequences already known

- Density encodes capture mode, not severity: 18 journal anxiety days in one year vs
  3 remembered bands per decade. The drawing must not let a well-sampled era read as a
  worse one.
- Certainty is a property of when a fact was captured: journaled-now = day-sharp,
  recalled recently = month, remembered decades = year+. Long-horizon returning chat is
  therefore also the data-quality strategy.
- Self-reported chat/journal data is direction-rich (70% of Patrick's 162 moments);
  relationship moves are the exception (mostly categorical) — couple/household lanes
  are stamped marks and ranges, not curves.

## The cartoon rule (ruled 2026-08-31)

The resting picture shows almost nothing: strip-small, always on, one or two lanes,
cartoon-level detail. The product exists to produce one or two brain-rearranging
correlations, not a comprehensive dataset — users must never feel they've taken on a
data project. Conversation drives everything; the UI is a secondary way to fill gaps,
and the coach aims the picture with an inline reference when it wants attention.
Questions are quiet marks in place — never cards, never a queue (survey feel killed
the "question-first" mockup). The undated shelf lives behind a tap. Coverage is never the goal:
it serves two things only — letting the coach ask better questions, and giving the
timeline enough to show a correlation itself. The acceptance
test for coach and picture alike is the felt shift ("something rearranging"), of which
two real instances are on record (the stepmother-out/mother-in/high-school pileup;
the triangle poke about B's relationship with A). Mockups:
https://claude.ai/code/artifact/a20195e0-2310-4308-8fd5-1dc74ac28dc9

### At-rest vocabulary (Patrick's storyboard review, 2026-09-01)

The resting strip failed a cold read: bands, ranges, and tick pairs are meaningless
without labels, and there is no room for labels. Rule: at strip scale only THREE marks
exist — a line, dots, and the amber question mark. Bands/ranges/fades/ticks appear only
in the expanded view where words fit beside them. Every mark says itself in a plain
sentence on tap ("sleep got worse, around 1996, give or take a year") — the teaching
gesture and the editing gesture are the same. No legends anywhere. Also queued as A/B
tests: calm-period return prompts ("while it's calm"); mark-vocabulary variants.
Only frame-4-style notifications are app-initiated; in-conversation aiming is not push.

### Expanded view must be designed for sparse data (Patrick's first sandbox walk, 2026-09-01)

First contact with the built expanded view: sparse lanes read as "random boxes drawn on
a giant rectangle" — items too far apart to read as sharing a time axis, question marks
floating at irregular offsets from their items. The view assumed clean dense data; the
record's normal shape (per the data audit) is sparse, band-heavy, unevenly spaced.
Rules: the expanded view organizes around eras/anchors, every mark visibly tied to the
axis (per-mark year labels or gridline snap), question marks attached to their items.
Horizontal pan/zoom of time is mandatory (multigenerational spans cannot fit a static
view). Undated-shelf chips must respond to tap (speak themselves + offer "ask the coach
when"). No lane-filter UI — lanes are chosen by the coach and user pins only (a filter
panel is a data project; killed).
