"""Saved coach responses, so a paid response is paid for once (R-0508; the
2026-09-25 spend rule). Each real call is saved under a hash of the whole
request; a later run replays it when the hash matches and calls the model only
when it does not, so a changed prompt or tool re-spends only on the calls it
changes. A replayed call costs nothing.

The same request seen again in one case is a new sample, not a repeat: its
hash takes the count of times it was seen before in the case, so a case run
k of n times replays n different saved responses.

The saved file holds the prompt only by hash. The response itself can echo the
private prompt, so the suite's store is sealed with sops like the prompts.

Dump mode spends nothing: a call with no saved response writes its whole request
to a file named by the key it would be saved under, and the case awaits an
answer written on the Claude Code subscription (answer.py)."""

import datetime
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
from btcopilot.quality import Source

REPO = Path(__file__).parents[3]
STORE = REPO / "private" / "replays"


class Mode(enum.StrEnum):
    Replay = "replay"
    Record = "record"
    Only = "only"
    Dump = "dump"

    @property
    def offline(self) -> bool:
        return self in (Mode.Only, Mode.Dump)


class Miss(Exception):
    pass


def request(model, system, messages, tools) -> dict:
    return {
        "model": model.model,
        "effort": model.effort,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": messages,
        "tools": tools,
    }


def request_hash(model, system, messages, tools) -> str:
    return hashlib.sha256(
        json.dumps(request(model, system, messages, tools), sort_keys=True, default=str).encode()
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
    def __init__(
        self, mode: Mode, store: Path = STORE, seal: bool = True, requests: Path | None = None
    ):
        self.mode, self.store, self.seal, self.requests = mode, store, seal, requests
        self.seen: Counter = Counter()
        self.replayed = self.recorded = 0
        self.awaiting: list[str] = []
        self.subscribed = mode is Mode.Dump

    def begin(self) -> None:
        self.seen.clear()
        self.awaiting.clear()

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
                raw = json.loads(promptdir.read(path))
                self.subscribed |= Source(raw["source"]) is Source.Subscription
                saved = loaded(raw)
                if saved.text:
                    yield saved.text
                return saved
            if self.mode is Mode.Dump:
                self.requests.mkdir(parents=True, exist_ok=True)
                (self.requests / path.name).write_text(
                    json.dumps(request(model, system, messages, tools), indent=2, default=str)
                )
                self.awaiting.append(path.name)
                raise Miss(f"awaiting an answer to {self.requests / path.name}")
            if self.mode is Mode.Only:
                raise Miss(f"no saved response for this request ({path.name})")
            answered = yield from real(model, system, messages, tools, turn_id)
            self.save(path, answered)
            return answered

        return turn

    def save(self, path: Path, answered: ModelTurn, source: Source = Source.Api) -> None:
        self.recorded += 1
        self.store.mkdir(parents=True, exist_ok=True)
        # Spent stays behind: a replay is free, and its tokens are not charged.
        row = asdict(answered)
        row.pop("spent")
        row["source"] = source
        row["date"] = datetime.date.today().isoformat()
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

