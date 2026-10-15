"""Runs live cases on the Claude Code subscription, $0: dumps every coach call
that has no saved answer, answers each through `claude -p` with the coach's
own system prompt and tools (btcopilot/subscription.py), saves it
to the replay store marked as the subscription's, and runs again until no
call is left unanswered. The last run is the verdict.

SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt uv run python bin/subscribe.py \\
    btcopilot/tests/live/test_coachturn.py -k graduate_school
"""

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from btcopilot.coachturn import MAX_STEPS
from btcopilot.tests.live.answer import saved
from btcopilot.tests.live.replay import REPO, Mode
from btcopilot.subscription import answer

# A case stops at its first unanswered call, so it takes one round per call in
# its longest chain: up to twelve coach turns of at most MAX_STEPS calls each.
ROUNDS = 12 * MAX_STEPS
PARALLEL = 4


def dumped(args: list[str], requests: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, LIVE_REPLAY=Mode.Dump, LIVE_REQUESTS=str(requests))
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--e2e",
            "-q",
            "-p",
            "no:cacheprovider",
            *args,
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )


def answered(request: Path, work: Path) -> str:
    message = answer(json.loads(request.read_text()), work)
    saved(request.name, message)
    calls = [b["name"] for b in message["content"] if b["type"] == "tool_use"]
    return f"{request.name}: {calls or 'words only'}"


def main(args: list[str]) -> int:
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        done = set()
        for round in range(ROUNDS):
            requests = scratch / f"requests{round}"
            ran = dumped(args, requests)
            waiting = sorted(requests.glob("*.json")) if requests.exists() else []
            if not waiting:
                print(ran.stdout[-2000:])
                return ran.returncode
            again = [r.name for r in waiting if r.name in done]
            if again:
                raise SystemExit(f"answered but not replayed: {again}")
            done |= {r.name for r in waiting}
            with ThreadPoolExecutor(PARALLEL) as pool:
                for line in pool.map(
                    answered,
                    waiting,
                    [scratch / f"work{i}" for i in range(len(waiting))],
                ):
                    print(f"round {round + 1}: {line}", flush=True)
    raise SystemExit(f"still awaiting answers after {ROUNDS} rounds")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
