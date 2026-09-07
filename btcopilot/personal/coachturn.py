"""One agent loop per user message. No modes, no staging [Oracle: R-0086].

The coach gets the record, the recent chat, what the user has been looking at,
and the tools. It talks and calls tools until it stops; every edit is already
in the record by the time the reply lands, and every event on the way out is
something the page can act on.
"""

import enum
import logging
import uuid

from btcopilot.extensions import ai_log, db
from btcopilot.personal import chips, recordtext
from btcopilot.personal.coachmodel import CoachModel
from btcopilot.personal.models import Change, Discussion, Statement
from btcopilot.personal.prompts import get_agent_prompt
from btcopilot.personal.routes.interactions import recent
from btcopilot.personal.toolbox import SCHEMAS, ToolError, Toolbox
from btcopilot.schema import DiagramData

_log = logging.getLogger(__name__)

MAX_STEPS = 6
RECENT_INTERACTIONS = 50


class EventKind(enum.StrEnum):
    Text = "text"
    ToolCall = "tool_call"
    RecordPatch = "record_patch"
    View = "view"
    Statement = "statement"


class CoachTurn:
    """One user message in, one coach statement and its edits out."""

    def __init__(
        self,
        discussion: Discussion,
        statement: str,
        *,
        model: CoachModel | None = None,
        session_id: str | None = None,
    ):
        self.discussion = discussion
        self.statement = statement
        self.model = model or CoachModel()
        self.session_id = session_id or str(discussion.id)
        self.turn_id = uuid.uuid4().hex
        self.diagram = discussion.diagram
        self.toolbox = Toolbox(
            self.diagram.id,
            self.turn_id,
            user_id=discussion.user_id,
            session_id=self.session_id,
        )

    @property
    def data(self) -> DiagramData:
        return self.diagram.get_diagram_data() if self.diagram else DiagramData()

    def run(self):
        """Yield (kind, payload) as the turn happens; the last is the statement."""
        ai_log.info(f"User statement: {self.statement}")
        data = self.data
        user_statement = Statement(
            discussion_id=self.discussion.id,
            text=chips.validate(self.statement, data),
            speaker=self.discussion.chat_user_speaker,
            order=self.discussion.next_order(),
        )
        db.session.add(user_statement)
        db.session.commit()

        system = get_agent_prompt(
            record=recordtext.render(data),
            interactions=recordtext.interactions(recent(self.diagram.id, RECENT_INTERACTIONS)),
        )
        messages = self._history()
        said = []

        for step in range(MAX_STEPS):
            words = self.model.turn(system, messages, SCHEMAS)
            while True:
                try:
                    yield EventKind.Text, {"text": next(words)}
                except StopIteration as stop:
                    turn = stop.value
                    break
            if turn.text:
                said.append(turn.text)
            if not turn.calls:
                break

            results = []
            for call in turn.calls:
                yield EventKind.ToolCall, {"name": call.name, "args": call.args}
                text, event, refused = self._call(call)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": text,
                        "is_error": refused,
                    }
                )
                if event and "view" in event:
                    yield EventKind.View, event
                elif event:
                    yield EventKind.RecordPatch, event
            messages.append({"role": "assistant", "content": turn.blocks})
            messages.append({"role": "user", "content": results})
        else:
            _log.warning(f"Turn {self.turn_id} hit {MAX_STEPS} steps without finishing")

        reply = chips.validate("\n\n".join(said).strip(), self.data)
        ai_log.info(f"AI response: {reply}")
        coach_statement = Statement(
            discussion_id=self.discussion.id,
            text=reply,
            speaker=self.discussion.chat_ai_speaker,
            order=self.discussion.next_order(),
            views=self.toolbox.views or None,
        )
        db.session.add(coach_statement)
        db.session.flush()
        Change.query.filter_by(
            diagram_id=self.diagram.id, turn_id=self.turn_id
        ).update({"statement_id": coach_statement.id})
        if self.discussion.title is None:
            self.discussion.update_title()
            self.discussion.update_summary()
        db.session.commit()

        yield EventKind.Statement, {
            "id": coach_statement.id,
            "text": reply,
            "views": self.toolbox.views,
            "turn_id": self.turn_id,
            "discussion_id": self.discussion.id,
        }

    def _call(self, call) -> tuple[str, dict | None, bool]:
        try:
            text, event = self.toolbox.call(call.name, call.args)
        except ToolError as e:
            _log.warning(f"Tool {call.name} refused: {e}")
            return f"That did not work: {e}", None, True
        return text, event, False

    def _history(self) -> list[dict]:
        """The chat so far, with the new message and what its chips point at."""
        messages = []
        prior = sorted(
            [s for s in self.discussion.statements if s.text],
            key=lambda s: (s.order or 0, s.id or 0),
        )[:-1]
        for s in prior:
            role = (
                "assistant"
                if s.speaker_id == self.discussion.chat_ai_speaker_id
                else "user"
            )
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"] += "\n\n" + s.text
            else:
                messages.append({"role": role, "content": s.text})
        if messages and messages[0]["role"] == "assistant":
            messages.insert(0, {"role": "user", "content": "Hello"})

        spoken = self.statement
        pointed = chips.context(self.statement, self.data)
        if pointed:
            spoken = f"{spoken}\n\n{pointed}"
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += "\n\n" + spoken
        else:
            messages.append({"role": "user", "content": spoken})
        return messages
