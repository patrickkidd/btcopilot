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
answer written on the Claude Code subscription (answer.py).

The store is a local cache, ignored by the repo (R-0813): a reply is touched
each time it is served, and once per run every reply neither served nor written
in the last KEEP is deleted, unless the repo tracks it."""

import datetime
import enum
import hashlib
import json
import subprocess
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from btcopilot import promptdir
from btcopilot.coachmodel import MAX_TOKENS, ModelTurn, ToolCall, message_turn
from btcopilot.llmutil import (
    NO_ADAPTIVE_THINKING,
    STRUCTURED_EFFORT,
    Hop,
    Parsed,
    Served,
    Spent,
    output_format,
)
from btcopilot.quality import Source
from btcopilot.schema import asdict as plain, from_dict

REPO = Path(__file__).parents[3]
STORE = REPO / "private" / "replays"
KEEP = datetime.timedelta(days=14)


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


def structured_request(prompt, model, schema, limit) -> dict:
    """A structured call in the shape the subscription answers: one user
    message, no tools, and the schema its answer must keep."""
    return {
        "model": model,
        "effort": None if model in NO_ADAPTIVE_THINKING else STRUCTURED_EFFORT,
        "max_tokens": limit,
        "system": "",
        "messages": [{"role": "user", "content": prompt}],
        "tools": [],
        "schema": output_format(schema)["schema"],
    }


def hashed(asked: dict) -> str:
    return hashlib.sha256(
        json.dumps(asked, sort_keys=True, default=str).encode()
    ).hexdigest()


def request_hash(model, system, messages, tools) -> str:
    return hashed(request(model, system, messages, tools))


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

    def prune(self) -> None:
        if not self.store.exists():
            return
        tracked = set()
        if self.store.is_relative_to(REPO):
            listed = subprocess.run(
                ["git", "ls-files", "-z", str(self.store.relative_to(REPO))],
                cwd=REPO,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            tracked = {REPO / name for name in listed.split("\0") if name}
        stale = time.time() - KEEP.total_seconds()
        for path in self.store.glob("*.json"):
            if path not in tracked and path.stat().st_mtime < stale:
                path.unlink()

    def begin(self) -> None:
        self.seen.clear()
        self.awaiting.clear()

    def path(self, model, system, messages, tools) -> Path:
        return self.keyed(request_hash(model, system, messages, tools))

    def keyed(self, request: str) -> Path:
        index = self.seen[request]
        self.seen[request] += 1
        return self.store / f"{request[:32]}-{index}.json"

    def saved(self, path: Path) -> dict | None:
        if not path.exists() or self.mode is Mode.Record:
            return None
        self.replayed += 1
        raw = json.loads(promptdir.read(path))
        path.touch()
        self.subscribed |= Source(raw["source"]) is Source.Subscription
        return raw

    def dumped(self, path: Path, asked: dict) -> Miss:
        if self.mode is Mode.Only:
            return Miss(f"no saved response for this request ({path.name})")
        self.requests.mkdir(parents=True, exist_ok=True)
        (self.requests / path.name).write_text(json.dumps(asked, indent=2, default=str))
        self.awaiting.append(path.name)
        return Miss(f"awaiting an answer to {self.requests / path.name}")

    def structured(self, real):
        """`real` is `llmutil.claude_structured`; the result stands in for it.
        A saved answer is the schema's value as the one text block."""

        async def call(prompt, response_format, model, schema, limit):
            asked = structured_request(prompt, model, schema, limit)
            path = self.keyed(hashed(asked))
            raw = self.saved(path)
            if raw is not None:
                value = from_dict(response_format, json.loads(raw["text"]))
                return Parsed(value, Spent(), Served(raw["served"]["model"]))
            if self.mode.offline:
                raise self.dumped(path, asked)
            parsed = await real(prompt, response_format, model, schema, limit)
            self.save(
                path,
                message_turn(
                    {
                        "model": parsed.served.model,
                        "content": [{"type": "text", "text": json.dumps(plain(parsed.value))}],
                    }
                ),
            )
            return parsed

        return call

    def wrap(self, real):
        """`real` is `CoachModel.turn`; the result stands in for it."""

        def turn(model, system, messages, tools, turn_id=""):
            path = self.path(model, system, messages, tools)
            raw = self.saved(path)
            if raw is not None:
                saved = loaded(raw)
                if saved.text:
                    yield saved.text
                return saved
            if self.mode.offline:
                raise self.dumped(path, request(model, system, messages, tools))
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

