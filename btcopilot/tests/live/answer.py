"""Saves an answer written on the Claude Code subscription to a request the
suite dumped (LIVE_REPLAY=dump), in the replay store under the request's own
key, sealed like the rest and marked as the subscription's, so the next run
replays it at no API cost.

uv run python -m btcopilot.tests.live.answer <request file> <answer file>

The answer file is the assistant message in the Anthropic response shape:
{"model": ..., "content": [text and tool_use blocks]}.
"""

import json
import sys
from pathlib import Path

from btcopilot.coachmodel import message_turn
from btcopilot.quality import Source
from btcopilot.tests.live.replay import STORE, Mode, Replay


def saved(name: str, message: dict, store: Path = STORE, seal: bool = True) -> Path:
    path = store / name
    Replay(Mode.Replay, store, seal).save(path, message_turn(message), Source.Subscription)
    return path


def save(request: Path, answer: Path, store: Path = STORE, seal: bool = True) -> Path:
    return saved(request.name, json.loads(answer.read_text()), store, seal)


if __name__ == "__main__":
    print(save(Path(sys.argv[1]), Path(sys.argv[2])))
