# What the reviewer must decide, ranked

Judge: judge-010, 2026-10-04. Each top item: the fork, the judge's call, the sources, an example. The
rest at one line each. Sources: FE = Family Evaluation; FTiCP = Family Therapy in Clinical Practice;
BS = Basic Series. All people named are fictional.

## 1. Is the question an early question that the dated history then checks, or the way the coach finds the periods?

The judge's call: an early question, asked once, then checked against the calendar and the wider
family; the dated history in Kerr's loose order stays the history, and Kerr's catch-all is asked
again after it. Why: neither Kerr nor Bowen asks the person to name or rank times; both derive the periods from
dated facts (FE ch10 L11, L15, L19; FTiCP ch9 L85, L89; BS 3 L479-497). The one open sweep comes
after the dated history (FE ch10 L15). What a person offers unasked is the symptom and the charged issue,
and the related events are what the family "operates always to obscure and misremember" (FTiCP ch9
L93; BS 6 L120-123); quiet years are not empty (FE ch10 L45). Example: Nadia names 2009 (her
father's illness, leaving college) and 2019 (her divorce). Her mother's brother died in 2008 and her
parents sold the family business in 2014; neither is on her list, and both are where the theory
would look. If this is accepted, the whole proposal follows; if rejected, so is the rest.

## 2. When is it asked: after what brings them has a date, or as the first question after onboarding?

The judge's call: after the presenting problem's start has a date, or at once when the person
brings no one thing; never before the person has said what brings them. Why: both authors start
with the problem and its dates (FE ch10 L11; FTiCP ch9 L85), the onboarding text already says to
carry on with what they said first, and "the presenting problems may be so consuming that there is
little time to do more" (FE ch10 L65, note 14). Example: Tomas opens with "my son stopped talking to
me in March". The coach dates March first, asks what was happening then, and only then asks which
two or three times in his life the most was going on.

## 3. The wording: what was going on, what stands out, or what was most stressful?

The judge's call: "what were the two or three times when the most was going on, and about what
years" (phrasings
.md, candidate 1). Why: it asks for Kerr's own mark of a period, "a series of stressful events
converged" (FE ch10 L45), in plain words; it asks what happened and when, never why (FTiCP ch16 L99;
Gilbert L785-792); and it does not steer toward bad years, so marriages, births and returns, which
disturb the balance as losses do (FTiCP ch15 L13; BS 6 L88-105), get named. "Stand out" (the brief's
shape) leans toward the person's own symptom years; "most stressful" (Kerr's word) asks for a
feeling about the years, and felt stress is not stress (FE ch10 L65, note 24). Example: asked what
stood out, Priya names the year her panic attacks began; asked when the most was going on, she names
that year and the year her daughter was born and her mother moved in.

## 4. Does the early question name the checklist item "periods of major stress"?

The judge's call: no. The early question is kept as a fact question on the person without the
`fact` item, so "periods of major stress" stays unasked until the dated history reaches it and the
coverage block prompts Kerr's catch-all at its proper place; closing the early question `answered`
would otherwise mark the family's periods known when only the person's markers are. The cost: the
tool text says to name the item "whenever the question asks for one of the required facts", and the
early question arguably does; and it is then not counted among the evaluation questions in the
coverage measures (doc/COVERAGE.md, "The metrics"). Changing the tool text needs Patrick's yes
(R-0625), so the choice is made within the current text. Either way needs no code change and no
change to the order of the dated history. Example: after Nadia's two times are gone through, the block
lists "periods of major stress" and the coach asks whether there were other years when a lot was
going on for the family; her uncle's death in 2008 comes up there.

## 5. A time named with nothing in it: a question naming the years, never an event

The judge's call: keep a fact question on the person that names the span ("What was going on in
your family between 2014 and 2016?"), allowed by R-0686 (named, not read); write no event, because
a noted event must say what happened (R-0363) and a shift needs a variable that moved on a person
at a date. A cluster from a label needs no rule: the code computes clusters from dated events and
refuses any group under three at the write (doc/CLUSTERS.md). Why: "2014 to 2016
was the worst" is a feeling about the years, and the record holds facts (Gilbert L745; FTiCP ch16
L99). Example: Omar says 2014 to 2016 was the worst. The record gets one open question and nothing
on the line until he says his wife's mother died in 2014 and he was laid off in 2015.

## 6. Are the years asked in the same question, or in the next turn?

The judge's call: in the same question ("and about what years were they"). Why: an undated marker is of
little use, since nearness in time is the only evidence the theory claims (FTiCP ch9 L93; FE ch10
L11), and the year is the first thing the follow-up would ask anyway, so asking it at once saves a
turn; the register is then evaluation (a date is a basic fact). Against: it makes the early question
two asks in one sentence. Example: "around 2009 and 2019" in the first answer, against two more
turns to get them.

## The rest, one line each

7. The "Good" example in coach_story_shape.md has the coach say two events "look like one story to
   me now"; Bowen never says so early (FTiCP ch9 L93; BS 6 L125), Kerr lets it dawn (FE ch10 L11);
   the proposal only asks that it wait for firm dates, and leaves the example to Patrick.
8. The years before the person's memory and the other side of the family are asked when the dated history
   reaches the parents and at each loss on the record (placement.md section 4); accept as the
   standing follow-up, or treat the open build item in doc/TOPICS.md ("the coach does not yet ask
   about the older households around each death, separation and move") as its own job.
9. The public edits are overridden by the private copies of the same fragments on the running coach;
   someone with the key mirrors them, and the private opening and flow fragments carry the order.
10. The live fixture lacks a `questions` reader; the drafts add one small reader.
11. Eval draft 2 does not assert "no event" because whether "everything went wrong" codes a
    functioning shift waits on the R-0428 decision.
12. impressions.md already says "a stretch of years"; the proposal leaves the existing words alone.
13. The phrasings say "times" and "years" because the coach may never say "period"; if Patrick wants
    the coach to say "period" to the person, coach_story_shape.md is the rule to change.
14. "Two or three" is a count, not a list of answers; if it reads as steering, drop it ("which
    times") and let the follow-up cap the number.
15. The brief's premise that intense times are remembered better is not in the sources; they say
    the related events are forgotten, which is a claim about what is left out (theory.md, section 4).
