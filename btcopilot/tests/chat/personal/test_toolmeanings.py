"""btcopilot's tool schemas say the shape of a value; what a field means to a
clinician comes from the private prompt files loaded over them (R-0305)."""

import importlib
import os

import pytest

from btcopilot.personal import prompts, toolbox

def private_meanings() -> str:
    lines = ["---", "name: tool_meanings", "description: private", "meanings:"]
    lines += [f"  {member.value}: private {member.value}" for member in prompts.ToolText]
    return "\n".join(lines + ["---", ""])


def _event_properties() -> dict:
    for schema in toolbox.schemas():
        if schema["name"] == toolbox.ToolName.EditEvent.value:
            return schema["input_schema"]["properties"]
    raise AssertionError("no edit_event schema")


@pytest.fixture
def private(tmp_path):
    (tmp_path / "tool_meanings.prompty").write_text(private_meanings())
    before = os.environ.get("FD_PRIVATE_PROMPTS")
    os.environ["FD_PRIVATE_PROMPTS"] = str(tmp_path)
    importlib.reload(prompts)
    yield
    if before is None:
        del os.environ["FD_PRIVATE_PROMPTS"]
    else:
        os.environ["FD_PRIVATE_PROMPTS"] = before
    importlib.reload(prompts)


def test_every_tool_parameter_has_a_default_meaning():
    # R-0451
    means = prompts.tool_meanings()
    assert set(means) == set(prompts.ToolText)


@pytest.fixture
def public(monkeypatch):
    """The app with no private prompt files, which is what the open-source
    repo ships."""
    monkeypatch.setenv("FD_PRIVATE_PROMPTS", "/nonexistent")
    importlib.reload(prompts)
    yield
    monkeypatch.undo()
    importlib.reload(prompts)


def test_the_default_schemas_say_nothing_clinical(public):
    # R-0305
    overridable = {member.value for member in prompts.ToolText}
    said = " ".join(
        str(field.get("description", ""))
        for schema in toolbox.schemas()
        for name, field in schema["input_schema"].get("properties", {}).items()
        if name in overridable
    ).lower()
    for word in ("projection", "overfunctioning", "cutoff", "fusion", "triangle"):
        assert word not in said


def test_a_private_prompt_file_replaces_the_tool_meanings(private):
    # R-0305
    properties = _event_properties()
    assert properties["relationship"]["description"] == "private relationship"
    assert properties["anxiety"]["description"] == "private anxiety"


def test_the_scribe_reads_the_same_meanings(private):
    # R-0305
    from btcopilot.review import adapter

    written = {schema["name"]: schema for schema in adapter.write_tools()}
    properties = written[toolbox.ToolName.EditEvent.value]["input_schema"]["properties"]
    assert properties["relationship"]["description"] == "private relationship"
