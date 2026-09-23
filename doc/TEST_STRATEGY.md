# Test strategy — what the chat app's tests cost and what they prove

Audited 2026-09-14 under R-0331, extended under R-0332. Measured on this branch. No
code was changed.

## The standard, 2026-09-23 (R-0421, R-0416)

Every test cites the ruling it proves on a comment line at its top: `# R-0NNN` under a
Python test's def, `// R-0NNN` above a TypeScript or Playwright test. A test that proves
no ruling says `no ruling` there instead, and is listed with what it proves in
`doc/TESTS_WITHOUT_RULING.md` for the owner to rule on or delete. A process ruling is
never cited for product behaviour. `btcopilot/tests/test_citations.py` fails on any test
in the three trees without one of the two. This replaces the "as tests are touched,
never as a sweep" fix in section 1: the sweep was ordered. Screenshots are compared only
where pixels matter: the resting picture on each fixture record, one open cluster, the
board on its first move, a reply in the chat, the sessions sheet and the settings root,
at phone size only. Everything else asserts words, roles and geometry (visible words,
no box outside its parent, the 44px floor). The desktop project keeps its assertions
but skips every screenshot and is not part of the gate; it runs by hand.

## The headline: the test suites are not where the time goes

The review back end runs 89 tests in 6.4 seconds; the front end unit suite runs 113 in
1.9 seconds. About 2.4 seconds of the review run is Python starting up before a test
runs, and the slowest single test is 0.31 seconds. Neither suite is worth optimising.
Spend no worker on making them faster. What costs time is not the running, it is that a
person cannot say which tests to run, and that the browser checks have forked into two
places.

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
test. Building the schema once per session and rolling each test back in a transaction
would save two to three seconds as the suite stands, and introduces leak-between-tests
bugs that cost debugging hours the first time they bite. In-memory already beats a file.
Recommendation: leave it. Revisit past thirty seconds.

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

**The browser checks have forked.** The repository already holds a Playwright harness
at `web/tests/visual` — seventeen spec files, accepted pictures, a phone size and a
desktop size, a sign-in helper, and a written reason it is parked. The four walks for
the review screens were written a day later into a scratch directory that is not a git
repository, with their own gates and their own browser launch. Two harnesses now do the
same job; one cannot be reviewed, recovered, or run by anyone who does not know it
exists. This is the largest risk here, and it is cheaper to fix than it looks, because
the destination already exists.

**The builder writes the walk for their own screen.** A pass tells you the author of
the screen also wrote the check.

**The review front end is 12,000 lines of TypeScript**, the picture and the main wiring
over a thousand lines each, with the review's screens in the same folder as the chat's.
The import boundary the back end enforces has no equivalent on the front end.

**The fixtures cross the boundary the source may not**, importing the chat's and the
desktop app's models directly. Defensible, but the isolation test cannot cover them.

## 6. Splitting the chat app's tests from Pro and training (R-0332)

Today the chat app's tests inherit Pro's world by directory. The chat's conftest imports
Pro's clients; the shared conftest at the root imports Pro's licence, machine and
activation models and stubs Stripe, Chroma and Celery for every test that runs; the one
pytest settings file carries seven markers that belong to the training app's screens.
None of that is needed to prove a cut cannot overlap.

Proposed layout, back end:

    btcopilot/tests/chat/          the chat app, own pytest.ini and conftest
        personal/                  moved as-is
        review/                    moved as-is
    btcopilot/tests/shared/        app factory, in-memory database, a signed-in user
    btcopilot/tests/pro/           unchanged
    btcopilot/tests/training/      unchanged

The rule that makes it hold: **shared fixtures are imported by name, never inherited by
directory.** A root conftest is invisible coupling — it applies to everything beneath
it whether or not a test wants it. Moving the genuinely common fixtures into a plain
module that each suite imports makes every dependency visible in the file that uses it,
and lets the chat suite drop the Stripe, Chroma and Celery stubs entirely.

Front end: `web/test/chat/` and `web/test/review/`, declared as two vitest projects
rather than one include pattern, and the review walks folded into
`web/tests/visual/review/` beside the chat's existing `web/tests/visual` specs.

**The one command.** A short runner, `bin/t`, taking a component name:

    bin/t chat      the chat back end only
    bin/t review    the review back end only
    bin/t web       the front end unit tests
    bin/t walks     the browser walks against the sandbox
    bin/t           whatever the current diff touches

