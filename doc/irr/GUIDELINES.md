# SARF Coding Guidelines

Rules established from IRR calibration meetings. Updated after each session.

## General Rules

1. **One shift per event, one event per atomic shift.** Each new shift gets a new event entry. Do not use "edit existing event" to append evidence to prior entries. Exception: you can only track one relationship shift per event, so two simultaneous R shifts at the same timestamp require two events.
2. **Two separate shifts for different people.** When a single statement implies events for different people (e.g., Sarah's anxiety vs. mother's diagnosis), code them as separate shifts.
3. **Deduplication.** Same timestamp + same person + same shift = duplicate. Remove one. Also: do not re-enter a shift just because it is mentioned again in a later statement — one shift per person per event in time.
4. **First sibling naming → add common parent pair bond.** When text first reveals someone is a sibling, add unnamed shared parents (e.g., "Sarah's mother," "Sarah's father") so both can be linked.
5. **Semantic similarity between description tense and timestamp.** Present-tense descriptions ("Michael doesn't help") should have present-date timestamps. Past-tense ("six months ago") should be backdated accordingly.
6. **Don't change reviewed case data.** Preserve original codings for cases that have been discussed in calibration meetings. Unreviewed cases can be corrected freely.

## Symptom Coding

### When to code "up" vs "down" vs "same"

## Anxiety Coding

### When to code "up" vs "down" vs "same"

## Relationship Coding

### Which RelationshipKind to use

**Minimize assumptions.** When evidence supports multiple mechanisms (triangle, over/under functioning, distance), prefer the code that makes the fewest theoretical assumptions. Toward/away makes fewer assumptions than over/under functioning, which makes fewer than triangle or distance.

- **Away** vs **Distance**: "Away" captures observable reduced involvement. "Distance" implies the specific emotional distance mechanism (anxiety-driven avoidance of content). Use away when you don't have evidence that the avoidance is anxiety-driven.
- **Toward/Away** vs **Over/Under Functioning** vs **Triangle**: When a statement could be coded as any of these, consider which has the most direct textual evidence. Toward/away is the most conservative default. This is an active area of calibration — no definitive rule yet.

### Over/Under Functioning (proposed definition)

Automatic behavior where someone is doing something for another person where there is opportunity to choose differently — "wiggle room." The mechanism is named to point out places where behavior is automatic and adaptive but could potentially be changed. The key test: is there room to consider whether this behavior is necessary?

### Multiple recipients

The data model supports multiple recipients on a single relationship shift. When someone is moving away from or toward multiple people simultaneously, you can code them all as recipients of the same event.

## Functioning Coding

### When to code "up" vs "down" vs "same"

## Geographic Moves

### Moved vs Distance

When a person has relocated geographically (e.g., "Dad's in Florida"), code "moved" — not "distance." Geographic distance does not imply emotional distance (the Bowen mechanism). Only code emotional distance when there is evidence of anxiety-driven avoidance of content, not merely physical separation. Divorce + geographic relocation alone is insufficient evidence for emotional distance.

## Structural Data

### Preemptively add parents

When a family member is first mentioned, add both parents (even unnamed — use "Sarah's mother," "Sarah's father") so that pair bonds can be established. This applies to any family member, not just the identified patient. When a sibling is identified, the shared parents should be added via this rule. Rationale: the data model requires a pair bond to assign parentage, and a pair bond requires two people.

### Person field directionality

The "person" field in a shift entry is the one performing the action (the distancer, the over-functioner, etc.). Recipients go in the recipient fields. Do not put the speaker/client in the person field by default — put whoever is described as doing the action.

## Edge Cases

### New shift vs reiteration

When a later statement reiterates evidence from an earlier one, do not add a new entry. One person doing one thing at one point in time = one shift entry, regardless of how many times it is mentioned. Exception: if the reiteration references a genuinely different timestamp (e.g., "two months later, he was still avoiding"), that is a new data point and can be a new entry, possibly with "same" value.

### Use of "same" value

The "same" value (for symptom, anxiety, functioning) represents a second data point confirming persistence at the same level. It requires a different timestamp than the original shift. Do not use "same" to track re-mentions of the same event at the same time period — that is deduplication, not a new data point.

## Revision History

| Date | Meeting | Changes |
|------|---------|---------|
| 2026-02-16 | Meeting 1 | Initial rules from Sarah Round 1 calibration |
| 2026-02-23 | Meeting 2 | Added: moved vs distance, preemptive parent addition, person field directionality, deduplication clarification, "same" value usage |
