"""Every prompt is a file now. These say the files render the same text the
Python constants produced, that a private file wins over a public one, and that
a fragment that is missing raises rather than rendering empty."""

import importlib
import json
import os
import shutil

import pytest
from jinja2 import TemplateNotFound

from btcopilot.personal import prompts
from btcopilot.personal.promptdir import PromptDir, read, split

GOLDENS = os.path.join(os.path.dirname(__file__), "prompt_goldens.json")
PRIVATE_GOLDENS = os.path.join(prompts.PRIVATE.parent, "goldens.json")

RECORD = "RECORD-SENTINEL\nsecond line"
INTERACTIONS = "INTERACTIONS-SENTINEL"
STATE = "STATE-SENTINEL"


def rendered(module) -> dict:
    """What every prompt says right now, under the same inputs the goldens were
    captured with."""
    out = {
        name: getattr(module, name)
        for name in dir(module)
        if name.isupper() and isinstance(getattr(module, name), str)
    }
    out["get_agent_prompt/empty"] = module.get_agent_prompt()
    out["get_agent_prompt/record"] = module.get_agent_prompt(record=RECORD)
    out["get_agent_prompt/both"] = module.get_agent_prompt(
        record=RECORD, interactions=INTERACTIONS
    )
    out["note_register"] = module.note_register()
    out["scribe_prompt/empty"] = module.scribe_prompt()
    out["scribe_prompt/record"] = module.scribe_prompt(record=RECORD)
    out["get_conversation_flow_prompt/claude"] = module.get_conversation_flow_prompt(
        model="claude-opus-4-6", committed_state=STATE
    )
    out["get_conversation_flow_prompt/claude_empty"] = (
        module.get_conversation_flow_prompt(model="claude-opus-4-6")
    )
    out["get_conversation_flow_prompt/gemini"] = module.get_conversation_flow_prompt(
        model="gemini-2.5-flash", committed_state=STATE
    )
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
    with open(GOLDENS) as f:
        compare(json.load(f), rendered(public))


@pytest.mark.skipif(
    not os.path.exists(PRIVATE_GOLDENS), reason="the private prompts are not installed"
)
def test_the_private_prompts_say_what_their_constants_said():
    compare(json.loads(read(prompts.PRIVATE.parent / "goldens.json")), rendered(prompts))


def test_the_app_runs_whole_with_no_private_prompts(public):
    assert public.get_agent_prompt(record="Marcus, 40")
    assert public.scribe_prompt(record="Marcus, 40")
    assert set(public.tool_meanings()) == set(public.ToolText)


def test_a_prompt_renders_the_fragments_it_includes(tmp_path):
    (tmp_path / "fragments").mkdir()
    (tmp_path / "fragments" / "one.md").write_text("FIRST")
    (tmp_path / "fragments" / "two.md").write_text("SECOND")
    (tmp_path / "joined.prompty").write_text(
        '---\nname: joined\ndescription: two fragments\n---\n'
        '{% include "fragments/one.md" %} and {% include "fragments/two.md" %}'
    )
    assert PromptDir([tmp_path]).text("joined") == "FIRST and SECOND"


def test_a_missing_fragment_raises_rather_than_rendering_empty(tmp_path):
    (tmp_path / "lonely.prompty").write_text(
        '---\nname: lonely\ndescription: nothing to include\n---\n'
        '{% include "fragments/gone.md" %}'
    )
    with pytest.raises(TemplateNotFound):
        PromptDir([tmp_path]).text("lonely")


def test_a_private_file_wins_over_the_public_one_of_the_same_name(tmp_path):
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
    if shutil.which("sops") is None or not prompts.PRIVATE.is_dir():
        pytest.skip("sops or the private prompts are not installed")
    head, body = split(read(prompts.PRIVATE / "scribe.prompty"))
    assert head["name"] == "scribe"
    assert "{{ committed_state }}" in body
