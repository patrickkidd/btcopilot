"""Which service answers the app's Claude calls, and how a Bedrock machine names
its models. No network: the SDK clients are built, never called."""

import anthropic
import pytest
from botocore.exceptions import UnauthorizedSSOTokenError

from btcopilot import llmutil, provider
from btcopilot.app import create_app
from btcopilot.coachmodel import CoachModel, model_for
from btcopilot.pricing import price
from btcopilot.provider import Provider
from btcopilot.push import keypair
from btcopilot.tests.test_llmutil import Named

SONNET = "us.anthropic.claude-sonnet-5-5"


@pytest.fixture
def anthropic_machine(monkeypatch):
    monkeypatch.delenv(provider.SETTING, raising=False)
    monkeypatch.delenv(provider.BEDROCK_MACHINE, raising=False)
    monkeypatch.delenv(llmutil.LOCAL_URL, raising=False)
    monkeypatch.delenv(llmutil.LOCAL_MODEL, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    return monkeypatch


@pytest.fixture
def bedrock_machine(anthropic_machine):
    anthropic_machine.setenv(provider.BEDROCK_MACHINE, "1")
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


def test_the_provider_is_anthropic_unless_set_or_the_machine_is_on_bedrock(
    anthropic_machine,
):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    assert provider.provider() is Provider.Anthropic
    assert isinstance(llmutil.anthropic_client(), anthropic.Anthropic)
    anthropic_machine.setenv(provider.SETTING, Provider.Bedrock.value)
    assert provider.provider() is Provider.Bedrock
    anthropic_machine.setenv(provider.SETTING, Provider.Anthropic.value)
    anthropic_machine.setenv(provider.BEDROCK_MACHINE, "1")
    assert provider.provider() is Provider.Bedrock
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


def test_on_bedrock_sonnet_answers_a_call_that_names_gemini(bedrock_machine):
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
    assert llmutil.response_text_sync("prompt") == "words"
    assert asked == [llmutil.GEMINI_STAND_IN] * 2 + [llmutil.RESPONSE_MODEL]


def test_a_bedrock_answer_is_priced_at_anthropics_rates(bedrock_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    assert price("us.anthropic.claude-opus-5-5") == price("claude-opus-5-5")
    assert price("us.anthropic.claude-haiku-4-5-20251001-v1:0") == price(
        "claude-haiku-4-5"
    )
    assert price("global.anthropic.claude-sonnet-5-5") == price("claude-sonnet-5-5")


def test_no_alias_names_gemini_any_more(anthropic_machine):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    assert not [alias for alias in llmutil.MODEL_ALIASES if "gemini" in alias]
    with pytest.raises(KeyError):
        model_for("gemini-flash")
