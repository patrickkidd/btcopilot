"""Every prompt is a file now. These say the files render the same text the
Python constants produced, that a private file wins over a public one, and that
a fragment that is missing raises rather than rendering empty."""

import importlib
import json
import os
import subprocess
import sys

import pytest
from jinja2 import TemplateNotFound

from btcopilot import prompts
from btcopilot.promptdir import PromptDir, key_present, read, split
from btcopilot.tests.repo import REPO

GOLDENS = os.path.join(os.path.dirname(__file__), "prompt_goldens.json")
# Where the private files sit in this repo, whatever the run was pointed at.
REAL_PRIVATE = REPO / "private" / "prompts"

RECORD = "RECORD-SENTINEL\nsecond line"
INTERACTIONS = "INTERACTIONS-SENTINEL"
TRANSCRIPT = "TRANSCRIPT-SENTINEL\n41 coach: Who were your father's brothers and sisters?"


def rendered(module, names) -> dict:
    """What every prompt says right now, under the same inputs the goldens were
    captured with. `names` is asked for by name because the fixed prompts are
    read on first use, so they are not in `dir()` until something asks."""
    out = {name: getattr(module, name) for name in names if name.isupper()}
    out["get_agent_prompt/empty"] = module.get_agent_prompt()
    out["get_agent_prompt/record"] = module.get_agent_prompt(record=RECORD)
    out["get_agent_prompt/both"] = module.get_agent_prompt(
        record=RECORD, interactions=INTERACTIONS
    )
    out["question_backfill"] = module.question_backfill(
        map=RECORD, transcript=TRANSCRIPT
    )
    out["note_register"] = module.note_register()
    out["scribe_prompt/empty"] = module.scribe_prompt()
    out["scribe_prompt/record"] = module.scribe_prompt(record=RECORD)
    out["tool_meanings"] = {str(k): v for k, v in module.tool_meanings().items()}
    out["generic_name"] = module.generic_name("Marcus", module.Role.Father)
    return out


@pytest.fixture
def public(monkeypatch):
    """The app with no private prompt directory at all."""
    monkeypatch.setenv("FD_PRIVATE_PROMPTS", "/nonexistent")
    module = importlib.reload(prompts)
    yield module
    monkeypatch.undo()
    importlib.reload(prompts)


def compare(want: dict, got: dict):
    missing = sorted(set(want) - set(got))
    assert not missing, f"prompts that no longer exist: {missing}"
    for key in sorted(want):
        assert got[key] == want[key], key


def test_the_open_source_prompts_say_what_their_constants_said(public):
    # R-0048
    with open(GOLDENS) as f:
        want = json.load(f)
    compare(want, rendered(public, want))


def test_the_private_prompts_say_what_their_constants_said(monkeypatch):
    # R-0048
    goldens = REAL_PRIVATE.parent / "goldens.json"
    if not goldens.exists() or not key_present():
        pytest.skip("the private prompts are not installed, or no key opens them")
    monkeypatch.delenv("FD_PRIVATE_PROMPTS", raising=False)
    module = importlib.reload(prompts)
    try:
        want = json.loads(read(goldens))
        compare(want, rendered(module, want))
    finally:
        monkeypatch.undo()
        importlib.reload(prompts)


def test_the_app_runs_whole_with_no_private_prompts(public):
    # R-0451
    assert public.get_agent_prompt(record="Marcus, 40")
    assert public.scribe_prompt(record="Marcus, 40")
    assert set(public.tool_meanings()) == set(public.ToolText)


def test_the_backfill_prompt_carries_the_session_the_map_and_the_judgement(public):
    # R-0482
    prompt = public.question_backfill(map=RECORD, transcript=TRANSCRIPT)
    assert TRANSCRIPT in prompt
    assert RECORD in prompt
    assert "people usually require questions to stimulate their thinking" in prompt
    assert "`asked_in`" in prompt
    assert "does the map or the rest of the session already answer it" in prompt
    assert "does an open question or one you have just added ask nearly the same thing" in prompt
    assert "write it so it reads alone, naming the person and the subject" in prompt
    assert 'it speaks to the person as "you"' in prompt
    assert "leave out any lead-in, hedge or reason" in prompt


