"""One agent loop per user message. No modes, no staging [Oracle: R-0086].

The coach gets the record, the recent chat, what the user has been looking at,
and the tools. It talks and calls tools until it stops; every edit is already
in the record by the time the reply lands.

The turn returns the coach's words plus the typed events behind them, so the
page can move the picture with the same reply it types out.
"""

import enum
import logging
import uuid

from btcopilot.extensions import ai_log, db
from btcopilot.personal import chips, clusters, recordtext
from btcopilot.personal.coachmodel import CoachModel
from btcopilot.personal.models import Change, Discussion, Statement, StatementKind
from btcopilot.personal.prompts import get_agent_prompt
from btcopilot.personal.interactions import recent
from btcopilot.personal.toolbox import SCHEMAS, ToolError, Toolbox
from btcopilot.schema import DiagramData, ItemKind

_log = logging.getLogger(__name__)

MAX_STEPS = 6
RECENT_INTERACTIONS = 50

# What the coach is told when it has used every step and is still working. The
# turn has to end in words, so the last call is made with no tools at all.
FINISH = (
    "You have used all the tool calls this turn allows. Stop working and reply "
    "to the person now, in your own voice: what you have put in the record, and "
    "what you want to know next."
)


SHORTEN = (
    "These chip labels are too long for the chip they go on: {labels}. Write "
    "your reply again with every label at most {limit} characters — a noun "
    "phrase, not a clause. Keep the same ids, the same events and the same "
    "words around them; only the labels change."
)


NARRATE = (
    "That reply is a list of chips, not something you said. Write it again as "
    "sentences: name the people, say what happened in order and what it meant, "
    "and put each chip inside a sentence that is already talking about that "
    "moment. Keep the same ids and the same events."
)


class EmptyReply(Exception):
    """The coach finished a turn without saying anything. A statement with no
    words is a bare bubble on the page, so the turn fails instead."""


class LabelTooLong(Exception):
    """A chip label will not fit and the coach would not shorten it. Trimming
    it here would hide a prompt that has stopped holding, and the page has no
    truncation left to cover it."""


class BareList(Exception):
    """The coach answered with a run of chips and would not narrate it when
    asked. A list of chips is not the coach speaking, and there is nothing here
    that can turn one into sentences."""


def _again(model, system: str, messages: list[dict], spoken: str, ask: str) -> str:
    """Ask once for the reply again. The words are the coach's own, so nothing
    here rewrites them — it asks the coach to."""
    asked = messages + [
        {"role": "assistant", "content": spoken},
        {"role": "user", "content": ask},
    ]
    words = model.turn(system, asked, [])
    while True:
        try:
            next(words)
        except StopIteration as stop:
            return stop.value.text


def shorten_labels(model, system: str, messages: list[dict], spoken: str, data) -> str:
    """Ask once for shorter chip labels."""
    over = chips.too_long(spoken, data)
    if not over:
        return spoken
    _log.warning(f"Chip labels too long, asking again: {over}")
    shortened = _again(
        model,
        system,
        messages,
        spoken,
        SHORTEN.format(
            labels="; ".join(repr(label) for label in over), limit=chips.CHIP_MAX
        ),
    )
    still = chips.too_long(shortened, data)
    if still:
        raise LabelTooLong(f"Chip labels still too long after asking again: {still}")
    return shortened


def narrate(model, system: str, messages: list[dict], spoken: str) -> str:
    """Ask once for sentences when the reply is a bare run of chips."""
    if not chips.bare_list(spoken):
        return spoken
    _log.warning("Reply is a bare list of chips, asking again")
    told = _again(model, system, messages, spoken, NARRATE)
    if chips.bare_list(told):
        raise BareList("Reply is still a bare list of chips after asking again")
    return told


class EventKind(enum.StrEnum):
    """What happened behind the words, in the order it happened."""

    ToolCall = "tool_call"
    RecordPatch = "record_patch"
    View = "view"


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

    def run(self) -> dict:
        """The coach's reply, its views, and the events behind it."""
        ai_log.info(f"User statement: {self.statement}")
        data = self.data
        user_statement = Statement(
            discussion_id=self.discussion.id,
            text=chips.validate(self.statement, data),
            speaker=self.discussion.chat_user_speaker,
            order=self.discussion.next_order(),
            kind=StatementKind.Turn,
        )
        # Flushed, not committed: a turn that fails before the coach answers
        # leaves no words behind, so a retry does not store them twice.
        db.session.add(user_statement)
        db.session.flush()

        system = get_agent_prompt(
            record=recordtext.render(data),
            interactions=recordtext.interactions(
                recent(self.diagram.id, RECENT_INTERACTIONS)
            ),
        )
        messages = self._history()
        spoken = ""
        events = []

        for step in range(MAX_STEPS):
            turn = self._say(system, messages, SCHEMAS)
            # A turn ends on words, never on a tool call. Text written before a
            # call is the model working out what to do and the user never sees
            # it, so only a step that calls nothing is the coach speaking.
            spoken = turn.text
            if not turn.calls:
                break
            if turn.text:
                _log.info(f"Turn {self.turn_id} step {step} thought aloud: {turn.text}")

            results = []
            for call in turn.calls:
                events.append(
                    {"type": EventKind.ToolCall.value, "name": call.name, "args": call.args}
                )
                text, event, refused = self._call(call)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": text,
                        "is_error": refused,
                    }
                )
                if event:
                    kind = EventKind.View if "view" in event else EventKind.RecordPatch
                    events.append(dict(event, type=kind.value))
            messages.append({"role": "assistant", "content": turn.blocks})
            messages.append({"role": "user", "content": results})
        else:
            _log.warning(
                f"Turn {self.turn_id} used all {MAX_STEPS} steps; asking for the reply"
            )
            messages.append({"role": "user", "content": FINISH})
            spoken = self._say(system, messages, []).text

        if not spoken.strip():
            raise EmptyReply(f"Turn {self.turn_id} produced no words for the user")
        spoken = shorten_labels(self.model, system, messages, spoken, self.data)
        spoken = narrate(self.model, system, messages, spoken)

        change = self._regroup()
        if change:
            events.append(
                {
                    "type": EventKind.RecordPatch.value,
                    "deltas": change.deltas,
                    "turn_id": change.turn_id,
                }
            )

        reply = chips.validate(spoken.strip(), self.data)
        ai_log.info(f"AI response: {reply}")
        coach_statement = Statement(
            discussion_id=self.discussion.id,
            text=reply,
            speaker=self.discussion.chat_ai_speaker,
            order=self.discussion.next_order(),
            views=self.toolbox.views or None,
            kind=StatementKind.Turn,
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

        return {
            "statement": reply,
            "statement_id": coach_statement.id,
            "views": self.toolbox.views,
            "events": events,
            "turn_id": self.turn_id,
        }

    def _regroup(self):
        """Re-cluster the line when the turn moved an event, so the clusters
        the coach and the picture point at are stored, not derived on read."""
        if not any(
            delta["item_kind"] == ItemKind.Event.value
            for delta in self.toolbox.deltas
        ):
            return None
        return clusters.sync(
            self.diagram.id,
            turn_id=self.turn_id,
            user_id=self.discussion.user_id,
            session_id=self.session_id,
        )

    def _say(self, system: str, messages: list[dict], tools: list[dict]):
        """One model call. The words arrive whole; the page types them out."""
        words = self.model.turn(system, messages, tools)
        while True:
            try:
                next(words)
            except StopIteration as stop:
                return stop.value

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
