"""The pairing prompt against Patrick's own pairing of the High School Sleep
Problems cut: four coders' 191 events, which he put together by hand into 66
things [Oracle: R-0964]. Names, places and exact days are fictionalized
(fd-corpus/private/eval/pairing/cut.json in the private corpus: the chat is
real, so it never enters this repo); every coder's line number and what they
wrote is kept.

The call is the app's own: the pairing prompt rendered by pairing.py, sent
through claude_structured on Fable, answered on the subscription."""

import asyncio
import functools
import json

import pytest

from btcopilot import llmutil
from btcopilot.review import pairing
from btcopilot.review.models.item import PairingConfidence
from btcopilot.review.pairing import CODER, KINDS, Answer
from btcopilot.tests.live.conftest import REPLAY
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.repo import SOURCES

PRIVATE = SOURCES / "fd-corpus" / "private" / "eval" / "pairing" / "cut.json"


@functools.cache
def cut() -> dict:
    return json.loads(PRIVATE.read_text())
# Of his 66 pairings of events, how many the call must give exactly: three in
# four. Every one it misses must touch a pairing it did not mark sure, so his
# review of the unsure ones first brings it up (R-0963).
KEPT = 50


@pytest.fixture
def answered(request, monkeypatch):
    replay = request.config.stash[REPLAY]
    monkeypatch.setattr(
        llmutil, "claude_structured", replay.structured(llmutil.claude_structured)
    )


def written() -> list[dict]:
    return [
        {
            "coding_id": coding["coding_id"],
            "coder": CODER,
            **{
                key: [
                    pairing.said(
                        {k: v for k, v in item.items() if k != "line"}, item.get("line")
                    )
                    for item in coding[key]
                ]
                for key in KINDS.values()
            },
        }
        for coding in cut()["codings"]
    ]


@functools.cache
def events() -> set[tuple[int, int]]:
    return {
        (coding["coding_id"], event["id"])
        for coding in cut()["codings"]
        for event in coding["events"]
    }


def events_paired(answer: Answer) -> list[tuple[list[list[int]], PairingConfidence]]:
    found = []
    for one in answer.pairings:
        keys = sorted(
            [e.coding_id, e.item_id]
            for e in one.entries
            if (e.coding_id, e.item_id) in events()
        )
        if keys:
            found.append((keys, PairingConfidence(one.confidence)))
    return found


@passes(1, of=1)
def test_the_call_pairs_the_events_as_patrick_did(answered):
    # R-0964, R-0961
    prompt = pairing.render(cut()["lines"], written())
    parsed = asyncio.run(
        llmutil.gemini_structured(
            prompt,
            Answer,
            model=pairing.MODEL,
            schema=pairing.SCHEMA,
            limit=pairing.LIMIT,
        )
    )
    versions = {
        (coding["coding_id"], item["id"]): (kind,)
        for coding in cut()["codings"]
        for kind, key in KINDS.items()
        for item in coding[key]
    }
    groups = [
        [(e.coding_id, e.item_id) for e in p.entries] for p in parsed.value.pairings
    ]
    assert (
        pairing.problems(groups, versions, {c["coding_id"] for c in cut()["codings"]})
        == {}
    )
    given = events_paired(parsed.value)
    exact = [keys for keys, _ in given]
    missed = [one for one in cut()["answer"] if one not in exact]
    assert len(cut()["answer"]) - len(missed) >= KEPT, f"missed: {missed}"
    doubtful = {
        tuple(key)
        for keys, sure in given
        if sure is not PairingConfidence.Sure
        for key in keys
    }
    hidden = [one for one in missed if not doubtful & {tuple(k) for k in one}]
    assert not hidden, f"missed and marked sure: {hidden}"