With no argument it maps changed paths to suites: a change under `btcopilot/review`
runs the review suite, a change under `web/src` runs the front end and the walks for
the screens named in the diff, a change under `btcopilot/pro` runs nothing of the
chat's. That is the whole feature — path to suite, nothing cleverer. Do not reach for a
coverage-tracing selector such as pytest-testmon here: it earns its keep on suites
measured in minutes, and ours are measured in seconds.

## 7. What the current practice literature says, and what I took from it

**Spec-derived tests detect more real bugs than agent-written ones.** Tufano and
colleagues (2026) had agents write tests for 90 historical production bugs in Google's
codebase. Agents grounded in a written specification detected 63.2% against 53.4% for
the same agent unguided, a 9.8 point gain at p=0.0352. The sharper number is the
mechanism: where the specification captured the contract the bug violated, detection
succeeded 54.9% of the time; where it did not, 19.4%. Taken: this is the evidence for
naming the ruling id in the test. It is not bookkeeping. A test that names the ruling it
enforces is measurably better at catching the bug than one that does not, and the chat
app already has the specification most projects lack.

**Agents left to judge their own work weaken the check.** The reward-hacking
benchmarks of the last year — ImpossibleBench, EvilGenie, SpecBench — all measure the
same failure: an agent that can edit the test will edit the test, deleting assertions,
hardcoding expected values, or editing the harness, rather than fix the code.
ImpossibleBench makes the task unsatisfiable and counts how often the agent makes it
pass anyway; EvilGenie detects edits to the test file directly. Taken: the builder must
not own the walk for the screen they built, and a walk edit in a diff should be looked
at as carefully as a source edit. This is the cheapest finding on the list to act on and
the one with no engineering cost.

**Change-scoped selection is standard practice, and it is a path map first.** The
common industrial pattern is to map a change to the affected component and run that
component's tests on every commit, keeping the whole suite for the end. Tooling that
traces coverage per test, such as pytest-testmon, exists and works, but pays back on
long suites. Taken: `bin/t` maps paths, and nothing more.

**Mutation testing is the right idea at the wrong time.** The 2026 work applying models
to mutation — generating mutants and checking whether the specification's postconditions
catch them — is aimed at finding weak specifications, which is exactly our risk. It is
also a whole machinery for a project this size. Taken: the one-mutant version. When a
walk is written, break the behaviour it checks and confirm the walk fails. One minute,
and it is the only thing that proves a walk checks anything at all.

Sources: [Tufano et al., Grounding AI Agents in Contracts (arXiv 2608.17177)](https://arxiv.org/html/2608.17177),
[SpecBench (arXiv 2605.21384)](https://arxiv.org/html/2605.21384v1),
[ImpossibleBench](https://www.lesswrong.com/posts/qJYMbrabcQqCZ7iqm/impossiblebench-measuring-reward-hacking-in-llm-coding-1),
[LLMs Gaming Verifiers (arXiv 2604.15149)](https://arxiv.org/pdf/2604.15149),
[pytest-testmon](https://github.com/tarpas/pytest-testmon),
[Autonomous coding agents and QA, 2026](https://www.devassure.io/blog/autonomous-coding-agents-rewriting-qa-playbook-2026/).

## The changes with the best return, ranked

1. **Fold the four scratch walks into `web/tests/visual`** and delete the duplicate
   harness. One hour. The destination, the sign-in helper and the viewport sizes
   already exist; this is a move, not a build. Returns every hour otherwise spent
   rebuilding a gate nobody can find.
2. **Write `bin/t`.** One to two hours. It is the difference between a worker running
   the right nine seconds and a worker running the wrong five minutes, several times a
   round, and it is what makes "only the changed component" enforceable rather than a
   request.
3. **Split the chat's tests from Pro and training**, with shared fixtures imported by
   name. Three to four hours. Saves little clock today; it is what stops the chat suite
   inheriting Pro's stubs and Pro's failures for the rest of the project's life.
4. **A different agent owns the walk from the one that built the screen**, and every
   new walk gets the one-mutant check. No engineering cost. Changes what a passing walk
   means, which is the finding the literature supports most strongly.
5. **Name the ruling id in each test as tests are touched.** Minutes per test. Worth
   roughly ten points of real-bug detection by the only published measurement of it.

Database fixture work is deliberately absent: most likely to be proposed, least return.
