"""Which service answers the app's Claude calls: Anthropic's API with a key, or
Amazon Bedrock with the machine's AWS sign-in. Production is Anthropic. A
machine signed in to Bedrock, where Anthropic's API is unreachable, is Bedrock
(Patrick, 2026-10-01)."""

import enum
import os
from typing import Iterable

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class Provider(enum.StrEnum):
    Anthropic = "anthropic"
    Bedrock = "bedrock"


SETTING = "BTCOPILOT_MODEL_PROVIDER"
# Claude Code sets this on a machine that reaches Claude through Bedrock.
BEDROCK_MACHINE = "CLAUDE_CODE_USE_BEDROCK"
REGION = "AWS_REGION"
SIGN_IN = "aws sso login"

# The app's model names, as Anthropic's API takes them, to the Bedrock
# inference profiles that serve them in us-west-2 (listed 2026-10-01).
BEDROCK_MODELS = {
    "claude-opus-5-5": "us.anthropic.claude-opus-5-5",
    "claude-opus-5": "us.anthropic.claude-opus-5",
    "claude-opus-4-8": "us.anthropic.claude-opus-4-8",
    "claude-opus-4-6": "us.anthropic.claude-opus-4-6-v1",
    "claude-sonnet-5-5": "us.anthropic.claude-sonnet-5-5",
    "claude-sonnet-5": "us.anthropic.claude-sonnet-5",
    "claude-haiku-4-5-20251001": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
}
BEDROCK_PREFIXES = ("us.anthropic.", "global.anthropic.", "anthropic.")


def provider() -> Provider:
    chosen = Provider(os.environ.get(SETTING, Provider.Anthropic))
    if chosen is Provider.Bedrock or os.environ.get(BEDROCK_MACHINE):
        return Provider.Bedrock
    return Provider.Anthropic


def region() -> str:
    found = os.environ.get(REGION)
    if not found:
        raise RuntimeError(f"Bedrock is the model provider but {REGION} is not set")
    return found


def credentials() -> None:
    """Check AWS credentials for Bedrock; raise with fix instructions if missing."""
    try:
        found = boto3.Session(region_name=region()).get_credentials()
        if found:
            found.get_frozen_credentials()
    except (BotoCoreError, ClientError) as error:
        raise RuntimeError(
            f"Bedrock is the model provider but the AWS sign-in is not usable "
            f"({error}); run {SIGN_IN}"
        ) from error
    if not found:
        raise RuntimeError(
            "Bedrock is the model provider but this machine has no AWS credentials; "
            f"set AWS_PROFILE and run {SIGN_IN}"
        )


def require_bedrock_ids(models: Iterable[str]) -> None:
    missing = sorted(set(models) - set(BEDROCK_MODELS))
    if missing:
        raise RuntimeError(
            f"No Bedrock inference profile for {', '.join(missing)}; "
            "add it to BEDROCK_MODELS in btcopilot/provider.py"
        )


def bedrock_model(model: str) -> str:
    require_bedrock_ids([model])
    return BEDROCK_MODELS[model]


def app_model(wire: str) -> str:
    """The app's name for a model a Bedrock call or answer named."""
    for prefix in BEDROCK_PREFIXES:
        if wire.startswith(prefix):
            return wire[len(prefix) :]
    return wire
