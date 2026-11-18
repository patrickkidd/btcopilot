"""The pairing prompt on two cuts. Patrick's own pairing of the High School
Sleep Problems cut: four coders' 191 events, which he put together by hand into
66 things [Oracle: R-0964]. Names, places and exact days are fictionalized
(fd-corpus/private/eval/pairing/cut.json in the private corpus: the chat is
real, so it never enters this repo); every coder's line number and what they
wrote is kept. And an invented cut on the stand-in family, so the prompt is
tested on something other than the cut its rules were drawn from.

The call is the app's own: the pairing prompt rendered by pairing.py, sent
through gemini_structured, which hands a Claude model to claude_structured, as
Metered.structured does for the worker's job; answered on the subscription."""

import asyncio
import functools
import json
import re

import pytest

from btcopilot import llmutil
from btcopilot.review import pairing
from btcopilot.review.models.item import PairingConfidence
from btcopilot.review.pairing import KINDS, Answer
from btcopilot.tests.live.conftest import REPLAY
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.repo import SOURCES

PRIVATE = SOURCES / "fd-corpus" / "private" / "eval" / "pairing" / "cut.json"

# Of his 66 pairings of events, how many the call must give exactly: three in
# four. Every one it misses must touch a pairing it did not mark sure, so his
# review of the unsure ones first brings it up (R-0963).
# The answer key is the same conversation the prompt's rules were drawn from, and this bar of 50 of 66 was set by the builder, not ruled.
KEPT = 50


def death(id: int, person: int, date: str | None, precision: str | None) -> dict:
    return {
        "id": id,
        "kind": "death",
        "person": person,
        "line": 11,
        **({"dateTime": date, "datePrecision": precision} if date else {}),
    }


def person(id: int, name: str, gender: str, line: int = 11) -> dict:
    return {"id": id, "name": name, "gender": gender, "line": line}


# Three coders on three lines of the stand-in family: two deaths said in one
# line that must stay apart, a grandparent under two names in each pair, and
# one line coded three ways with nothing in common on its face.
INVENTED = {
    "lines": [
        [11, "Corinne", "My grandfather Errol died in 1989, and my grandmother Odile in March 1998."],
        [12, "Coach", "What happened after your father left Arizona?"],
        [13, "Corinne", "That winter I just stopped calling home. I didn't talk to anyone in the family for months."],
    ],
    "codings": [
        {
            "coding_id": 1,
            "people": [
                person(1, "Corinne", "female", 13),
                person(2, "Odile", "female"),
                person(3, "Errol", "male"),
            ],
            "couples": [],
            "events": [
                death(10, 2, "1998-03-01", "month"),
                death(11, 3, "1989-01-01", "year"),
                {"id": 12, "kind": "shift", "person": 1, "relationship": "cutoff", "title": "Cut off from the family", "line": 13},
            ],
        },
        {
            "coding_id": 2,
            "people": [
                person(5, "Corinne", "female", 13),
                person(6, "Corinne's grandmother", "female"),
                person(7, "Errol", "male"),
            ],
            "couples": [],
            "events": [
                death(20, 7, None, None),
                death(21, 6, "1998-01-01", "year"),
                {"id": 22, "kind": "noted", "person": 5, "title": "A quiet winter", "line": 13},
            ],
        },
        {
            "coding_id": 3,
            "people": [
                person(1, "Corinne", "female", 13),
                person(4, "Odile", "female"),
                person(8, "Grandpa", "male"),
            ],
            "couples": [],
            "events": [
                death(30, 4, "1998-03-01", "month"),
                death(31, 8, "1989-01-01", "year"),
                {"id": 32, "kind": "shift", "person": 1, "functioning": "down", "title": "Kept to herself", "line": 13},
            ],
        },
    ],
    "answer": [
        [[1, 1], [2, 5], [3, 1]],
        [[1, 2], [2, 6], [3, 4]],
        [[1, 3], [2, 7], [3, 8]],
        [[1, 10], [2, 21], [3, 30]],
        [[1, 11], [2, 20], [3, 31]],
        [[1, 12], [2, 22], [3, 32]],
    ],
}


