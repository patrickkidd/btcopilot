# SCOUT — what the outside world changed, and whether it helped us

The scout looks outward once a week and proposes changes to this project's own way of
working. It never changes application code and never applies its own proposals. Ruling
R-0333. Its brief is `.claude/skills/scout/SKILL.md`.

**Intended schedule** (Patrick creates it; the scout never creates its own):

```
0 6 * * 0  America/Anchorage
```

Weekly, Sunday 06:00 Alaska time, on the `FD-362` branch of btcopilot.

Every session reads this file after STATE.md and says in its first reply whether any open
item applies to that day's work.

## The four numbers

These are the only numbers a proposal may predict against. Each is measured from the
corpus, not from instinct.

| Number | Baseline this week | Where it was measured |
|---|---|---|
| Hours from brief to walk-ready | 8 | The overnight build of 13/14 September: first commit 19:59, last 03:39 |
| Patrick's findings per walk | 4.5 | Nine findings across two of his walks, 11 and 12 September (REVIEW_LOG rows 70 to 78) |
| Re-walks per screen | 1 | The independent verification of 12 September found 24 failures across the review screens; one fixing pass closed them, and one re-walk followed |
| Chat suite minutes | 0.14 | The review back end runs 89 tests in 6.4 seconds and the front end 113 in 1.9 seconds (TEST_STRATEGY.md, 14 September) |

Two notes on the baselines, so a later run does not misread them. The verifier ran 366
checks and 24 failed; that is the count of screen faults found by an independent agent, not
by Patrick. And the suite minutes are already so small that no proposal predicting a move
on them is worth ranking highly — TEST_STRATEGY.md says as much.

## The kill rules

These stop the scout from becoming a cost of its own.

1. **Fewer than one proposal in six merged after eight runs stops the scout.** Count
   merged draft pull requests against proposals opened. Below that rate the scout is
   producing reading, not change, and it is retired rather than tuned.
2. **A merged change that does not move its predicted number within two builds stops that
   kind of proposal.** The kind is named in the row. One failed prediction of a kind is a
   miss; the rule fires on the kind, so a second proposal of the same kind is not opened.

A run that fires either rule says so at the top of this file before anything else.

## Open items

None yet. The first run fills this section.

## Proposals ledger

| Date | Item | Prediction | Merged / closed | Measured two builds later |
|---|---|---|---|---|
| | | | | |
