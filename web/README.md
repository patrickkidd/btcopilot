# The companion page

One Vite + TypeScript + SVG page, phone first, installed as a PWA. Flask serves
the built bundle at `/companion/` and injects the CSRF token, the diagram and the
session the user returns to.

Build it, then run the server that serves it:

```bash
npm --prefix web install && npm --prefix web run build
FLASK_APP=btcopilot.app:create_app uv run python -m flask run -p 8889 --no-reload
```

The build writes to `btcopilot/companion/static/web/`, which is not in git: the
Docker image builds it. Nothing serves `/companion/` until you have built it once,
and the page tests need it too.

`npm --prefix web test` runs the unit tests for the chip tokenizer and the
caption's two-tap state machine.
