import json
import os
import subprocess
import time

import pytest

from btcopilot.coachmodel import CoachModel, ModelTurn, Spent, ToolCall, marked_ends
from btcopilot.llmutil import Served
from btcopilot.quality import Source
from btcopilot.tests.live import answer, replay, subscription
from btcopilot.tests.live.replay import KEEP, Miss, Mode, Replay

MESSAGES = [{"role": "user", "content": "My brother moved away last spring."}]
TOOLS = [{"name": "add_event", "input_schema": {"type": "object"}}]


class Wire:
    """The paid call, counted."""

    def __init__(self):
        self.calls = 0

    def turn(self, model, system, messages, tools, turn_id=""):
        self.calls += 1
        yield f"Reply {self.calls}"
        return ModelTurn(
            text=f"Reply {self.calls}",
            calls=[ToolCall("t1", "add_event", {"kind": "moved"})],
            blocks=[{"type": "text", "text": f"Reply {self.calls}"}],
            spent=Spent(input=900, output=40),
            served=Served("claude-sonnet-5"),
        )


def drain(turn):
    words = []
    try:
        while True:
            words.append(next(turn))
    except StopIteration as done:
        return words, done.value


def call(replay, wire, system="The coaching text."):
    return drain(replay.wrap(wire.turn)(CoachModel(), system, MESSAGES, TOOLS))


def test_a_saved_response_replays_with_no_model_call(tmp_path):
    # R-0508, R-0531
    wire = Wire()
    recorded = call(Replay(Mode.Replay, tmp_path, seal=False), wire)
    replayed = call(Replay(Mode.Only, tmp_path, seal=False), wire)
    assert wire.calls == 1
    assert replayed[0] == recorded[0]
    assert replayed[1].calls == recorded[1].calls
    assert replayed[1].served == recorded[1].served
    assert replayed[1].spent == Spent()


def test_a_changed_system_prompt_misses_and_records(tmp_path):
    # R-0508, R-0531
    wire = Wire()
    call(Replay(Mode.Replay, tmp_path, seal=False), wire)
    _, turn = call(Replay(Mode.Replay, tmp_path, seal=False), wire, "Changed text.")
    assert wire.calls == 2
    assert turn.text == "Reply 2"


def test_replay_only_fails_on_a_miss(tmp_path):
    # R-0508, R-0531
    with pytest.raises(Miss):
        call(Replay(Mode.Only, tmp_path, seal=False), Wire())


def test_the_same_request_again_is_a_new_sample(tmp_path):
    # R-0508, R-0531
    wire = Wire()
    first = Replay(Mode.Replay, tmp_path, seal=False)
    texts = [call(first, wire)[1].text for _ in range(3)]
    again = Replay(Mode.Only, tmp_path, seal=False)
    assert [call(again, wire)[1].text for _ in range(3)] == texts
    assert texts == ["Reply 1", "Reply 2", "Reply 3"]


def test_record_calls_the_model_even_when_saved(tmp_path):
    # R-0508, R-0531
    wire = Wire()
    call(Replay(Mode.Replay, tmp_path, seal=False), wire)
    call(Replay(Mode.Record, tmp_path, seal=False), wire)
    assert wire.calls == 2


class Unpaid:
    """A coach with no key: any call is a paid call that must not happen."""

    def turn(self, model, system, messages, tools, turn_id=""):
        raise AssertionError("dump mode reached the model")
        yield


def dumped(tmp_path) -> Replay:
    replay = Replay(Mode.Dump, tmp_path / "store", seal=False, requests=tmp_path / "requests")
    replay.begin()
    with pytest.raises(Miss):
        call(replay, Unpaid())
    return replay


def test_dump_writes_the_request_and_calls_no_model(tmp_path):
    # R-0568
    replay = dumped(tmp_path)
    (request,) = (tmp_path / "requests").glob("*.json")
    assert replay.awaiting == [request.name]
    written = json.loads(request.read_text())
    assert (written["system"], written["messages"], written["tools"]) == (
        "The coaching text.",
        MESSAGES,
        TOOLS,
    )
    assert written["model"] == CoachModel().model
    assert not (tmp_path / "store").exists()


def test_a_subscription_answer_replays_where_replay_only_finds_it(tmp_path):
    # R-0568
    dumped(tmp_path)
    (request,) = (tmp_path / "requests").glob("*.json")
    reply = tmp_path / "reply.json"
    reply.write_text(
        json.dumps(
            {
                "model": "claude-opus-5-5",
                "content": [
                    {"type": "text", "text": "When did he leave?"},
                    {"type": "tool_use", "id": "t1", "name": "add_event", "input": {"kind": "moved"}},
                ],
            }
        )
    )
    saved = answer.save(request, reply, tmp_path / "store", seal=False)
    assert json.loads(saved.read_text())["source"] == Source.Subscription
    replay = Replay(Mode.Only, tmp_path / "store", seal=False)
    words, turn = call(replay, Unpaid())
    assert words == ["When did he leave?"]
    assert turn.calls == [ToolCall("t1", "add_event", {"kind": "moved"})]
    assert turn.spent == Spent()
    assert replay.subscribed


def test_a_subscription_replay_sends_none_of_the_apps_cache_marks(tmp_path):
    # R-0568
    chat = marked_ends(
        [
            {"role": "user", "content": "My brother moved away last spring."},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "When did he leave?"},
                    {"type": "tool_use", "id": "t1", "name": "add_event", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
            },
            {"role": "user", "content": [{"type": "text", "text": "In April."}]},
        ],
        [2, 3],
    )
    assert "cache_control" in json.dumps(chat)
    lines = subscription.transcript(chat, "s1", tmp_path)
    assert "cache_control" not in json.dumps([line["message"] for line in lines])
    assert lines[1]["message"]["content"][1]["name"] == "mcp__coach__add_event"


def aged(path):
    old = time.time() - KEEP.total_seconds() - 60
    os.utime(path, (old, old))


def test_serving_a_reply_refreshes_its_time(tmp_path):
    # R-0799
    call(Replay(Mode.Replay, tmp_path, seal=False), Wire())
    (saved,) = tmp_path.glob("*.json")
    aged(saved)
    call(Replay(Mode.Only, tmp_path, seal=False), Wire())
    assert time.time() - saved.stat().st_mtime < 60


def test_a_reply_unused_past_keep_is_deleted(tmp_path):
    # R-0799
    call(Replay(Mode.Replay, tmp_path, seal=False), Wire())
    (saved,) = tmp_path.glob("*.json")
    fresh = tmp_path / "fresh-0.json"
    fresh.write_text("{}")
    aged(saved)
    Replay(Mode.Replay, tmp_path, seal=False).prune()
    assert list(tmp_path.glob("*.json")) == [fresh]


def test_a_tracked_reply_is_never_deleted(tmp_path, monkeypatch):
    # R-0799
    monkeypatch.setattr(replay, "REPO", tmp_path)
    store = tmp_path / "replays"
    store.mkdir()
    tracked, loose = store / "tracked-0.json", store / "loose-0.json"
    for path in (tracked, loose):
        path.write_text("{}")
        aged(path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "replays/tracked-0.json"], cwd=tmp_path, check=True)
    Replay(Mode.Replay, store, seal=False).prune()
    assert list(store.glob("*.json")) == [tracked]


def test_pruning_an_empty_or_missing_store_works(tmp_path):
    # R-0799
    Replay(Mode.Replay, tmp_path / "missing", seal=False).prune()
    Replay(Mode.Replay, tmp_path, seal=False).prune()
    assert not (tmp_path / "missing").exists()
