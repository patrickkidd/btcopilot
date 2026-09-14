# Test strategy — what the chat app's tests cost and what they prove

Audited 2026-09-14 under R-0331, measured on this branch. No code was changed.

## The headline: the test suites are not where the time goes

The review back end runs 89 tests in 6.4 seconds; the front end unit suite runs 113 in
1.9 seconds. About 2.4 seconds of the review run is Python starting up before a test
runs, and the slowest single test is 0.31 seconds. Neither suite is worth optimising.
That contradicts the premise this audit was ordered on; spend no worker on it.

## 1. Which tests trace to a ruling

The oracle holds 331 rulings, 229 about the product rather than process. Thirteen
distinct ruling ids are named anywhere in the tests. The branch's code and documents
name 196, so the tests are the weakest link in the chain, not the corpus.

The tests instead carry the ruling in the test's name, in the oracle's own words: a cut
cannot be placed before the last ratified one, a coder cannot open the vote. That reads
well and is not traceability — nobody can ask which tests must change when a ruling
changes, or which ruled behaviour has no test. The front end names no ruling at all.
Fix: a comment line naming the ruling id at the top of each test, as tests are touched,
never as a sweep.

## 2. Unit tests doing work they do not need

Every review test builds a Flask application, creates every table in an in-memory
database and drops them, including tests that only need a function: the scribe's reading
of a turn, name matching, divergence. That costs about 40 milliseconds a test, under
four seconds across the suite — worth knowing, not worth fixing until the suite is
several times larger. Two things are right and should stay: no test reaches the real
coach, and password hashing is stubbed. Twenty-three personal-suite tests make real
model calls and are skipped unless asked for.

## 3. The database fixture strategy

Today: in-memory SQLite, tables created and dropped per test, fresh application per
test. Building the schema once per session and rolling each test back in a
transaction would save two to three seconds as the suite stands, and introduces
leak-between-tests bugs that cost debugging hours the first time they bite. In-memory
already beats a file. Recommendation: leave it. Revisit past thirty seconds.

## 4. Where a test should live

- **Unit** if it can be decided by calling a function with records in hand: scribe
  reply, name matching, divergence, tendencies, export shape. No application, no
  database.
- **Integration** if what is proved is a route, a role, or a rule the database
  enforces: who may open a vote, that a cut cannot overlap, that ratifying writes the
  export. Correctly the bulk of the review suite today.
- **Walk** if what is proved is what a person sees or taps.

The test proving the review reaches the two apps through one module is the most
valuable on the branch; it protects a boundary that would otherwise rot silently.

## 5. What will cost later

**The walks are not in version control.** All four browser walks live in a scratch
directory that is not a git repository. They hold the only deterministic gates the
project has — console errors, failed requests, boxes outside their parent, sideways
scrolling — and are one delete from gone. No reviewer can see them. Largest risk here.

**The builder writes the walk for their own screen.** A pass tells you the author of
the screen also wrote the check. The walks are well built, which makes this easy to miss.

**The review front end is 12,000 lines of TypeScript**, the picture and the main wiring
over a thousand lines each, with the review's screens in the same folder as the chat's.
The import boundary the back end enforces has no equivalent on the front end.

**The fixtures cross the boundary the source may not**, importing the chat's and the
desktop app's models directly. Defensible, but the isolation test cannot cover them.

## The five changes with the best return

1. **Move the walks into the repository** under the web folder with their fixture
   scripts. Half an hour; returns every hour otherwise spent rebuilding a lost gate.
2. **One runner that fails the batch**, so a screen's check is a command, not four
   remembered invocations. An hour; saves minutes per round and stops walks being skipped.
3. **Name the ruling id in each test as tests are touched.** Minutes per test; turns a
   ruling change into a mechanical edit.
4. **A different agent owns the walk from the one that built the screen.** No
   engineering cost; changes what a passing walk means.
5. **A named boundary between the review's front end and the chat's**, mirroring the
   back end's one-door rule. Two to three hours now against a rewrite later.

Database fixture work is deliberately absent: most likely to be proposed, least return.
