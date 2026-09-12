"""btcopilot's tool schemas say the shape of a value; what a field means to a
clinician comes from the private prompts fdserver loads over them (R-0305)."""

import importlib
import os

import pytest

from btcopilot.personal import prompts, toolbox

PRIVATE = '''
from btcopilot.personal.prompts import ToolText


def tool_meanings() -> dict:
    return {member: f"private {member.value}" for member in ToolText}
'''


def _event_properties() -> dict:
    for schema in toolbox.schemas():
        if schema["name"] == toolbox.ToolName.EditEvent.value:
            return schema["input_schema"]["properties"]
    raise AssertionError("no edit_event schema")


@pytest.fixture
def private(tmp_path):
    path = tmp_path / "private_prompts.py"
    path.write_text(PRIVATE)
    before = os.environ.get("FDSERVER_PROMPTS_PATH")
    os.environ["FDSERVER_PROMPTS_PATH"] = str(path)
    importlib.reload(prompts)
    yield
    if before is None:
        del os.environ["FDSERVER_PROMPTS_PATH"]
    else:
        os.environ["FDSERVER_PROMPTS_PATH"] = before
    importlib.reload(prompts)


def test_every_tool_parameter_has_a_default_meaning():
    means = prompts.tool_meanings()
    assert set(means) == set(prompts.ToolText)


def test_the_default_schemas_say_nothing_clinical():
    properties = _event_properties()
    said = " ".join(
        str(properties[member.value]["description"]) for member in prompts.ToolText
    ).lower()
    for word in ("projection", "overfunctioning", "cutoff", "fusion", "triangle"):
        assert word not in said


def test_the_private_module_replaces_the_tool_meanings(private):
    properties = _event_properties()
    assert properties["relationship"]["description"] == "private relationship"
    assert properties["anxiety"]["description"] == "private anxiety"


def test_the_scribe_reads_the_same_meanings(private):
    from btcopilot.review import adapter

    written = {schema["name"]: schema for schema in adapter.write_tools()}
    properties = written[toolbox.ToolName.EditEvent.value]["input_schema"]["properties"]
    assert properties["relationship"]["description"] == "private relationship"
