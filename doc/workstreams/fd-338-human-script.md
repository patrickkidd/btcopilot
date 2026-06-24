# Rebuild Diagram — Human Validation Walk (C12)

**What this walk decides.** The bet behind this feature: one tap rebuilds your fragmented family diagram into a structure you recognize as your family — trustworthy enough to be the foundation later features build on. Everything countable (connection numbers, progress, cards, badges, saving mechanics) is already machine-checked. Do not re-check any of that. You are here for the one thing no harness can judge: is this your family as you know it?

## Setup

The test backend is already running. Launch the app with:

```
cd /Users/patrick/worktrees/deep-reextract/familydiagram && PYTHONPATH=/Users/patrick/worktrees/deep-reextract/familydiagram:/Users/patrick/worktrees/deep-reextract/btcopilot FD_SERVER_URL_ROOT=http://127.0.0.1:8889 /Users/patrick/theapp/.venv/bin/python pkdiagram/main.py --personal
```

If the rebuild errors immediately after you start it, the backend may be down — tell the assistant rather than debug it yourself.

## Main path

### A1 — Open your diagram

Arrange: The app is running (setup above).

Act: Open your own personal diagram — the one built up from your past conversations. Then tap the "Discuss" title at the top of the screen and pick one of your discussions from the dropdown — the rebuild button only shows up once a discussion is selected.

Assert:
- The screen shows your diagram as you last left it: your people present but scattered, many not connected to anyone.
- A grey circular-arrow rebuild button appears at the top right, next to the red badge.

### A2 — Run the rebuild

Arrange: Your diagram is open with a discussion selected (A1). Leave the "Max fidelity" switch off.

Act: Tap the grey circular-arrow rebuild button at the top right and wait — it takes about 2 minutes.

Assert:
- When it finishes, the screen shows a review of proposed people and connections for you to accept or reject.
- No error message appeared.

### A3 — Review and accept

Arrange: The review of proposed changes is on screen.

Act: Look through the proposed cards. One known wart you may see: a proposed person named "Client" that duplicates you — reject that one card and move on. It is a known bug already on the list, not part of your judgment. Then accept everything else.

Assert:
- The rejected "Client" card disappears from the review.
- After you accept, the review closes and the drawn diagram shows the rebuilt family.

### A4 — Judge the family

Arrange: The rebuilt family is drawn on screen.

Act: Look at the drawn family and compare it against your own knowledge — you are the only person who can.

Assert:
- The drawing shows your partner connected to you by a couple line.
- Every couple you know of — your parents, your partner's parents, married siblings — appears as a pair joined by a couple line.
- Each child appears under their correct parent pair, joined to that couple by a line.
- Your side of the family shows as one connected group — every relative of yours present in it, linked by lines, none floating alone.
- Your partner's side shows as one connected group the same way.
- At most exactly two people appear unconnected — a friend and an ex. Those two alone is correct, not a failure.

### A5 — Quit and come back

Arrange: You have accepted the rebuild and the family is on screen.

Act: Quit the app completely. Launch it again with the same command from the setup block, and reopen the same diagram.

Assert:
- After the relaunch, the reopened diagram still shows the same connected family structure you accepted — the same couple lines and child lines drawn as before you quit, so the saved diagram itself holds the rebuilt family, not just the screen you left behind.
- Nothing has reverted to the scattered state you started from in A1.
- Give your verdict, GO or NO-GO: GO if the drawn diagram is your family as you know it — the right people connected to the right people, trustworthy as the base later features build on.
- NO-GO if people are connected wrongly or groups that should hang together don't — note who is wrong and tell the assistant.

## Optional — skip freely

The walk above is complete without these.

- **Cancel mid-run:** start another rebuild and tap cancel while it is running. Look at the diagram: nothing changed.
- **Max fidelity:** run a rebuild with the "Max fidelity" switch on. It takes longer and costs about $0.60; expect a similar result.
