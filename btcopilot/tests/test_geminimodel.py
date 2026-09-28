"""The coach on Gemini Flash: a whole tool-using turn, the chat sent back the
way Gemini requires, the price, the endpoint and a refusal. No network."""

import base64
from decimal import Decimal

import pytest
from google.genai import types

from btcopilot import llmutil
from btcopilot.coachmodel import CoachModel, model_for
from btcopilot.coachturn import CoachTurn, drain
from btcopilot.geminimodel import UNSIGNED, GeminiModel, contents, spent
from btcopilot.modelturn import Refusal, Spent
from btcopilot.models import ModelCall
from btcopilot.pricing import cost
from btcopilot.tests.test_llmutil import anthropic_env  # noqa: F401
from btcopilot.toolbox import ToolName

FLASH = "gemini-3.8-flash"
SIGNATURE = b"opaque-signature"


def usage(prompt=1000, cached=0, out=100, thought=0):
    return types.GenerateContentResponseUsageMetadata(
        prompt_token_count=prompt,
        cached_content_token_count=cached,
        candidates_token_count=out,
        thoughts_token_count=thought,
    )


def chunk(*parts, finish=None, used=None):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=list(parts)),
                finish_reason=finish,
            )
        ],
        usage_metadata=used,
        model_version=FLASH,
    )


class Client:
    """Gemini, answering each call with the next scripted stream."""

    def __init__(self, *streams):
        self.streams = list(streams)
        self.sent = []
        self.models = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def generate_content_stream(self, model, contents, config):
        self.sent.append({"model": model, "contents": contents, "config": config})
        return iter(self.streams.pop(0))


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )


@pytest.fixture
def gemini(monkeypatch):
    client = Client(
        [
            chunk(
                types.Part(
                    function_call=types.FunctionCall(
                        name=ToolName.EditPerson.value, args={"name": "Nell"}
                    ),
                    thought_signature=SIGNATURE,
                ),
                finish=types.FinishReason.STOP,
                used=usage(prompt=1200, cached=0, out=20, thought=80),
            )
        ],
        [
            chunk(types.Part(text="I put Nell ")),
            chunk(
                types.Part(text="down."),
                finish=types.FinishReason.STOP,
                used=usage(prompt=1300, cached=1000, out=10),
            ),
        ],
    )
    monkeypatch.setattr("btcopilot.geminimodel.gemini_client", lambda timeout: client)
    return client


def test_a_whole_tool_using_turn_runs_on_gemini(discussion, gemini):
    # R-0597
    reply = CoachTurn(
        discussion, "My sister is Nell.", model=GeminiModel(FLASH, "medium")
    ).run()
    assert reply["statement"] == "I put Nell down."

    people = discussion.diagram.get_diagram_data().people
    assert "Nell" in [person["name"] for person in people]

    calls = ModelCall.query.filter_by(diagram_id=discussion.diagram_id).all()
    assert [call.model for call in calls] == [FLASH, FLASH]
    assert (calls[0].input_tokens, calls[0].output_tokens) == (1200, 100)
    assert (calls[1].input_tokens, calls[1].cache_read_tokens) == (300, 1000)
    assert calls[0].cost_usd > 0

    offered = gemini.sent[0]["config"].tools[0].function_declarations
    assert ToolName.EditPerson.value in [tool.name for tool in offered]


def test_the_second_call_sends_back_the_call_its_signature_and_its_answer(
    discussion, gemini
):
    # R-0597
    CoachTurn(discussion, "My sister is Nell.", model=GeminiModel(FLASH)).run()

    asked, answered = gemini.sent[1]["contents"][-2:]
    assert asked.role == "model"
    assert asked.parts[0].function_call.name == ToolName.EditPerson.value
    assert asked.parts[0].thought_signature == SIGNATURE
    assert answered.role == "user"
    response = answered.parts[0].function_response
    assert response.name == ToolName.EditPerson.value
    assert "output" in response.response


def test_a_call_gemini_did_not_make_carries_the_stand_in_signature():
    # R-0597
    sent = contents(
        [
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "a", "name": "read_people", "input": {}},
                    {"type": "tool_use", "id": "b", "name": "read_events", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "b",
                        "content": "none",
                        "is_error": True,
                    },
                ],
            },
        ]
    )
    first, second = sent[1].parts
    assert first.thought_signature == UNSIGNED
    assert second.thought_signature is None
    assert sent[2].parts[0].function_response.name == "read_events"
    assert sent[2].parts[0].function_response.response == {"error": "none"}


def test_a_signature_survives_the_record_as_text():
    # R-0597
    encoded = base64.b64encode(SIGNATURE).decode()
    sent = contents(
        [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "a",
                        "name": "read_people",
                        "input": {},
                        "signature": encoded,
                    }
                ],
            }
        ]
    )
    assert sent[0].parts[0].thought_signature == SIGNATURE


def test_the_price_computes_from_gemini_usage():
    # R-0597
    used = spent(usage(prompt=1000, cached=400, out=100, thought=50))
    assert used == Spent(input=600, output=150, cache_creation=0, cache_read=400)
    assert cost(FLASH, used) == Decimal("0.0010425")


def test_a_safety_finish_raises_refusal(monkeypatch):
    # R-0597
    client = Client([chunk(finish=types.FinishReason.SAFETY, used=usage())])
    monkeypatch.setattr("btcopilot.geminimodel.gemini_client", lambda timeout: client)
    with pytest.raises(Refusal) as refused:
        drain(
            GeminiModel(FLASH).turn("system", [{"role": "user", "content": "hi"}], [])
        )
    assert refused.value.category == "safety"


def test_a_gemini_alias_gets_the_gemini_model(anthropic_env):  # noqa: F811
    # R-0597
    model = model_for("gemini-flash")
    assert isinstance(model, GeminiModel)
    assert model.model == FLASH
    with pytest.raises(KeyError):
        model_for("gemini-flsh")


def test_a_local_url_runs_a_gemini_name_on_the_local_model(anthropic_env):  # noqa: F811
    # R-0597
    anthropic_env.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    anthropic_env.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    model = model_for("gemini-flash")
    assert isinstance(model, CoachModel)
    assert model.model == "qwen3:8b"


@pytest.fixture
def made(monkeypatch):
    kwargs = {}
    monkeypatch.setattr("btcopilot.llmutil.genai.Client", lambda **k: kwargs.update(k))
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "fd-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "gemini-key")
    monkeypatch.delenv(llmutil.GEMINI_ENDPOINT, raising=False)
    return kwargs


def test_gemini_goes_to_vertex_unless_told_otherwise(made):
    # R-0597
    llmutil.gemini_client()
    assert made["vertexai"] is True
    assert made["project"] == "fd-project"
    assert "api_key" not in made


def test_the_developer_endpoint_uses_the_api_key(made, monkeypatch):
    # R-0597
    monkeypatch.setenv(llmutil.GEMINI_ENDPOINT, llmutil.GeminiEndpoint.Developer.value)
    llmutil.gemini_client(30)
    assert made["api_key"] == "gemini-key"
    assert "vertexai" not in made
    assert made["http_options"].timeout == 30_000
