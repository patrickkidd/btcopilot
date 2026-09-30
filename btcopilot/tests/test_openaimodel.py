"""The coach on GPT-6.1 Sol: a whole tool-using turn, the chat and the
reasoning sent back the way the Responses API requires, the price and a
refusal. No network."""

import json
from decimal import Decimal

import pytest
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseReasoningItem,
    ResponseTextDeltaEvent,
    ResponseUsage,
)
from openai.types.responses.response import IncompleteDetails
from openai.types.responses.response_usage import (
    InputTokensDetails,
    OutputTokensDetails,
)

from btcopilot import llmutil
from btcopilot.coachmodel import CoachModel, model_for
from btcopilot.coachturn import CoachTurn, drain
from btcopilot.llmutil import openai_spent
from btcopilot.modelturn import Refusal, Spent
from btcopilot.models import ModelCall, Purpose
from btcopilot.openaimodel import OpenAIModel, functions
from btcopilot.pricing import cost
from btcopilot.tests.conftest import wrote
from btcopilot.tests.test_llmutil import anthropic_env  # noqa: F401
from btcopilot.toolbox import ToolName

SOL = "gpt-6.1-sol"


def usage(prompt=1000, cached=0, written=0, out=100, reasoning=0):
    return ResponseUsage.model_construct(
        input_tokens=prompt,
        input_tokens_details=InputTokensDetails.model_construct(
            cached_tokens=cached, cache_write_tokens=written
        ),
        output_tokens=out,
        output_tokens_details=OutputTokensDetails.model_construct(
            reasoning_tokens=reasoning
        ),
        total_tokens=prompt + out,
    )


def said(text):
    return ResponseOutputMessage.model_construct(
        id="msg_1",
        type="message",
        role="assistant",
        status="completed",
        content=[ResponseOutputText.model_construct(type="output_text", text=text)],
    )


def done(*output, used=None, incomplete=None):
    return ResponseCompletedEvent.model_construct(
        type="response.completed",
        sequence_number=9,
        response=Response.model_construct(
            model=SOL,
            output=list(output),
            usage=used or usage(),
            incomplete_details=incomplete,
        ),
    )


def delta(text):
    return ResponseTextDeltaEvent.model_construct(
        type="response.output_text.delta", delta=text
    )


class Client:
    """OpenAI, answering each call with the next scripted stream."""

    def __init__(self, *streams):
        self.streams = list(streams)
        self.sent = []
        self.responses = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def create(self, **kwargs):
        self.sent.append(kwargs)
        return iter(self.streams.pop(0))


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
    )


@pytest.fixture
def sol(monkeypatch):
    client = Client(
        [
            done(
                ResponseReasoningItem.model_construct(
                    id="rs_1", type="reasoning", summary=[], encrypted_content="sealed"
                ),
                ResponseFunctionToolCall.model_construct(
                    type="function_call",
                    call_id="call_1",
                    name=ToolName.EditPerson.value,
                    arguments=json.dumps({"name": "Nell"}),
                ),
                used=usage(prompt=1200, written=1024, out=100, reasoning=80),
            )
        ],
        [
            delta("I put Nell "),
            delta("down."),
            done(said("I put Nell down."), used=usage(prompt=1300, cached=1024, out=10)),
        ],
    )
    monkeypatch.setattr("btcopilot.openaimodel.openai_client", lambda timeout: client)
    return client


def test_a_whole_tool_using_turn_runs_on_gpt(discussion, sol):
    # R-0598
    reply = CoachTurn(
        discussion,
        "My sister is Nell.",
        purpose=Purpose.Coach,
        model=OpenAIModel(SOL, "low"),
    ).run()
    assert reply["statement"] == "I put Nell down."

    people = discussion.diagram.get_diagram_data().people
    assert "Nell" in [person["name"] for person in people]

    calls = ModelCall.query.filter_by(
        diagram_id=discussion.diagram_id, purpose=Purpose.Coach
    ).all()
    assert [call.model for call in calls] == [SOL, SOL]
    assert (calls[0].input_tokens, calls[0].cache_creation_tokens) == (176, 1024)
    assert (calls[1].input_tokens, calls[1].cache_read_tokens) == (276, 1024)
    assert calls[0].output_tokens == 100
    assert calls[0].cost_usd > 0

    first = sol.sent[0]
    assert first["reasoning"] == {"effort": "low"}
    assert first["store"] is False
    offered = {tool["name"]: tool for tool in first["tools"]}
    assert offered[ToolName.EditPerson.value]["type"] == "function"


def test_the_second_call_sends_back_the_reasoning_the_call_and_its_answer(
    discussion, sol
):
    # R-0598
    CoachTurn(
        discussion,
        "My sister is Nell.",
        purpose=Purpose.Coach,
        model=OpenAIModel(SOL),
    ).run()

    items = sol.sent[1]["input"]
    kinds = [item.get("type") for item in items]
    at = kinds.index("reasoning")
    reasoning, asked, answered = items[at : at + 3]
    assert reasoning["encrypted_content"] == "sealed"
    assert asked["type"] == "function_call"
    assert asked["call_id"] == "call_1"
    assert json.loads(asked["arguments"]) == {"name": "Nell"}
    assert answered["type"] == "function_call_output"
    assert answered["call_id"] == "call_1"
    assert "output" in json.loads(answered["output"])
    assert "reasoning" not in sol.sent[1]


def test_the_tool_schemas_go_over_unchanged():
    # R-0598
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    sent = functions([{"name": "edit", "description": "Edit.", "input_schema": schema}])
    assert sent == [
        {
            "type": "function",
            "name": "edit",
            "description": "Edit.",
            "parameters": schema,
            "strict": False,
        }
    ]


def test_the_alias_resolves_and_prices(anthropic_env):  # noqa: F811
    # R-0598
    model = model_for("gpt")
    assert isinstance(model, OpenAIModel)
    assert model.model == SOL
    used = openai_spent(usage(prompt=1000, cached=400, written=100, out=100))
    assert vars(used) == vars(
        Spent(input=500, output=100, cache_creation=100, cache_read=400)
    )
    assert cost(SOL, used) == Decimal("0.00229")


def test_a_local_url_runs_the_gpt_alias_on_the_local_model(anthropic_env):  # noqa: F811
    # R-0598
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    anthropic_env.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    model = model_for("gpt")
    assert isinstance(model, CoachModel)
    assert model.model == "qwen3:8b"


def test_a_content_filter_stop_raises_refusal(monkeypatch):
    # R-0598
    client = Client([done(incomplete=IncompleteDetails(reason="content_filter"))])
    monkeypatch.setattr("btcopilot.openaimodel.openai_client", lambda timeout: client)
    with pytest.raises(Refusal) as refused:
        drain(OpenAIModel(SOL).turn("system", [{"role": "user", "content": "hi"}], []))
    assert refused.value.category == "content_filter"
