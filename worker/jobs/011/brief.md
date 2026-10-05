Amended 2026-10-04 (before any claim): item 1 backstop search now uses a fixed word list per fact, run by the tool. If you read the earlier version, re-read item 1.

# Job 011: the coach stops asking for what it was already told (FD-371 item 3)

Base ref: origin/FD-371 of patrickkidd/btcopilot (58ff6087 or later). Work branch: `worker/fd371-memory` (create from the base, push it; never master, never FD-371 itself).

## First, before any work
Put in `status.md`, with `claimed`, two checks: (1) decrypting works: `sops -d private/prompts/fragments/agent_fidelity.md > /dev/null && echo decrypt-ok`; (2) whether the live suite's subscription replay runs on your machine (btcopilot/tests/live/README.md describes it; run one existing case from btcopilot/tests/live/test_repeats.py through the replay, $0, never an API key). If either fails, write `question:` and wait.

## Goal (Patrick, 2026-10-04, verbatim)
"All I know is that a user who said they can't have children should not be asked if they have any children. And same question about her father." Also: "yes make it so the user's timezone is honored in the FE."
Measured on production (paraphrased; never use real data): the coach asked one user whether she had children 205 messages after she said she couldn't have any; asked whether her father was alive and his age 73 messages after giving his birthday and that her parents were still married; repeated its own open question at least 12 times (one three times in a row); said "turns 70 tomorrow" two days early because "today" is the server's UTC date, not the person's (Alaska, evening).

## Root cause (checked in code by a design review)
The coach's list of what is still unknown marks "how many children" unknown unless a closed fact question says so (events like "news: can't have children" do not count), and "alive or not" unknown unless a death event or a closed alive question exists. Both re-asks were the coach obeying that list. Its existing chat search would have found "children"; search is not the gap. Ruling R-0737 (shipped): no age limit on asking who is alive; the coach asks, and the answer is stored as a closed alive question, never asked again.

## Build (approved design)
1. The question tool refuses recording an asked fact question when the record already answers that item (closed question, death event, dated birth, and so on), and returns the stored answer to the coach. With the refusal, add one cheap backstop: a search of the conversation using the existing chat search, run by the tool itself, not worded by the coach (Patrick's worry: the coach may not know the exact words the person used). The tool searches a fixed list of everyday words per fact, kept in code next to the fact list (children: children, kids, son, daughter, pregnant, baby, IVF, adopt; alive: alive, living, died, passed, death, funeral, still married; and so on for each fact), restricted to messages that name the person or their relation (father, dad, mother, mom...). No embeddings. In the live cases, include one paraphrase the word list must catch (for example "we were never able to start a family" for children) and report any paraphrase it misses, so Patrick can decide later whether meaning-based search is worth it.
2. The question tool can add a fact question already closed in one call (outcome answered or unknown, the person's words as the answer), so "we can't have children" and "my father is still alive" are stored as answered when said. Default for "can't have children": the couple's children item counts answered (no children) and is never asked again. Add a prompt line in the fidelity fragment, BOTH public btcopilot/prompty/fragments/ and the private sops copy under private/prompts/fragments/ (kept identical, private re-encrypted), telling the coach to store such statuses as answered when said.
3. The tool refuses a second open asked fact question on the same person and item while one is open, and says so to the coach (soft: it steers, it cannot block free text).
4. Time zone: the page sends the browser's IANA zone (Intl.DateTimeFormat().resolvedOptions().timeZone) with each chat message; the coach's "today", the follow-up date check and the asked-on date are computed in that zone. Server stays UTC; stored timestamps stay naive UTC. No new column. The scheduled follow-up job keeps using UTC.
No new table, column or record field. If anything needs one, stop and write `question:`.

## Files you may touch
btcopilot/toolbox.py, btcopilot/questions.py, btcopilot/coverage.py, btcopilot/coachturn.py, the chat route that receives a message (find it; doc/API.md), the web file that sends a chat message under web/src/, the two fidelity fragments, btcopilot/tests/test_coverage.py, the test files for the tool, questions and chat route, btcopilot/tests/live/ (new cases), btcopilot/tests/prompt_goldens.json and private/goldens.json (regenerated the repo's way), private/oracle/topics/ + bin/oracleindex.py output + btcopilot/tests/conventions/fingerprints.txt (one new ruling: Patrick's words above as evidence; cite it in every new test; never author anything he did not say), doc/COVERAGE.md, doc/API.md, private/replays/ (new saved replies). Anything else: `question:`.

## Tests you must run (no full suite)
`uv run pytest -m "not conventions" btcopilot/tests/test_coverage.py btcopilot/tests/test_promptfiles.py <the tool, questions, chat-route test files> -q`; `uv run pytest -m conventions btcopilot/tests/conventions -q`; web: the repo's typecheck and unit tests for the file you changed. Deterministic tests: a closed children or alive question makes the item known; an asked fact question on a known item is refused with the answer; a closed question added in one call; a duplicate open question refused; "today" follows the sent zone (an evening in America/Anchorage when UTC is already tomorrow). Each new test must fail with its change removed.
Live, on the free subscription replay only (never an API key, never real money): two fictional cases in the style of test_repeats.py: (a) the person says "we can't have children" in message 1, then a later turn invites the children question; (b) the person gives the father's birth date and "my parents are still married", then a turn invites alive/age. Pass: the reply asks no children / alive / age question, 3 of 3 runs. Plus the existing test_repeats.py cases still pass.

## Done
Work branch pushed; report.md (at most 10 lines): last commit, tests run with counts, replay results k of 3 per case, the ruling id, anything unfinished. Use Opus sub-agents for building; Fable only for a design doubt.

## Must not
Push master or FD-371, merge, open or change a PR, touch production, a sandbox on another machine, Jira, .env files or secrets beyond decrypting the prompts and rulings, make real model API calls, run the full suite, add a migration.
