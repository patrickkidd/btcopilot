import json
import subprocess
from decimal import Decimal

import pytest

from btcopilot import flow
from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import (
    Discussion,
    ModelCall,
    Purpose,
    Speaker,
    SpeakerType,
    Statement,
)


def said(id, spk, text, minute, turn_id, *, uid=1, diagram_id=1, kind="turn", **more):
    return {
        "id": id,
        "did": diagram_id,
        "uid": uid,
        "diagram_id": diagram_id,
        "created_at": f"2026-09-01T10:{minute:02d}:00",
        "spk": spk,
        "text": text,
        "turn_id": turn_id,
        "kind": kind,
        "ord": id,
        **more,
    }


def export(folder, stmts=None):
    folder.mkdir()
    stmts = stmts or [
        said(1, "Subject", "My aunt Rosa moved to Leeds in 1984.", 0, "t1"),
        said(
            2,
            "Expert",
            "How did you feel about that?",
            1,
            "t1",
            model="opus",
            prompt_version="p1",
        ),
        said(3, "Subject", "I'll call my aunt Rosa on Sunday to ask her.", 2, "t2"),
        said(
            4,
            "Expert",
            "When did Rosa leave Leeds?",
            3,
            "t2",
            model="opus",
            prompt_version="p2",
        ),
    ]
    changes = [
        {
            "id": 1,
            "diagram_id": 1,
            "turn_id": "t1",
            "created_at": "2026-09-01T10:01:00",
            "deltas": [
                {
                    "item_id": 5,
                    "item_kind": "person",
                    "field": None,
                    "before": None,
                    "after": {"id": 5, "name": "Rosa"},
                },
                {
                    "item_id": 7,
                    "item_kind": "event",
                    "field": "location",
                    "before": None,
                    "after": "Leeds",
                },
                {
                    "item_id": 7,
                    "item_kind": "event",
                    "field": "dateTime",
                    "before": None,
                    "after": "1984-01-01",
                },
            ],
        },
        {
            "id": 2,
            "diagram_id": 1,
            "turn_id": "t2",
            "created_at": "2026-09-01T10:03:00",
            "deltas": [
                {
                    "item_id": 9,
                    "item_kind": "question",
                    "field": None,
                    "before": None,
                    "after": {"id": 9, "kind": "todo"},
                },
            ],
        },
    ]
    (folder / "stmts.json").write_text(json.dumps(stmts))
    (folder / "changes.json").write_text(json.dumps(changes))
    return folder


def track(flask_app, *args):
    return flask_app.test_cli_runner().invoke(admin, ["flow", "track", *map(str, args)])


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_counts_per_model_and_prompt_and_no_text(flask_app, tmp_path):
    # R-0669
    result = track(
        flask_app, "--export", export(tmp_path / "x"), "--out", tmp_path / "out"
    )
    assert result.exit_code == 0, result.output
    threads = {
        (r["model"], r["prompt_version"]): r
        for r in lines(tmp_path / "out/threads.jsonl")
    }
    assert set(threads) == {("opus", "p1"), ("opus", "p2")}
    assert (
        threads["opus", "p1"]["feeling_questions"],
        threads["opus", "p2"]["specifics"],
    ) == (1, 1)
    assert {r["rules_version"] for r in threads.values()} == {flow.RULES_VERSION}
    assert threads["opus", "p2"]["own_steps_stored"] == 1
    written = (tmp_path / "out/threads.jsonl").read_text() + (
        tmp_path / "out/accounts.jsonl"
    ).read_text()
    assert "Rosa" not in written and "Leeds" not in written