def test_the_scribe_gives_every_date_its_certainty(public):
    # R-0482
    prompt = " ".join(public.scribe_prompt().split())
    assert "Whenever you add an event or change its date, always give its date_certainty" in prompt
    assert "certain when the coder gave the exact day" in prompt
    assert "approximate when they gave only the month" in prompt


def test_a_prompt_renders_the_fragments_it_includes(tmp_path):
    # R-0454
    (tmp_path / "fragments").mkdir()
    (tmp_path / "fragments" / "one.md").write_text("FIRST")
    (tmp_path / "fragments" / "two.md").write_text("SECOND")
    (tmp_path / "joined.prompty").write_text(
        '---\nname: joined\ndescription: two fragments\n---\n'
        '{% include "fragments/one.md" %} and {% include "fragments/two.md" %}'
    )
    assert PromptDir([tmp_path]).text("joined") == "FIRST and SECOND"


def test_a_missing_fragment_raises_rather_than_rendering_empty(tmp_path):
    # R-0453
    (tmp_path / "lonely.prompty").write_text(
        '---\nname: lonely\ndescription: nothing to include\n---\n'
        '{% include "fragments/gone.md" %}'
    )
    with pytest.raises(TemplateNotFound):
        PromptDir([tmp_path]).text("lonely")


def test_a_private_file_wins_over_the_public_one_of_the_same_name(tmp_path):
    # R-0305
    pub, priv = tmp_path / "pub", tmp_path / "priv"
    (pub / "fragments").mkdir(parents=True)
    priv.mkdir()
    (pub / "fragments" / "shared.md").write_text("PUBLIC FRAGMENT")
    (pub / "a.prompty").write_text("---\nname: a\ndescription: x\n---\nPUBLIC A")
    (pub / "b.prompty").write_text(
        '---\nname: b\ndescription: x\n---\n{% include "fragments/shared.md" %}'
    )
    (priv / "a.prompty").write_text("---\nname: a\ndescription: x\n---\nPRIVATE A")
    files = PromptDir([priv, pub])
    assert files.text("a") == "PRIVATE A"
    assert files.text("b") == "PUBLIC FRAGMENT"


def test_an_encrypted_prompt_reads_as_its_plain_text():
    # R-0322
    if not key_present() or not REAL_PRIVATE.is_dir():
        pytest.skip("the private prompts are not installed, or no key opens them")
    head, body = split(read(REAL_PRIVATE / "scribe.prompty"))
    assert head["name"] == "scribe"
    assert "{{ committed_state }}" in body


def test_importing_the_app_decrypts_nothing(tmp_path):
    # R-0451
    """A prompt is read when it is called for, never when a module loads, or a
    test run and the migration chain would need a key before they could start."""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "sops").write_text("#!/bin/sh\nexit 99\n")
    (fake / "sops").chmod(0o755)
    env = dict(os.environ, PATH=f"{fake}:{os.environ['PATH']}")
    env.pop("FD_PRIVATE_PROMPTS", None)
    env["PYTHONPATH"] = str(REPO)
    done = subprocess.run(
        [sys.executable, "-c", "import btcopilot.app, btcopilot.prompts"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert done.returncode == 0, done.stderr[-2000:]


def test_one_coach_prompt_and_no_mode_variants():
    # R-0015
    for d in (prompts.PUBLIC, REAL_PRIVATE):
        names = {p.stem for p in d.glob("*.prompty")}
        assert "agent" in names
        assert [n for n in names if n != "agent" and n.startswith("agent")] == []
        assert [n for n in names if "mode" in n] == []
