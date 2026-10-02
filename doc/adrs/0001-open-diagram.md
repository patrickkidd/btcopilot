# ADR 0001: The web app opens a diagram in one step, from one store

Status: accepted, 2026-10-01 (FD-366, approved by Patrick).

## Context

The page kept two copies of which diagram was in use (the account's column on
the server and a variable in the page), five places that changed the page's
copy, four more copies kept by hand (the title, the product events, the
read-only flag, the ticks on the diagrams list), and seven separate fetch
paths. Most reads named no diagram and got whatever the server column said at
that moment. Nothing tore the old diagram down on a switch: a coach turn still
running kept drawing into the new chat, an older page of chat landed above it,
and the slower of two switches could draw last. Four reported bugs on
2026-10-01 each came from one of these paths and were fixed one screen at a
time.

## Decision

- One module, `web/src/store.ts`, holds the open diagram: the diagram, its
  record and questions, the newest thread page, its sittings, the running
  turn's stream and the abort controller of its pending reads.
- One step, `store.open(id)`, opens a diagram for the first load and every
  switch: abort the pending reads and the running turn's stream, reset every
  registered screen, read every part by id in parallel, draw every screen.
  An open overtaken by a later one draws nothing.
- Screens register a reset and a draw with the store and read only from it;
  any request about the open diagram goes through the store so its answer is
  dropped after a switch.
- Every request about the diagram names its id; the server checks that the
  caller may open that id (owner, granted, or an admin looking read-only) and
  answers 404 otherwise. No tables, no migration, no change to the tools.

## Consequences

- A new screen that shows the open diagram registers with the store; it does
  not add a fetch path or a copy of which diagram is open.
- Another tab or phone switching the account's diagram no longer changes what
  this page reads; the server column only decides where the next load lands.
- The coding screen and the cut picker show other diagrams by design and keep
  their own reads.
