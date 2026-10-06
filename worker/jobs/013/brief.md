# Job 013: how Murray Bowen conducts an interview, turn by turn

Base ref: branch FD-372 of btcopilot-sources, commit 413c099 (fetch it; it holds the transcripts and the measures). Work branch: worker/job-013-bowen-coding of btcopilot-sources, created from that base. Push only that branch. Nothing from this job goes into btcopilot.

## Inputs (all on the base ref of btcopilot-sources)
- theory/transcripts/murray-bowen/: 17 machine transcripts with speaker labels. Only the seven where Bowen interviews are in scope: couple-01, couple-02, couple-03 (one 75-minute interview of a couple, cut in three) and double-blind-01 to -04 (one 55-minute interview of a family, cut in four). SPEAKER_CHECK.md lists the turns whose speaker is uncertain; INDEX.md describes each file. Turns are numbered with timestamps; ⟦ ⟧ marks low-confidence words.
- research/conversation-flow/measures.md and suite.md (job 012): the measures, each with a coach-side definition.
- research/conversation-flow/kerr-pilot.md (job 012): the same kind of coding done on Kerr's interview; follow its layout and its move classes so the two are comparable.

## Do
1. Code every Bowen turn in the seven files with fixed written rules, one row per turn: the move class (at least: follows the person's last statement; pivots to a new topic; returns to an earlier topic, with the turn it returns to and how many turns back; asks for a fact; asks for a date or works a vague date to an anchor; asks who/what/when/where/how; asks a why or feeling question; reflects or restates; states an impression or a connection; teaches or advises; sums up; silence or minimal acknowledgement; other), plus every coach-side measure from measures.md that can be read from a single turn. Where a class is uncertain, mark it; never guess silently. Turns SPEAKER_CHECK.md marks uncertain are coded but flagged.
2. Also code the family's turns minimally: words per turn, whether it answers the question asked, whether it brings a new topic, whether it pushes back, whether it states a realisation.
3. Totals per interview and overall: share of each move class; questions per turn; words per Bowen turn against words per family turn; how often Bowen returns to a dropped topic and after how many turns; how he opens and how he closes each interview; how he handles the person's own "why"; the longest stretch he follows without pivoting; where he states a connection, if ever, and what preceded it.
4. Compare with kerr-pilot.md in one table.
5. Say which measure definitions in measures.md and suite.md failed on real speech (ambiguous, uncodable, or missing a class Bowen uses often) and propose the fix for each, as a rule precise enough to code.
6. One independent re-code of couple-02 and double-blind-03 by an agent that did not see the first coding; report agreement per class.

## Outputs (on the work branch, under research/conversation-flow/bowen-coding/)
<slug>.md per file (the coded table), TOTALS.md, COMPARE-KERR.md, MEASURE-FIXES.md, AGREEMENT.md, and report.md on the mailbox (at most 10 lines: files coded, turns coded, agreement, the five most striking numbers, the measure definitions that failed).

## Models and rules
Coding by Opus agents to the written rules; judgement, synthesis and the measure fixes on Fable at effort xhigh. No model judges a measure's value: every number comes from a written rule applied to the transcript. No real user data exists in this job and none is to be requested. No tests. Do not alter the transcripts. Named people on the tapes are only ever referred to by their role (husband, wife, father, Angela's mother, and so on) in totals and reports; the per-turn tables may quote the transcript.
