"""Which service answers the app's Claude calls, and how a Bedrock machine names
its models. No network: the SDK clients are built, never called."""

import asyncio
from types import SimpleNamespace

import anthropic
import subprocess
import sys

import pytest

from btcopilot.geminimodel import GeminiModel
from botocore.exceptions import UnauthorizedSSOTokenError

from btcopilot import llmutil, provider
from btcopilot.app import create_app
from btcopilot.coachmodel import CoachModel, model_for
from btcopilot.pricing import price
from btcopilot.models import Discussion
from btcopilot.models.modelcall import ModelCall
from btcopilot.provider import Provider
from btcopilot.push import keypair
from btcopilot.tests.test_llmutil import Named

SONNET = "us.anthropic.claude-sonnet-5-5"
HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


@pytest.fixture
def anthropic_machine(monkeypatch):
    monkeypatch.delenv(provider.SETTING, raising=False)
    monkeypatch.delenv(llmutil.LOCAL_URL, raising=False)
    monkeypatch.delenv(llmutil.LOCAL_MODEL, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    return monkeypatch


@pytest.fixture
def bedrock_machine(anthropic_machine):
    anthropic_machine.setenv(provider.SETTING, Provider.Bedrock.value)
    anthropic_machine.setenv(provider.REGION, "us-west-2")
    anthropic_machine.delenv("ANTHROPIC_API_KEY")
    anthropic_machine.delenv("ANTHROPIC_EXTRACTION_API_KEY", raising=False)
    return anthropic_machine


class Session:
    """boto3 on a machine whose sign-in is the one given."""

    def __init__(self, found):
        self.found = found

    def get_credentials(self):
        return self.found


class Expired:
    def get_frozen_credentials(self):
        raise UnauthorizedSSOTokenError()


class Signed:
    def get_frozen_credentials(self):
        return self


def test_the_provider_is_anthropic_unless_the_flag_says_bedrock(anthropic_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    anthropic_machine.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    assert provider.provider() is Provider.Anthropic
    assert isinstance(llmutil.anthropic_client(), anthropic.Anthropic)
    anthropic_machine.setenv(provider.SETTING, "")
    assert provider.provider() is Provider.Anthropic
    anthropic_machine.setenv(provider.SETTING, Provider.Bedrock.value)
    anthropic_machine.setenv(provider.REGION, "us-west-2")
    assert provider.provider() is Provider.Bedrock
    assert isinstance(llmutil.anthropic_client(), anthropic.AnthropicBedrock)
    anthropic_machine.setenv(provider.SETTING, "bedrok")
    with pytest.raises(ValueError):
        provider.provider()


def test_a_bedrock_machine_builds_bedrock_clients_and_reads_no_key(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    client = llmutil.anthropic_client(timeout=30)
    assert isinstance(client, anthropic.AnthropicBedrock)
    assert client.aws_region == "us-west-2"
    assert isinstance(llmutil._anthropic_client(), anthropic.AsyncAnthropicBedrock)
    assert isinstance(
        llmutil._extraction_anthropic_client(), anthropic.AsyncAnthropicBedrock
    )


def test_bedrock_without_a_region_fails_plainly(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    bedrock_machine.delenv(provider.REGION)
    with pytest.raises(RuntimeError, match=provider.REGION):
        llmutil.anthropic_client()


def test_every_model_the_app_names_has_a_bedrock_profile(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    provider.require_bedrock_ids(llmutil.bedrock_models())
    assert llmutil.wire_model(llmutil.resolve_model("sonnet")) == SONNET
    assert CoachModel(model="sonnet").model == SONNET
    assert CoachModel().model == "us.anthropic.claude-opus-5-5"
    assert model_for("haiku-4.5").model == (
        "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )


def test_a_model_without_a_bedrock_profile_is_named(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    with pytest.raises(RuntimeError, match="claude-opus-4-7"):
        provider.require_bedrock_ids([*llmutil.bedrock_models(), "claude-opus-4-7"])
    with pytest.raises(RuntimeError, match="claude-opus-4-7"):
        llmutil.wire_model("claude-opus-4-7")


def test_bedrock_takes_no_fallbacks(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    assert llmutil.fallback_args("claude-opus-5-5") == {}
    assert llmutil.fallback_args(llmutil.wire_model("claude-opus-5-5")) == {}


def test_the_local_server_comes_before_bedrock(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    bedrock_machine.setenv(llmutil.LOCAL_URL, "http://127.0.0.1:11434")
    bedrock_machine.setenv(llmutil.LOCAL_MODEL, "qwen3:8b")
    assert isinstance(llmutil.anthropic_client(), anthropic.Anthropic)
    assert CoachModel().model == "qwen3:8b"
    llmutil.check_provider()


def test_bedrock_with_no_aws_sign_in_stops_the_app_at_startup(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    bedrock_machine.setattr(provider.boto3, "Session", lambda **k: Session(None))
    with pytest.raises(RuntimeError, match=provider.SIGN_IN):
        provider.credentials()
    public, private = keypair()
    with pytest.raises(RuntimeError, match=provider.SIGN_IN):
        create_app(
            config={
                "CONFIG": "testing",
                "TESTING": True,
                "SECRET_KEY": "test_secret_key",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "VAPID_PUBLIC_KEY": public,
                "VAPID_PRIVATE_KEY": private,
                "VAPID_SUBJECT": "mailto:test@example.com",
            }
        )


def test_an_expired_aws_sign_in_stops_the_app_plainly(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    bedrock_machine.setattr(provider.boto3, "Session", lambda **k: Session(Expired()))
    with pytest.raises(RuntimeError, match=provider.SIGN_IN):
        llmutil.check_provider()
    bedrock_machine.setattr(provider.boto3, "Session", lambda **k: Session(Signed()))
    llmutil.check_provider()


def test_on_bedrock_haiku_answers_a_call_that_names_gemini(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    asked = []

    async def claude_structured(prompt, response_format, model):
        asked.append(model)

    async def claude_text(prompt=None, **kwargs):
        asked.append(kwargs["model"])
        return "words"

    bedrock_machine.setattr(llmutil, "claude_structured", claude_structured)
    bedrock_machine.setattr(llmutil, "claude_text", claude_text)
    llmutil.gemini_structured_sync("prompt", Named)
    assert llmutil.gemini_text_sync("prompt", model="gemini-2.5-flash") == "words"
    assert llmutil.gemini_calibration_sync("prompt") == "words"
    assert llmutil.response_text_sync("prompt") == "words"
    assert llmutil.GEMINI_STAND_IN == "claude-haiku-4-5-20251001"
    assert llmutil.wire_model(llmutil.GEMINI_STAND_IN) == HAIKU
    assert asked == [llmutil.GEMINI_STAND_IN] * 3 + [llmutil.RESPONSE_MODEL]


class Gemini:
    """A Gemini client that records the model each call names."""

    def __init__(self, asked):
        self.aio = self
        self.models = self
        self.asked = asked

    async def generate_content(self, model, **kwargs):
        self.asked.append(model)
        raise RuntimeError("asked")


def test_without_the_flag_gemini_calls_go_to_gemini(anthropic_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    asked = []

    async def claude(*args, **kwargs):
        raise AssertionError("Claude answered a Gemini call")

    anthropic_machine.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    anthropic_machine.setattr(llmutil, "claude_structured", claude)
    anthropic_machine.setattr(llmutil, "claude_text", claude)
    anthropic_machine.setattr(llmutil, "_client", lambda: Gemini(asked))
    for call in (
        lambda: llmutil.gemini_structured_sync("prompt", Named),
        lambda: llmutil.gemini_text_sync("prompt", model="gemini-2.5-flash"),
        lambda: llmutil.gemini_calibration_sync("prompt"),
    ):
        with pytest.raises(RuntimeError, match="asked"):
            call()
    assert asked == [
        llmutil.EXTRACTION_MODEL,
        "gemini-2.5-flash",
        llmutil.CALIBRATION_MODEL,
    ]


def test_a_bedrock_answer_is_priced_at_anthropics_rates(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    assert price("us.anthropic.claude-opus-5-5") == price("claude-opus-5-5")
    assert price("us.anthropic.claude-haiku-4-5-20251001-v1:0") == price(
        "claude-haiku-4-5"
    )
    assert price("global.anthropic.claude-sonnet-5-5") == price("claude-sonnet-5-5")


def test_a_gemini_coach_fails_plainly_on_bedrock(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-09, Gemini coach back on the Anthropic path
    with pytest.raises(ValueError, match="not on Bedrock"):
        model_for("gemini-flash")


def test_a_gemini_coach_is_offered_off_bedrock(anthropic_machine):
    # R-0000 ruling pending: Patrick 2026-10-09, Gemini coach back on the Anthropic path
    assert isinstance(model_for("gemini-pro"), GeminiModel)


class Asked(Exception):
    pass


class Claude:
    """An Anthropic client that records what a call sends, then stops it."""

    def __init__(self, sent):
        self.beta = self
        self.messages = self
        self.sent = sent

    async def create(self, **kwargs):
        self.sent.append(kwargs)
        raise Asked()

    def stream(self, **kwargs):
        self.sent.append(kwargs)
        raise Asked()

    async def close(self):
        pass


@pytest.mark.parametrize(
    "model, reasons",
    [(llmutil.GEMINI_STAND_IN, False), (llmutil.RESPONSE_MODEL, True)],
)
def test_haiku_is_sent_no_thinking_and_no_effort(bedrock_machine, model, reasons):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    sent = []
    bedrock_machine.setattr(llmutil, "_anthropic_client", lambda: Claude(sent))
    bedrock_machine.setattr(
        llmutil, "_extraction_anthropic_client", lambda: Claude(sent)
    )
    with pytest.raises(Asked):
        llmutil.claude_text_sync("prompt", model=model)
    with pytest.raises(Asked):
        asyncio.run(llmutil.claude_structured("prompt", Named, model))
    for call in sent:
        assert ("thinking" in call) is reasons
        assert ("output_config" in call) is reasons


@pytest.mark.parametrize(
    "wire",
    [
        "anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "global.anthropic.claude-haiku-4-5-20251001-v2:0",
        "claude-haiku-4-5-20251001",
    ],
)
def test_a_stored_model_name_is_the_app_name(wire):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    assert provider.app_model(wire) == "claude-haiku-4-5-20251001"
    assert ModelCall(model=wire).model == "claude-haiku-4-5-20251001"


def test_served_reads_a_usage_without_iterations():
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    message = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        content=[SimpleNamespace(type="text", text="words")],
        model="claude-haiku-4-5-20251001",
    )
    answered = llmutil.served(message, "claude_structured")
    assert answered.model == "claude-haiku-4-5-20251001"
    assert answered.hops == []


class Built(Claude):
    """anthropic.Anthropic, recording what it was built with."""

    built = []

    def __init__(self, **kwargs):
        super().__init__([])
        Built.built.append(kwargs)

    def stream(self, **kwargs):
        raise Asked()

    def close(self):
        pass


class Discussed:
    """A meter that sends a Gemini call straight to llmutil."""

    def gemini(self, **kwargs):
        return llmutil.gemini_text_sync(**kwargs)


def test_with_no_flag_the_title_and_summary_call_gemini_flash_lite_unthinking(
    anthropic_machine,
):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    asked = []

    class Recorded(Gemini):
        async def generate_content(self, model, contents, config):
            asked.append((model, config.thinking_config.thinking_budget))
            raise Asked()

    anthropic_machine.setattr(llmutil, "_client", lambda: Recorded([]))
    discussion = Discussion(statements=[])
    with pytest.raises(Asked):
        discussion.update_summary(Discussed())
    with pytest.raises(Asked):
        discussion.update_title(Discussed())
    assert asked == [("gemini-3.1-flash-lite", 0)] * 2


def test_with_no_flag_the_coach_builds_anthropic_with_the_api_key(anthropic_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    Built.built = []
    anthropic_machine.setattr(llmutil.anthropic, "Anthropic", Built)
    with pytest.raises(Asked):
        list(CoachModel().turn("system", [{"role": "user", "content": "hi"}], []))
    assert len(Built.built) == 1
    assert Built.built[0]["api_key"] == "anthropic-key"
    assert "base_url" not in Built.built[0] and "aws_region" not in Built.built[0]


def test_with_no_flag_startup_does_not_touch_aws(anthropic_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    def touched(**kwargs):
        raise AssertionError("startup asked AWS for a sign-in")

    anthropic_machine.setattr(provider.boto3, "Session", touched)
    public, private = keypair()
    create_app(
        config={
            "CONFIG": "testing",
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "VAPID_PUBLIC_KEY": public,
            "VAPID_PRIVATE_KEY": private,
            "VAPID_SUBJECT": "mailto:test@example.com",
        }
    )


NO_BOTO3 = """
import sys
sys.modules["boto3"] = sys.modules["botocore"] = sys.modules["botocore.exceptions"] = None
from btcopilot import llmutil, provider
llmutil.anthropic_client()
llmutil._anthropic_client()
print("built")
"""


def test_the_default_path_runs_without_boto3(anthropic_machine):
    # R-0000 ruling pending: Patrick 2026-10-09, Gemini coach back on the Anthropic path
    done = subprocess.run(
        [sys.executable, "-c", NO_BOTO3], capture_output=True, text=True
    )
    assert done.stdout.strip() == "built", done.stderr


def test_bedrock_without_boto3_fails_plainly(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-09, Gemini coach back on the Anthropic path
    bedrock_machine.setattr(provider, "boto3", None)
    with pytest.raises(RuntimeError, match="uv sync --extra bedrock"):
        provider.credentials()


def test_app_model_keeps_anthropic_and_gemini_names(anthropic_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    for name in (
        "claude-sonnet-5",
        "claude-haiku-4-5-20251001",
        llmutil.EXTRACTION_MODEL,
    ):
        assert provider.app_model(name) == name
