import pytest

from btcopilot import llmutil
from btcopilot.schema import EventKind, PDPDeltas
from btcopilot import testing
from btcopilot.testing import llmstub

CONVERSATION = (
    "Zephyrine: My brother Quillon stopped calling after Marisol died.\n"
    "Coach: When did that start?\n"
    "Zephyrine: Around the time Quillon moved away.\n"
)


@pytest.fixture
def stub():
    llmstub.install()
    yield llmstub
    llmstub.uninstall()


def test_off_by_default(monkeypatch):
    monkeypatch.delenv(llmstub.LLM_ENV, raising=False)
    assert not llmstub.stubbed()


def test_an_app_built_without_the_flag_takes_the_stub_back_out(flask_app, monkeypatch):
    monkeypatch.setenv(llmstub.LLM_ENV, "stub")
    testing.init_app(flask_app)
    assert llmutil._client.__module__ == llmstub.__name__

    monkeypatch.delenv(llmstub.LLM_ENV)
    testing.init_app(flask_app)
    assert llmutil._client.__module__ == llmutil.__name__


def test_enabled_by_env(monkeypatch):
    monkeypatch.setenv(llmstub.LLM_ENV, "stub")
    assert llmstub.stubbed()


def test_names_come_from_conversation_lines_only(stub):
    assert stub.new_names(CONVERSATION) == ["Quillon", "Marisol"]


def test_names_already_committed_are_not_restaged(stub):
    prompt = '{\n  "people": [\n    {"name": "Quillon"}\n  ]\n}\n' + CONVERSATION
    assert stub.new_names(prompt) == ["Marisol"]


def test_deltas_are_deterministic(stub):
    first = stub.deltas_for(CONVERSATION)
    assert first == stub.deltas_for(CONVERSATION)
    assert [p["id"] for p in first["people"]] == [-1, -2]
    assert first["events"][0]["person"] == -1
    assert first["events"][0]["kind"] == EventKind.Shift.value


def test_no_people_means_no_event(stub):
    assert stub.deltas_for("Coach: When did that start?\n")["events"] == []


def test_chat_echoes_the_last_user_statement(stub, monkeypatch):
    monkeypatch.setattr(llmutil, "RESPONSE_MODEL", "claude-opus-4-6")
    reply = llmutil.response_text_sync(turns=[("user", "My mother Marisol left.")])
    assert reply == "Tell me more about that. You said: My mother Marisol left."


def test_gemini_chat_echoes_the_last_user_statement(stub):
    reply = llmutil.gemini_text_sync(
        system_instruction="anything", turns=[("user", "My mother Marisol left.")]
    )
    assert reply == "Tell me more about that. You said: My mother Marisol left."


def test_structured_extraction_returns_a_usable_pdp(stub):
    deltas = llmutil.gemini_structured_sync(CONVERSATION, PDPDeltas)
    assert [p.name for p in deltas.people] == ["Quillon", "Marisol"]
    assert deltas.events[0].person == deltas.people[0].id
    assert deltas.events[0].dateTime == llmstub.STUB_EVENT_DATE


async def test_claude_structured_extraction_returns_a_usable_pdp(stub):
    deltas = await llmutil.gemini_structured(
        CONVERSATION, PDPDeltas, model="claude-opus-4-6"
    )
    assert [p.name for p in deltas.people] == ["Quillon", "Marisol"]


def test_uninstall_restores_the_real_factories():
    llmstub.install()
    llmstub.uninstall()
    assert llmutil._client.__module__ == llmutil.__name__
