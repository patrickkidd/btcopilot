# FD-321 — Human Validation

Judge a PASS by this success-picture:
- A fresh Personal app raises a **Welcome** setup screen with no prompting.
- The name you enter once is the cross-app **identity spine**: same name on the diagram node, the chat speaker label, and the account drawer.
- That identity survives a restart — no re-onboarding, name still there.

## Ground rules (read once)
- Everything runs in a **SANDBOX**: a throwaway SQLite server on port 62090. NOT production.
- Every command below is pre-filled. Nothing to substitute — paste as-is.
- Don't lead the witness: in A1, judge whether the Welcome screen appears **on its own**. Do not assume it will.

## A1 — Bring the sandbox up
Act:
```bash
bash /Users/patrick/worktrees/FD-321/btcopilot/doc/workstreams/FD-321/fd321_sandbox.sh up
```
Assert:
- A Personal-app window AND a Pro-app window appear.
- The Personal app shows a **Welcome** setup screen unprompted.

## A2 — Onboard (Personal app gesture)
In the Welcome screen, type your real first + last name and a birth date, then click **Get Started**.
Assert:
- The Welcome screen closes; the main app appears.

## A3 — Confirm the server recorded it
Act:
```bash
bash /Users/patrick/worktrees/FD-321/btcopilot/doc/workstreams/FD-321/fd321_sandbox.sh state
```
Assert:
- ACCOUNT NAME shows your name; DIAGRAM NODE(S) shows your name as primary.

## A4 — The spine: same name in all three (gesture)
In the Pro app open the diagram (close and re-open it if already open). In the Personal app read the chat speaker label and open the account drawer (hamburger menu).
Assert:
- Pro diagram node shows your name.
- Chat speaker label shows your name, not "Client".
- Account drawer shows your name.

## A5 — Survives restart (persistence)
Quit the Personal-app window, then relaunch it against the same running server.
Act:
```bash
bash /Users/patrick/worktrees/FD-321/btcopilot/doc/workstreams/FD-321/fd321_sandbox.sh relaunch-personal
bash /Users/patrick/worktrees/FD-321/btcopilot/doc/workstreams/FD-321/fd321_sandbox.sh state
```
Assert:
- The app returns with your name shown and NO Welcome screen.
- `state` still records your name.

## Teardown
```bash
bash /Users/patrick/worktrees/FD-321/btcopilot/doc/workstreams/FD-321/fd321_sandbox.sh down
```

## Optional
- Empty first name keeps **Get Started** disabled.
- **Skip for now** on a fresh profile leaves the app usable.
