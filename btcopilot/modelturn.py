"""What one model call returns, whichever company's model made it."""

from dataclasses import dataclass, field

from btcopilot.llmutil import Billed, Served, Spent

# Thinking counts toward the cap even though its text is not returned.
MAX_TOKENS = 16000


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class ModelTurn:
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)
    spent: Spent = field(default_factory=Spent)
    served: Served | None = None


class Refusal(Billed):
    """Every model in the fallback chain declined the call on safety grounds.
    The turn fails with the category it named rather than ending in silence.
    The refusal was still paid for."""

    def __init__(self, message: str, category: str | None, served: Served, spent: Spent):
        super().__init__(message, served, spent)
        self.category = category
