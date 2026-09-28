"""What one model call returns, whichever company's model made it."""

from dataclasses import dataclass, field

from btcopilot.llmutil import Served

# Thinking counts toward the cap even though its text is not returned.
MAX_TOKENS = 16000


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class Spent:
    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0

    def add(self, other: "Spent") -> None:
        self.input += other.input
        self.output += other.output
        self.cache_creation += other.cache_creation
        self.cache_read += other.cache_read


@dataclass
class ModelTurn:
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)
    spent: Spent = field(default_factory=Spent)
    served: Served | None = None


class Refusal(Exception):
    """Every model in the fallback chain declined the call on safety grounds.
    The turn fails with the category it named rather than ending in silence."""

    def __init__(self, message: str, category: str | None):
        super().__init__(message)
        self.category = category
