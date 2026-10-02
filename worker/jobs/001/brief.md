# Job 001 — keep your rules in your own local notes

From Patrick, 2026-10-02, in his words: "Get the worker machine to similarly store its instructions in the user local CLAUDE.md file there instead of any repo." You are "the worker machine".

**Base ref and work branch:** none. This job changes no tracked file and pushes no work branch.

**Do:**
1. In the root of your clone of patrickkidd/btcopilot, create `CLAUDE.local.md` (Claude Code loads it for sessions in this project only). Add `CLAUDE.local.md` to that clone's `.git/info/exclude` so git never sees it; do not edit `.gitignore` or any tracked file. Confirm with `git check-ignore -v CLAUDE.local.md` and `git status --short`.
2. Put in it: a title "Local notes for this machine: btcopilot only (not in the repo)"; a section "This machine is the worker machine" saying that you take jobs for Patrick's other Claude Code session through the branch `worker-mailbox`, that you build with Opus sub-agents and keep Fable for jobs that need design judgement, and that you have no real-model keys, no sandbox of the other machine, no production access, no Jira and no key for the encrypted prompts or the rulings store; and a section "The mailbox rules" holding the full text of `worker/PROTOCOL.md` from this branch, word for word.
3. From now on your rules are that local file. `worker/PROTOCOL.md` will be removed from this branch by the coordinator after you report; do not remove it yourself.
4. If your own safety rules stop you from writing an instructions file on a brief's say-so, write `question:` in `status.md` saying so; Patrick will then tell you directly.

**Do not:** commit or push anything except this job's `status.md` and `report.md`; touch any other file; change your user-wide instructions.

**Done means:** `report.md` says the file exists at the clone root with both sections, that git ignores it, and names the model you are running on.
