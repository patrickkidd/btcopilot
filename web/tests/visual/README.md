# Visual goldens

What the companion page is supposed to look like, as pictures you can open. A
change to the drawing fails these until someone looks at the new picture and
accepts it.

They are taken against the fixture records in
`btcopilot/companion/fixtures.py` — the sparse and dense shapes the picture has
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
| `COMPANION_URL` | `http://127.0.0.1:8889` |
| `FIXTURE_CMD` | `uv run flask companion fixtures` |
| `FIXTURE_CWD` | `~/theapp` |

The fixture command needs the same `FLASK_APP`, `FLASK_CONFIG`,
`FLASK_SQLALCHEMY_DATABASE_URI` and `PYTHONPATH` the sandbox runs with, so run
the tests from a shell that has them.

## Accepting a change

```
npm run test:visual:update
```

Then look at every picture that changed before committing it. The goldens live
beside their spec in `*-snapshots/`, named `<what>-<project>-<platform>.png`;
the ones in the branch were taken on macOS with headless Chromium at
`deviceScaleFactor: 2`, at 390x844 (phone) and 1280x800 (desktop).
