# Visual goldens

What the chat page is supposed to look like, as pictures you can open. A
change to the drawing fails these until someone looks at the new picture and
accepts it.

They are taken against the fixture records in
`btcopilot/fixtures.py` — the sparse and dense shapes the picture has
to survive, one record whose labels are long enough to break a chip out of its
bubble, and one holding a moment per move the picture can draw. Nobody's real
record is ever involved.

## Running them

Start a sandbox server on 8889 against a throwaway database, then, from `web/`:

```
npm run test:visual
```

Environment, if your sandbox is elsewhere:

| variable | default |
|---|---|
| `SANDBOX_URL` | `http://127.0.0.1:8889` |
| `FIXTURE_CMD` | `uv run flask app fixtures` |
| `FIXTURE_CWD` | `~/theapp` |

The fixture command needs the same `FLASK_APP`, `FLASK_CONFIG`,
`FLASK_SQLALCHEMY_DATABASE_URI` and `PYTHONPATH` the sandbox runs with, so run
the tests from a shell that has them.

## The review walks

`sandbox*.spec.ts` are not pictures. Each one drives a whole journey through
the running review sandbox — the table, the ballot, the meeting and its
result, the meeting read line by line, the family structure, the chat app's own
screens, the scribe, and tapping on the coding thread — and checks a sentence
about behaviour at every step. They run as their own projects
(`sandbox-phone`, `sandbox-webkit`, `sandbox-desktop`) and skip unless the
sandbox and its sign-in links are named in the environment, so a plain golden
run never waits on them. `tests/visual/sandbox.ts` says which variables.

The scripts in `~/worktrees/fd362-sandbox` set those variables and reset the
fixture between walks: `runspec.sh <spec> <width> <height> <tag>` runs one,
`runall.sh` runs the table, the ballot and the meeting in order.

## The thread walks

`sandboxthreads`, `sandboxhandedit`, `sandboxhandundo` and `sandboxlive` check
the chat thread and the lists drawer against stand-in families that
`btcopilot/tests/frontend/` seeds. Run the seed scripts from the repo root with
the sandbox's Flask settings, then name what they print:

| variable | what |
|---|---|
| `INVITE_TURNS` | the link `seedturns.py` prints |
| `THREAD_LINKS` | a file holding what `seedthreads.py` prints, plus `"std": {"link": <INVITE_TURNS>}` |
| `SANDBOX_PG` | the sandbox's Postgres container, read only (`sandboxhandedit`) |
| `SANDBOX_ENV` | a shell file with the sandbox's Flask settings (`sandboxhandundo`, which runs its script from `FIXTURE_CWD`) |
| `SANDBOX_LIVE` | set to 1 to let `sandboxlive` make real coach turns, on local Ollama unless the sandbox was started with `SANDBOX_MODEL=anthropic` |
| `SANDBOX_NO_MODEL` | set to 1 when the sandbox has no model key, for the try-again walk in `sandboxthreads` |
| `SANDBOX_WALKS_ONLY` | set to 1 to skip installing the golden fixtures first |

## Accepting a change

```
npm run test:visual:update
```

Then look at every picture that changed before committing it. The goldens live
beside their spec in `*-snapshots/`, named `<what>-<project>-<platform>.png`;
the ones in the branch were taken on macOS with headless Chromium at
`deviceScaleFactor: 2`, at 390x844 (phone) and 1280x800 (desktop).
