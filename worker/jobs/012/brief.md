# Job 012: what keeps a person talking and coming back, and how to measure conversational flow

Base ref: origin/master of btcopilot-sources (the private repo). Work branch: `worker/job-012-conversation-flow` in btcopilot-sources (create from the base, push it; never master). Nothing in patrickkidd/btcopilot is touched by this job, and nothing private goes on the mailbox branch: status and report here stay to file names, counts and one-line findings.

## First, before any work
In `status.md`, with `claimed`: whether you can do web research from that machine (search and open pages). If not, write `question:` and wait.

## Why (Patrick, product owner, 2026-10-05, his words)
"The immediate product challenge that we have is having people return. People are chatting for a while which is cool but we want them to return to the app. So the coach needs to demonstrate some value fairly early I assume."
"People have been training psychotherapists for decades and there is this nuanced balance that professionals hold while talking to someone, particularly in the first few sessions when the client is getting used to the therapist and what therapy is in general."
"We most certainly do not want to pursue pathological addiction here but we do want to understand what gets users motivated to talk about their life issues."
"Take all of that to the research in the Bowen literature and outside of the Bowen literature to see what it says."
Go hard and be creative: the aim is a set of things we can look for and measure in a coaching conversation, and a starting point for modelling conversation flow.

## The product, in one paragraph
A chat coach grounded in Bowen family systems theory. A person talks about their family; the coach follows their story, gathers the dated facts of the family (who, when, where; never why), keeps a record, and draws the family and its timeline. One person, text only, no therapist in the loop. The coach sees a short window of recent messages plus the stored record, so anything it wants to return to must be stored.

## Part A: the literature, inside and outside Bowen theory
1. Bowen theory: read `bowentheory/` (Family Evaluation ch. 10 and 11; Family Therapy in Clinical Practice ch. 9, 14, 15, 16, 21, 22; Basic-Series; Gilbert) and `theory/` (notes, REFERENCE.md, and the diarized interview at `theory/transcripts/HFamilyInterview-Kerr.txt`). What do Bowen and Kerr say and show about: the first interviews; when to follow the person and when to collect facts; returning to something raised earlier; what motivates a family to continue; the coach's neutrality and staying out of the family's emotional process; humor and reversals; what a person takes home between sessions.
2. Outside Bowen theory, by web research, with sources: early-session engagement and dropout in psychotherapy (the therapeutic alliance, expectations and role induction, the first three sessions, session-by-session feedback); motivational interviewing (it came out of addiction treatment and is about what gets people talking about change); what clinical training teaches about pacing, following versus leading, and returning to a dropped thread; attrition and return in digital mental-health and coaching apps, including chat agents; behavioural research on habit and return (variable rewards, streaks, unfinished-task effects, commitment devices), including what the gambling and consumer-app industries developed, read critically.
3. For each finding: the claim, the source (author, year, link), the strength of the evidence (meta-analysis, trial, observational, industry practice, opinion), and whether it is compatible with Bowen theory, in tension with it, or ruled out by it, with the passage that says so. Never invent a citation; a verifier agent opens every cited source before the report.

## Part B: measures of conversational flow
Propose measures that can be computed from a transcript plus the stored record with fixed rules (no model as the judge), each with: a definition precise enough to code, what it is evidence of, the source it comes from, and how it would be checked in a test with made-up people. Start from this seed list and go well beyond it:
- share of the words that are the person's, per sitting, and the coach's reply length over time
- the mix of question kinds: fact, date, story-opening, process (who did what, then what), and counts of "why" and feeling questions
- how many turns the talk stays on one story before the topic changes, and who changed it
- what the person's next message looks like after each kind of coach move (length, new people named, new dates)
- returns: a topic raised and left, and whether and when the coach comes back to it
- widening: moves from the person to another family member or another generation, and when they come
- the share of stories that get a date within a few turns
- turns until the coach first shows the person something they did not say themselves (two dated facts side by side), and how the person responds
- how a sitting ends, whether a thread is left open for next time, and days until the next sitting by kind of ending
- recovery after the person objects or says they already answered
- what follows a heavy disclosure: a fact question or staying with it
- the share of the person's talk about their own part versus other people's
Code the Kerr family interview with your measures as a pilot and report the numbers, so the same coding can later be run on Murray Bowen's own interviews (arriving separately) and on the app's threads.

## Part C: early value and the line not to cross
What should the coach do in the first sitting or two so a person has a reason to return, each item marked compatible or in tension with Bowen theory. Separately, the techniques to rule out because they drive compulsion rather than motivation, with the reason and the source.

## Output, on the work branch under `research/conversation-flow/` (use `git add -f` if a pattern ignores it)
`findings.md` (ranked top ten with sources, the rest one line each), `measures.md`, `kerr-pilot.md`, `early-value.md`, `not-this.md`, `decide.md` (a ranked list of what Patrick must decide, each with its source and one concrete made-up example; plain words, no coined terms; "cluster" and "event", never "stretch" or "moment").

## Models and rules
Judgement, synthesis and inventing measures on Fable; literature search and reading on Opus or Sonnet readers; one independent verifier for citations. Fictional people in every example. No real user data, no production, no secrets, no changes to btcopilot. Tests: none.

## Done
`report.md` here, at most 10 lines: the work branch and last commit, counts of sources read and verified, the top five findings in one line each, anything unfinished.
