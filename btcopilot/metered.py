import time
from decimal import Decimal

from sqlalchemy.orm import Session

from btcopilot.extensions import db
from btcopilot.llmutil import (
    Served,
    Spent,
    gemini_structured_sync,
    gemini_text_sync,
    response_text_sync,
)
from btcopilot.models.modelcall import ModelCall, Purpose
from btcopilot.pricing import cost, heard


class Metered:
    """The model with every call's tokens summed, so one turn charges one meter
    row, and each call written down with its cost. With no model, only plain
    text calls are made, on the response model, and structured calls, on the
    extraction model. A call about no record, such as ratifying a cut or
    judging a thread, has no diagram."""

    def __init__(
        self,
        user_id: int,
        diagram_id: int | None,
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

    def structured(self, prompt: str, response_format):
        started = time.monotonic()
        parsed = gemini_structured_sync(prompt, response_format)
        self._write(parsed.served, parsed.spent, started, 0)
        return parsed.value

    def gemini(self, **kwargs) -> str:
        started = time.monotonic()
        said = gemini_text_sync(**kwargs)
        self._write(said.served, said.spent, started, 0)
        return said.words

    def transcribed(self, model: str, seconds: float):
        """A transcription, billed by the length of the audio, not by tokens."""
        self._row(Served(model), Spent(), heard(model, seconds), 0, 0)

    def _write(self, served: Served, spent: Spent, started: float, tool_calls: int):
        self.spent.add(spent)
        self._row(
            served,
            spent,
            cost(served.model, spent),
            round((time.monotonic() - started) * 1000),
            tool_calls,
        )

    def _row(
        self,
        served: Served,
        spent: Spent,
        cost_usd: Decimal,
        duration_ms: int,
        tool_calls: int,
    ):
        # Its own transaction: the money is spent whether or not the turn
        # that made the call goes on to fail and roll back.
        with Session(db.engine) as ledger, ledger.begin():
            ledger.add(
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
                    cost_usd=cost_usd,
                    duration_ms=duration_ms,
                    tool_calls=tool_calls,
                )
            )
