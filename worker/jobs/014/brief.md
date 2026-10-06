# Job 014: three more Bowen interviews, coded the same way as job 013

Base ref: branch FD-372 of btcopilot-sources, commit 280c8f5 (fetch it). Work branch: worker/job-014-bowen-coding-2 of btcopilot-sources, created from the base. Push only that branch. Nothing from this job goes into btcopilot.

Context: job 013 (branch worker/job-013-bowen-coding, last commit 1e32980) coded seven Bowen interviews with the rulebook research/conversation-flow/bowen-coding/RULES.md and the scripts under scripts/. Patrick has since confirmed that Murray Bowen is also the interviewer in the EPPI series and the therapist in "One Year of Therapy with the Same Family". These three files on the base ref are relabelled with BOWEN as the interviewer and carry the same speaker check: theory/transcripts/murray-bowen/eppi-01.md, eppi-02.md, one-year-therapy.md (eppi-03.md is two clinicians discussing the case; leave it out). Note from the speaker check: eppi-02 has a 71-second gap at 0:12:49 after which the family is gone and the family's own therapist answers Bowen; code that stretch but mark it as a clinician conversation, not family.

## Do
1. Merge branch worker/job-013-bowen-coding into your work branch first so RULES.md, scripts/ and the seven tables are present; do not change the seven tables or RULES.md (if a rule must change to code the new files, write the change in MEASURE-FIXES.md as a proposal and apply the existing rule as written).
2. Code eppi-01, eppi-02 and one-year-therapy exactly as job 013 did: one row per Bowen turn with the same columns, the family turns with the same minimal codes, uncertain rows flagged not guessed, uncertain-speaker turns coded and flagged.
3. One blind re-code of one-year-therapy by an agent that did not see the first coding; agreement per class into AGREEMENT.md as a new section.
4. Re-run the counting scripts over all ten files; update TOTALS.md with per-interview totals kept separate (the couple, the double-blind family, the EPPI family, the one-year family) and an all-ten total; update COMPARE-KERR.md; add to MEASURE-FIXES.md anything the three new files broke.
5. report.md on the mailbox, at most 10 lines: turns coded, agreement, the five numbers that changed most from the seven-file totals, and whether the one-year family (a year of sessions with the same family) looks different from the single interviews in any measure.

## Models and rules
Coding by Opus agents to RULES.md; synthesis and the measure fixes on Fable at effort xhigh. Every number from a script or counting rule. No real user data; none to be requested. No tests. Transcripts unchanged. People on the tapes referred to by role in totals and reports.