def test_leaves_out_plays_test_accounts_and_scratch(flask_app, tmp_path):
    # R-0669
    stmts = [
        said(1, "Subject", "My father left in 1990.", 0, "t1"),
        said(
            2, "Expert", "Where did he go?", 1, "t1", model="opus", prompt_version="p1"
        ),
        said(
            3,
            "Expert",
            "Here is the play.",
            2,
            "t2",
            kind="play",
            model="opus",
            prompt_version="p1",
        ),
        said(
            4,
            "Subject",
            "Testing.",
            0,
            "t3",
            uid=2,
            diagram_id=2,
            username="claude-test@x.invalid",
        ),
        said(
            5,
            "Expert",
            "Why?",
            1,
            "t3",
            uid=2,
            diagram_id=2,
            username="claude-test@x.invalid",
        ),
        said(6, "Subject", "A copy.", 0, "t4", uid=3, diagram_id=3, scratch=True),
        said(7, "Expert", "Why?", 1, "t4", uid=3, diagram_id=3, scratch=True),
    ]
    result = track(
        flask_app, "--export", export(tmp_path / "x", stmts), "--out", tmp_path / "out"
    )
    assert result.exit_code == 0, result.output
    threads = lines(tmp_path / "out/threads.jsonl")
    assert [(r["thread"], r["coach_messages"]) for r in threads] == [(1, 1)]
    assert [r["account"] for r in lines(tmp_path / "out/accounts.jsonl")] == [1]


def test_written_keys_are_kept_unless_again(flask_app, tmp_path):
    # R-0669
    folder, out = export(tmp_path / "x"), tmp_path / "out"
    track(flask_app, "--export", folder, "--out", out)
    path = out / "threads.jsonl"
    path.write_text(
        path.read_text().replace('"coach_messages": 1', '"coach_messages": 99')
    )
    result = track(flask_app, "--export", folder, "--out", out)
    assert "threads: 0 written, 2 already there" in result.output
    assert 99 in [r["coach_messages"] for r in lines(path)]

    result = track(flask_app, "--export", folder, "--out", out, "--again")
    assert "threads: 2 written, 0 already there" in result.output
    assert 99 not in [r["coach_messages"] for r in lines(path)]


def test_refuses_a_folder_inside_a_git_work_tree(flask_app, tmp_path):
    # R-0669
    subprocess.run(["git", "init", "-q", str(tmp_path / "repo")], check=True)
    result = track(
        flask_app,
        "--export",
        export(tmp_path / "x"),
        "--out",
        tmp_path / "repo/tracked",
    )
    assert result.exit_code != 0
    assert "inside a git work tree" in result.output
    assert not (tmp_path / "repo/tracked").exists()


def test_refuses_production_without_leave(flask_app, tmp_path, monkeypatch):
    # R-0669
    monkeypatch.setitem(flask_app.config, "CONFIG", "production")
    result = track(flask_app, "--database", "--out", tmp_path / "out")
    assert result.exit_code != 0
    assert "--production" in result.output


def test_database_reads_model_and_prompt_version(flask_app, test_user, tmp_path):
    # R-0669
    discussion = Discussion(user_id=test_user.id, diagram_id=test_user.free_diagram_id)
    db.session.add(discussion)
    db.session.flush()
    person = Speaker(
        discussion_id=discussion.id, name="Person", type=SpeakerType.Subject
    )
    coach = Speaker(discussion_id=discussion.id, name="Coach", type=SpeakerType.Expert)
    db.session.add_all([person, coach])
    db.session.flush()
    for order, (speaker, text, turn_id, prompt) in enumerate(
        [
            (person, "My brother moved away in 2001.", "t1", None),
            (coach, "Where did he move to?", "t1", "p9"),
            (person, "To the coast.", "t2", None),
            (coach, "When was that?", "t2", None),
        ]
    ):
        db.session.add(
            Statement(
                discussion_id=discussion.id,
                speaker_id=speaker.id,
                text=text,
                order=order,
                turn_id=turn_id,
                prompt_version=prompt,
            )
        )
    db.session.add(
        ModelCall(
            user_id=test_user.id,
            turn_id="t1",
            purpose=Purpose.Coach,
            model="claude-opus-5-5",
            input_tokens=1,
            output_tokens=1,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            cost_usd=Decimal(0),
            duration_ms=1,
            tool_calls=0,
        )
    )
    db.session.commit()
    result = track(flask_app, "--database", "--out", tmp_path / "out")
    assert result.exit_code == 0, result.output
    keys = {
        (r["model"], r["prompt_version"]) for r in lines(tmp_path / "out/threads.jsonl")
    }
    assert keys == {("claude-opus-5-5", "p9"), ("unknown", "unknown")}
