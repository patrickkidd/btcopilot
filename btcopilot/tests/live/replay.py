"""Saved coach responses, so a paid response is paid for once (R-0508; the
2026-09-25 spend rule). Each real call is saved under a hash of the whole
request; a later run replays it when the hash matches and calls the model only
when it does not, so a changed prompt or tool re-spends only on the calls it
changes. A replayed call costs nothing.

The same request seen again in one case is a new sample, not a repeat: its
hash takes the count of times it was seen before in the case, so a case run
k of n times replays n different saved responses.

The saved file holds the prompt only by hash. The response itself can echo the
private prompt, so the suite's store is sealed with sops like the prompts."""

import enum
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from btcopilot import promptdir
from btcopilot.coachmodel import MAX_TOKENS, ModelTurn, ToolCall
from btcopilot.llmutil import Hop, Served

REPO = Path(__file__).parents[3]
STORE = REPO / "private" / "replays"


class Mode(enum.StrEnum):
    Replay = "replay"
    Record = "record"
    Only = "only"


class Miss(Exception):
    pass


def request_hash(model, system, messages, tools) -> str:
    request = {
        "model": model.model,
        "effort": model.effort,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": messages,
        "tools": tools,
    }
    return hashlib.sha256(
        json.dumps(request, sort_keys=True, default=str).encode()
    ).hexdigest()


def loaded(raw: dict) -> ModelTurn:
    served = raw["served"]
    return ModelTurn(
        text=raw["text"],
        calls=[ToolCall(**call) for call in raw["calls"]],
        blocks=raw["blocks"],
        served=served
        and Served(
            served["model"], [Hop(**hop) for hop in served["hops"]], served["sticky"]
        ),
    )


class Replay:
    def __init__(self, mode: Mode, store: Path = STORE, seal: bool = True):
        self.mode, self.store, self.seal = mode, store, seal
        self.seen: Counter = Counter()
        self.replayed = self.recorded = 0

    def begin(self) -> None:
        self.seen.clear()

    def path(self, model, system, messages, tools) -> Path:
        request = request_hash(model, system, messages, tools)
        index = self.seen[request]
        self.seen[request] += 1
        return self.store / f"{request[:32]}-{index}.json"

    def wrap(self, real):
        """`real` is `CoachModel.turn`; the result stands in for it."""

        def turn(model, system, messages, tools, turn_id=""):
            path = self.path(model, system, messages, tools)
            if path.exists() and self.mode is not Mode.Record:
                self.replayed += 1
                saved = loaded(json.loads(promptdir.read(path)))
                if saved.text:
                    yield saved.text
                return saved
            if self.mode is Mode.Only:
                raise Miss(f"no saved response for this request ({path.name})")
            answered = yield from real(model, system, messages, tools, turn_id)
            self.save(path, answered)
            return answered

        return turn

    def save(self, path: Path, answered: ModelTurn) -> None:
        self.recorded += 1
        self.store.mkdir(parents=True, exist_ok=True)
        # Spent stays behind: a replay is free, and its tokens are not charged.
        row = asdict(answered)
        row.pop("spent")
        path.write_text(json.dumps(row, indent=2))
        if self.seal:
            subprocess.run(
                ["sops", "-e", "-i", str(path.relative_to(REPO))],
                cwd=REPO,
                check=True,
                capture_output=True,
            )

    def summary(self) -> str:
        return f"{self.replayed} coach calls replayed, {self.recorded} recorded"