@functools.cache
def cut() -> dict:
    return json.loads(PRIVATE.read_text())


@pytest.fixture
def answered(request, monkeypatch):
    replay = request.config.stash[REPLAY]
    monkeypatch.setattr(
        llmutil, "claude_structured", replay.structured(llmutil.claude_structured)
    )


def names(case: dict) -> dict[int, str]:
    ids = [coding["coding_id"] for coding in case["codings"]]
    return pairing.labels(ids, set(ids))


def named(reason: str, case: dict) -> bool:
    """A reason that names a coding by its label or its number (R-0969)."""
    return any(
        re.search(rf"\b{re.escape(label)}\b", reason, re.IGNORECASE)
        for label in names(case).values()
    ) or bool(pairing.NUMBERED.search(reason))


def written(case: dict) -> list[dict]:
    return [
        pairing.block(
            names(case)[coding["coding_id"]],
            True,
            {
                kind: [
                    pairing.said(
                        {k: v for k, v in item.items() if k != "line"}, item.get("line")
                    )
                    for item in coding[key]
                ]
                for kind, key in KINDS.items()
            },
        )
        for coding in case["codings"]
    ]


def paired(case: dict) -> list[tuple]:
    """The app's call on `case`, held to the fixed check and to reasons that
    name no coding; its pairings as (entries, reason, confidence)."""
    parsed = asyncio.run(
        llmutil.gemini_structured(
            pairing.render(case["lines"], written(case)),
            Answer,
            model=pairing.MODEL,
            schema=pairing.SCHEMA,
            limit=pairing.LIMIT,
        )
    )
    versions = {
        (coding["coding_id"], item["id"]): (kind,)
        for coding in case["codings"]
        for kind, key in KINDS.items()
        for item in coding[key]
    }
    groups = pairing.unlabelled(parsed.value, names(case))
    assert (
        pairing.problems(
            [g[0] for g in groups], versions, {c["coding_id"] for c in case["codings"]}
        )
        == {}
    )
    raw = [p.reason for p in parsed.value.pairings if named(p.reason, case)]
    print(f"reasons naming a coding before the rewrite: {len(raw)} {raw[:3]}")
    assert not [reason for _, reason, _ in groups if named(reason, case)]
    return groups


def given(
    groups: list[tuple], keep: set[tuple[int, int]] | None = None
) -> list[tuple[list[list[int]], PairingConfidence]]:
    found = []
    for entries, _, confidence in groups:
        keys = sorted(list(key) for key in entries if keep is None or key in keep)
        if keys:
            found.append((keys, PairingConfidence(confidence)))
    return found


@passes(2, of=3)
def test_the_call_pairs_the_events_as_patrick_did(answered):
    # R-0964, R-0961, R-0969
    events = {
        (coding["coding_id"], event["id"])
        for coding in cut()["codings"]
        for event in coding["events"]
    }
    found = given(paired(cut()), events)
    exact = [keys for keys, _ in found]
    missed = [one for one in cut()["answer"] if one not in exact]
    print(f"exact: {len(cut()['answer']) - len(missed)} of {len(cut()['answer'])}")
    assert len(cut()["answer"]) - len(missed) >= KEPT, f"missed: {missed}"
    doubtful = {
        tuple(key)
        for keys, sure in found
        if sure is not PairingConfidence.Sure
        for key in keys
    }
    hidden = [one for one in missed if not doubtful & {tuple(k) for k in one}]
    assert not hidden, f"missed and marked sure: {hidden}"


@passes(2, of=3)
def test_the_call_pairs_an_invented_cut_it_was_not_written_from(answered):
    # R-0964, R-0961, R-0968
    exact = [keys for keys, _ in given(paired(INVENTED))]
    missed = [one for one in INVENTED["answer"] if one not in exact]
    print(f"invented exact: {len(INVENTED['answer']) - len(missed)} of {len(INVENTED['answer'])}")
    assert not missed, f"missed: {missed}"
