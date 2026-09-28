"""Runs live cases on the Claude Code subscription, $0: dumps every coach call
that has no saved answer, answers each through `claude -p` with the coach's
own system prompt and tools (btcopilot/tests/live/subscription.py), saves it
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

from btcopilot.tests.live.answer import saved
from btcopilot.tests.live.replay import REPO, Mode
from btcopilot.tests.live.subscription import answer

ROUNDS = 12
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
        for round in range(ROUNDS):
            requests = scratch / f"requests{round}"
            ran = dumped(args, requests)
            waiting = sorted(requests.glob("*.json")) if requests.exists() else []
            if not waiting:
                print(ran.stdout[-2000:])
                return ran.returncode
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
