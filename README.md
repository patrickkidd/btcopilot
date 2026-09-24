# btcopilot

The server and web app for Family Diagram's chat app: a coach, trained in Bowen
theory, who never forgets your family. You talk to it by voice or text; it asks
what a trained coach asks and keeps the family record (people, pair-bonds, events
and the clusters they form) as a picture pinned above the chat. The coach edits the
record turn by turn with its tools; you can correct anything on the picture by hand.

The Pro desktop app's backend and the training app live on branch `master-legacy`.
`btcopilot.schema` is the one module the desktop apps import; it depends on nothing
else in the package.

## What runs

| Part | Where |
|------|-------|
| Flask app (the chat app's API, sign-in, the review, admin commands) | `btcopilot/` |
| The page (TypeScript, built with Vite into the package) | `web/` |
| Database: Postgres in production, SQLite in tests; one migration from empty | `btcopilot/migrations/`, `alembic.ini` |
| Background work: Celery on Redis | `btcopilot/celery.py` |
| Prompts, encrypted with sops (the open defaults run without the key) | `private/prompts/`, `btcopilot/prompty/` |
| The box: one compose file, Caddy, Grafana Alloy | `deploy/` |

A merge to master builds the image, tags it `3.YYYY.M.D.N+g<sha7>`, pushes it to
GHCR and rolls it onto the box without dropping a request (`.github/workflows/release.yml`,
runbook in `deploy/README.md`). `/health` answers with the running version.

## Working on it

```bash
uv sync --extra app --extra test
npm --prefix web ci && npm --prefix web run build
uv run pytest btcopilot/tests          # the Python suite
npm --prefix web test                  # the page's unit tests
npm --prefix web run test:visual       # Playwright goldens against a sandbox on 8889
FLASK_APP=btcopilot.app:create_app uv run flask run -p 8889
FLASK_APP=btcopilot.app:create_app uv run flask admin db upgrade
```

Admin commands for the box run as `flask admin ...`; `flask admin --help` lists them.

## Where the truth lives

- [doc/STATE.md](doc/STATE.md) is the current truth: what is built, what is ruled,
  what is open. Read it first.
- [doc/HISTORY.md](doc/HISTORY.md) is how it got there, appended, never rewritten.
- [doc/HOW_THIS_PROJECT_WORKS.md](doc/HOW_THIS_PROJECT_WORKS.md) holds the process rules.
- Patrick's rulings are cited by id (R-0001 and on) and stored encrypted in
  `private/oracle/`; nothing in the open repo restates them.
- [decisions/log.md](decisions/log.md) logs point-in-time decisions;
  [CONTEXT.md](CONTEXT.md) holds the Bowen theory domain model.
- Jira epic FD-362 carries the project at product level.
- Older material is in [doc/archive/](doc/archive/), including the research-phase
  README this file replaced.

## License

See [LICENSE](LICENSE).
