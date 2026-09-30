import time

from btcopilot.extensions import db
from btcopilot.llmutil import Served, Spent, response_text_sync
from btcopilot.models.modelcall import ModelCall, Purpose
from btcopilot.pricing import cost


class Metered:
    """The model with every call's tokens summed, so one turn charges one meter
    row, and each call written down with its cost. With no model, only plain
    text calls are made, on the response model."""

    def __init__(
        self,
        user_id: int,
        diagram_id: int,
        turn_id: str,
        purpose: Purpose,
        model=None,
    ):
        self.model = model
        self.user_id = user_id
        self.diagram_id = diagram_id
        self.turn_id = turn_id
        self.purpose = purpose
        self.spent = Spent()

    def turn(self, system, messages: list[dict], tools: list[dict], turn_id: str = ""):
        started = time.monotonic()
        turn = yield from self.model.turn(system, messages, tools, turn_id)
        self._write(turn.served, turn.spent, started, len(turn.calls))
        return turn

    def text(self, prompt: str) -> str:
        started = time.monotonic()
        said = response_text_sync(prompt)
        self._write(said.served, said.spent, started, 0)
        return said.words

    def _write(self, served: Served, spent: Spent, started: float, tool_calls: int):
        self.spent.add(spent)
        db.session.add(
            ModelCall(
                user_id=self.user_id,
                diagram_id=self.diagram_id,
                turn_id=self.turn_id,
                purpose=self.purpose,
                model=served.model,
                fallback=served.fallback,
                input_tokens=spent.input,
                output_tokens=spent.output,
                cache_creation_tokens=spent.cache_creation,
                cache_read_tokens=spent.cache_read,
                cost_usd=cost(served.model, spent),
                duration_ms=round((time.monotonic() - started) * 1000),
                tool_calls=tool_calls,
            )
        )
