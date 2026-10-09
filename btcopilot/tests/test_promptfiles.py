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
from mock import patch

from btcopilot import promptdir, prompts
from btcopilot.promptdir import PromptDir, key_present, read, split
from btcopilot.tests.repo import REPO

GOLDENS = os.path.join(os.path.dirname(__file__), "prompt_goldens.json")
# Where the private files sit in this repo, whatever the run was pointed at.
REAL_PRIVATE = REPO / "private" / "prompts"

RECORD = "RECORD-SENTINEL\nsecond line"
INTERACTIONS = "INTERACTIONS-SENTINEL"
COVERAGE = "COVERAGE-SENTINEL"
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
    out["get_agent_prompt/coverage"] = module.get_agent_prompt(
        record=RECORD, coverage=COVERAGE
    )
    out["question_backfill"] = module.question_backfill(
        map=RECORD, transcript=TRANSCRIPT
    )
    out["impression_backfill"] = module.impression_backfill(
        map=RECORD, transcript=TRANSCRIPT
    )
    out["note_register"] = module.note_register()
    out["case_report_rewrite"] = module.case_report_rewrite()
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


def test_the_private_coach_prompt_keeps_every_paragraph_it_had(monkeypatch):
    # R-0392
    goldens = REAL_PRIVATE.parent / "goldens.json"
    if not goldens.exists() or not key_present():
        pytest.skip("the private prompts are not installed, or no key opens them")
    monkeypatch.delenv("FD_PRIVATE_PROMPTS", raising=False)
    module = importlib.reload(prompts)
    try:
        want = json.loads(read(goldens))
        got = rendered(module, want)
        for key in [k for k in want if k.startswith("get_agent_prompt/")]:
            said = [p.strip() for p in want[key].split("\n\n")]
            says = [p.strip() for p in got[key].split("\n\n")]
            assert sorted(says) == sorted(said), key
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


def test_the_impression_backfill_carries_the_session_the_map_and_the_judgement(public):
    # R-0482
    prompt = public.impression_backfill(map=RECORD, transcript=TRANSCRIPT)
    assert TRANSCRIPT in prompt
    assert RECORD in prompt
    assert "`add_impression`" in prompt
    assert "one that treats shifts as a series or a trend" in prompt


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


@pytest.fixture
def loader(monkeypatch):
    """The loader as a session sees it: the open-source prompts allowed, the
    private directory where the repo keeps it, and nothing cached."""
    monkeypatch.setenv(prompts.OPEN, "1")
    monkeypatch.delenv("FD_PRIVATE_PROMPTS", raising=False)
    prompts.files.cache_clear()
    yield prompts.files
    prompts.files.cache_clear()


def test_without_a_key_the_open_prompts_are_used_and_said(
    loader, monkeypatch, tmp_path, capsys
):
    # R-0488
    monkeypatch.delenv("SOPS_AGE_KEY", raising=False)
    monkeypatch.setenv("SOPS_AGE_KEY_FILE", str(tmp_path / "keys.txt"))
    assert loader().dirs == [prompts.PUBLIC]
    assert capsys.readouterr().err == promptdir.missing() + "\n"
    assert str(tmp_path / "keys.txt") in promptdir.missing()


def test_a_key_in_the_environment_alone_is_left_for_sops_to_read(
    monkeypatch, tmp_path
):
    # R-0488
    """A cloud session holds the key in SOPS_AGE_KEY and has no key file; naming
    the missing file would make sops fail."""
    monkeypatch.setenv("SOPS_AGE_KEY", "AGE-SECRET-KEY-FOR-TESTS")
    monkeypatch.delenv("SOPS_AGE_KEY_FILE", raising=False)
    monkeypatch.setattr(promptdir, "KEYFILE", tmp_path / "keys.txt")

    def sent_env() -> dict:
        with patch.object(promptdir.subprocess, "run") as run:
            run.return_value.stdout = "plain"
            assert promptdir.decrypt(tmp_path / "a.prompty") == "plain"
        return run.call_args.kwargs["env"]

    env = sent_env()
    assert "SOPS_AGE_KEY_FILE" not in env
    assert env["SOPS_AGE_KEY"] == "AGE-SECRET-KEY-FOR-TESTS"

    (tmp_path / "keys.txt").write_text("AGE-SECRET-KEY-FOR-TESTS\n")
    assert sent_env()["SOPS_AGE_KEY_FILE"] == str(tmp_path / "keys.txt")


def test_with_the_key_the_private_prompts_are_used(loader, capsys):
    # R-0454
    if promptdir.missing():
        pytest.skip(promptdir.missing())
    files = loader()
    assert files.dirs == [REAL_PRIVATE, prompts.PUBLIC]
    assert files.head("scribe")["name"] == "scribe"
    assert capsys.readouterr().err == ""


def test_the_sandbox_will_not_start_on_the_open_prompts_unasked(tmp_path):
    # R-0488
    env = dict(
        os.environ,
        SANDBOX_HOME=str(tmp_path),
        SOPS_AGE_KEY_FILE=str(tmp_path / "keys.txt"),
        SANDBOX_PYTHON=sys.executable,
    )
    env.pop("SOPS_AGE_KEY", None)
    done = subprocess.run(
        [REPO / "bin" / "sandbox" / "sandbox", "up", "keyless", "8916"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert done.returncode != 0
    assert f"no sops key in {tmp_path / 'keys.txt'}" in done.stderr
    assert "--open-prompts" in done.stderr


def test_the_coach_keeps_a_fact_told_unasked_as_a_question_already_answered(public):
    # R-0760
    prompt = " ".join(public.get_agent_prompt(record=RECORD, coverage=COVERAGE).split())
    assert "**Facts told before you ask.**" in prompt
    assert (
        "keep it at once as a fact question already closed: add_question with state "
        "resolved, outcome answered"
    ) in prompt
    assert '"We can\'t have children" closes the couple\'s children item as answered' in prompt


def test_the_coach_asks_the_times_the_most_was_going_on_on_a_thread_that_never_asked(public):
    # R-0762
    prompt = " ".join(public.get_agent_prompt(record=RECORD, coverage=COVERAGE).split())
    assert (
        "Where what brings them and when it began are already in the record from an "
        "earlier sitting, and this question is not yet among the questions kept, the "
        "reply you are writing now asks it, before any other question, whatever the "
        "person has just said."
    ) in prompt


def test_the_coach_keeps_a_story_left_untold_and_asks_a_waiting_question_first(public):
    # R-0770, R-0771
    prompt = public.get_agent_prompt(record=RECORD)
    assert "keep the story in that same turn as a question `held` for later" in prompt
    assert "a waiting question comes before any new question about the basic data" in prompt
    assert "never with a second `add_question`" in prompt

def test_the_coach_asks_one_item_and_the_question_names_it(public):
    # R-0006, R-0771
    prompt = public.get_agent_prompt(record=RECORD, coverage=COVERAGE)
    assert (
        "Only when no question is waiting, ask one item from this list this turn."
    ) in prompt
    fact = public.tool_meanings()[public.ToolText.Fact]
    assert "Name it whenever the question asks for one of the required facts." in fact
    assert "A question that asks for two items is kept as two questions." in fact
