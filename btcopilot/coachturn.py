"""One agent loop per user message. No modes, no staging [Oracle: R-0086].

The coach gets the record, the recent chat, what the user has been looking at,
and the tools. It talks and calls tools until it stops; every edit is already
in the record by the time the reply lands.

The turn returns the coach's words plus the typed events behind them, so the
page can move the picture with the same reply it types out.
"""

import datetime
import logging
import time
import uuid
from typing import Callable

from opentelemetry import trace

from btcopilot.extensions import ai_log, db
from btcopilot import chips, clusters, profile, recordtext, turnstore
from btcopilot.pricing import cost
from btcopilot.coachmodel import CoachModel, Spent
from btcopilot.models import (
    Change,
    Discussion,
    DiscussionKind,
    ModelCall,
    Statement,
    StatementKind,
    TokenMeter,
)
from btcopilot.prompts import agent_prompt, note_register, onboarding
from btcopilot.interactions import recent
from btcopilot.toolbox import READS, ToolError, Toolbox, schemas
from btcopilot.toolnames import toolcall
from btcopilot.turnlog import TurnEventKind
from btcopilot.schema import DiagramData, ItemKind

_log = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

MAX_STEPS = 20
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


# Where the sentences the regrouping wrote are put for the coach to read: after
# the tool answer of the step that moved an event, so the system prompt stays
# the same for every call in the turn and the wire keeps it. The
# coach_story_shape fragment in its system prompt says what to do with them.
STORY = "**What changed in the story since last time**\n\n{sentences}"


# What a past turn's read answers are replaced with in the history: the record
# may have moved since, and the map and the read tools are how the coach sees it.
NOT_KEPT = "What this read returned is not kept. Read again if you need it."


NARRATE = (
    "That reply is a list of chips, not something you said. Write it again as "
    "sentences: name the people, say what happened in order and what it meant, "
    "and put each chip inside a sentence that is already talking about that "
    "event. Keep the same ids and the same events."
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


def drain(words):
    """The model's turn, once every piece of its words has gone by."""
    while True:
        try:
            next(words)
        except StopIteration as stop:
            return stop.value


def run_call(toolbox: Toolbox, call) -> tuple[str, dict | None, str | None]:
    """What the model reads, what the page sees, and why the record refused
    the call in plain words, or None."""
    try:
        text, event = toolbox.call(call.name, call.args)
    except ToolError as e:
        _log.warning(f"Tool {call.name} refused: {e}")
        return f"That did not work: {e}", None, e.plain
    return text, event, None


def _again(model, system, messages: list[dict], spoken: str, ask: str, turn_id: str):
    """Ask once for the reply again. The words are the coach's own, so nothing
    here rewrites them — it asks the coach to."""
    asked = messages + [
        {"role": "assistant", "content": spoken},
        {"role": "user", "content": ask},
    ]
    return drain(model.turn(system, asked, [], turn_id)).text


def shorten_labels(
    model, system, messages: list[dict], spoken: str, data, turn_id=""
) -> str:
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
        turn_id,
    )
    still = chips.too_long(shortened, data)
    if still:
        raise LabelTooLong(f"Chip labels still too long after asking again: {still}")
    return shortened


def narrate(model, system, messages: list[dict], spoken: str, turn_id="") -> str:
    """Ask once for sentences when the reply is a bare run of chips."""
    if not chips.bare_list(spoken):
        return spoken
    _log.warning("Reply is a bare list of chips, asking again")
    told = _again(model, system, messages, spoken, NARRATE, turn_id)
    if chips.bare_list(told):
        raise BareList("Reply is still a bare list of chips after asking again")
    return told


def record_of(discussion: Discussion) -> DiagramData:
    """The record a session is about; a session with no record has an empty
    one, which is what a first message lands in."""
    return (
        discussion.diagram.get_diagram_data() if discussion.diagram else DiagramData()
    )


class Metered:
    """The model with every call's tokens summed, so one turn charges one meter
    row, and each call written down with its cost."""

    def __init__(self, model, user_id: int, diagram_id: int, turn_id: str):
        self.model = model
        self.user_id = user_id
        self.diagram_id = diagram_id
        self.turn_id = turn_id
        self.spent = Spent()

    def turn(self, system, messages: list[dict], tools: list[dict], turn_id: str = ""):
        started = time.monotonic()
        turn = yield from self.model.turn(system, messages, tools, turn_id)
        self.spent.add(turn.spent)
        db.session.add(
            ModelCall(
                user_id=self.user_id,
                diagram_id=self.diagram_id,
                turn_id=self.turn_id,
                model=turn.served.model,
                fallback=turn.served.fallback,
                input_tokens=turn.spent.input,
                output_tokens=turn.spent.output,
                cache_creation_tokens=turn.spent.cache_creation,
                cache_read_tokens=turn.spent.cache_read,
                cost_usd=cost(turn.served.model, turn.spent),
                duration_ms=round((time.monotonic() - started) * 1000),
                tool_calls=len(turn.calls),
            )
        )
        return turn


class CoachTurn:
    """One user message in, one coach statement and its edits out."""

    def __init__(
        self,
        discussion: Discussion,
        statement: str,
        *,
        model: CoachModel | None = None,
        session_id: str | None = None,
        statement_id: int | None = None,
        sink: Callable[[dict], None] | None = None,
        turn_id: str | None = None,
        resume: bool = False,
    ):
        self.discussion = discussion
        self.statement = statement
        # The route stores the user's words before the turn is handed to the
        # worker, so the turn is told which statement it is answering.
        self.statement_id = statement_id
        self.resume = resume
        self.sink = sink
        # Everything the database keeps of this turn once it ends: what the page
        # was told, less the words, plus each round of tool calls as sent.
        self.kept: list[dict] = []
        self.streamed = ""
        self.session_id = session_id or str(discussion.id)
        self.turn_id = turn_id or uuid.uuid4().hex
        self.diagram = discussion.diagram
        self.model = Metered(
            model or CoachModel(), discussion.user_id, self.diagram.id, self.turn_id
        )
        self.toolbox = Toolbox(
            self.diagram.id,
            self.turn_id,
            user_id=discussion.user_id,
            session_id=self.session_id,
        )

    @property
    def data(self) -> DiagramData:
        return record_of(self.discussion)

    def run(self) -> dict:
        """The coach's reply, its views, and the events behind it."""
        with _tracer.start_as_current_span(
            "coach.run",
            attributes={
                "user.email": self.discussion.user.username,
                "user.id": self.discussion.user_id,
                "turn_id": self.turn_id,
                "discussion_id": self.discussion.id,
            },
        ):
            return self._run()

    def _run(self) -> dict:
        ai_log.info(f"User statement: {self.statement}")
        data = self.data
        if self.statement_id is None:
            user_statement = Statement(
                discussion_id=self.discussion.id,
                text=chips.validate(self.statement, data),
                speaker=self.discussion.chat_user_speaker,
                order=self.discussion.next_order(),
                kind=StatementKind.Turn,
                turn_id=self.turn_id,
            )
            # Flushed, not committed: a turn that fails before the coach answers
            # leaves no words behind, so a retry does not store them twice.
            db.session.add(user_statement)
            db.session.flush()

        # The coaching text is the same every turn and the rest is not, so they
        # go over the wire apart: the first is kept there, the second re-read.
        # In a note the clinician is writing, not the person whose entry it is.
        note = DiscussionKind(self.discussion.kind) is DiscussionKind.Note
        own = profile.own(data)
        fixed, tail = agent_prompt(
            record=recordtext.outline(
                data, self.diagram.version, None if note or not own else own["id"]
            ),
            interactions=recordtext.interactions(
                recent(self.diagram.id, RECENT_INTERACTIONS)
            ),
            today=datetime.date.today().isoformat(),
        )
        if note:
            tail = f"{tail}\n\n{note_register()}"
        gaps = profile.missing(data)
        if gaps:
            tail = f"{tail}\n\n{onboarding(gaps, own['id'] if own else 1)}"
        system = [fixed, tail]
        messages = self._history()
        if self.resume:
            messages += self._picked_up()
        spoken = ""
        events = []

        for step in range(MAX_STEPS):
            turn = self._say(system, messages, schemas(), stream=True)
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
                asked = toolcall(self.toolbox.data, call.name, call.args)
                text, event, refusal = run_call(self.toolbox, call)
                asked["refusal"] = refusal
                self._note(events, asked)
                # Kept after the page was told, so only the database holds what
                # it answered; a read's answer is too long to keep and goes stale.
                if call.name not in READS:
                    asked["result"] = text
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": text,
                        "is_error": refusal is not None,
                    }
                )
                if event:
                    kind = (
                        TurnEventKind.View
                        if "view" in event
                        else TurnEventKind.RecordPatch
                    )
                    self._note(events, dict(event, type=kind.value))
            sentences = self._regroup(events)
            if sentences:
                last = results[-1]
                said = STORY.format(sentences="\n".join(sentences))
                last["content"] = f"{last['content']}\n\n{said}"
            messages.append({"role": "assistant", "content": turn.blocks})
            messages.append({"role": "user", "content": results})
            self.kept.append(
                {
                    "type": TurnEventKind.Step.value,
                    "blocks": turn.blocks,
                    "results": results,
                }
            )
        else:
            _log.warning(
                f"Turn {self.turn_id} hit the step cap: {MAX_STEPS} steps used, "
                f"last tool {turn.calls[-1].name}"
            )
            messages.append({"role": "user", "content": FINISH})
            spoken = self._say(system, messages, [], stream=True).text

        if not spoken.strip():
            raise EmptyReply(f"Turn {self.turn_id} produced no words for the user")
        spoken = shorten_labels(
            self.model, system, messages, spoken, self.data, self.turn_id
        )
        spoken = narrate(self.model, system, messages, spoken, self.turn_id)

        reply = chips.validate(spoken.strip(), self.data)
        # What was typed out live is the words as the model first said them. A
        # retry for shorter labels or for sentences replaces them, so the page
        # is told to drop what it has and take these instead.
        if reply != self.streamed:
            self._send({"type": TurnEventKind.TextReset.value})
            self._send({"type": TurnEventKind.Text.value, "text": reply})
        ai_log.info(f"AI response: {reply}")
        coach_statement = Statement(
            discussion_id=self.discussion.id,
            text=reply,
            speaker=self.discussion.chat_ai_speaker,
            order=self.discussion.next_order(),
            views=self.toolbox.views or None,
            kind=StatementKind.Turn,
            turn_id=self.turn_id,
        )
        db.session.add(coach_statement)
        db.session.flush()
        Change.query.filter_by(diagram_id=self.diagram.id, turn_id=self.turn_id).update(
            {"statement_id": coach_statement.id}
        )
        if self.discussion.title is None:
            self.discussion.update_title()
            self.discussion.update_summary()
        profile.mirror(self.discussion.user, self.data)
        TokenMeter.charge(self.discussion.user_id, self.model.spent)
        db.session.commit()

        return {
            "statement": reply,
            "statement_id": coach_statement.id,
            "views": self.toolbox.views,
            "events": events,
            "turn_id": self.turn_id,
        }

    def _regroup(self, events: list[dict]) -> list[str]:
        """Re-group the line when the turn has moved an event, before the coach
        speaks, so the grouping it points at is stored. Returns the sentences
        saying what changed, for the coach to read in the tool answer."""
        if not any(
            delta["item_kind"] == ItemKind.Event.value for delta in self.toolbox.deltas
        ):
            return []
        # A grouping that fails its checks twice keeps the groups already there
        # rather than kill the turn [Oracle: R-0410, R-0371].
        try:
            regrouped = clusters.sync(
                self.diagram.id,
                turn_id=self.turn_id,
                user_id=self.discussion.user_id,
                session_id=self.session_id,
            )
        except clusters.ClusterError as rejected:
            _log.warning(
                f"Turn {self.turn_id} kept its clusters: regrouping rejected: {rejected}"
            )
            return []
        if not regrouped:
            return []
        self._note(
            events,
            {
                "type": TurnEventKind.RecordPatch.value,
                "deltas": regrouped.change.deltas,
                "turn_id": regrouped.change.turn_id,
            },
        )
        if regrouped.sentences:
            self._note(
                events,
                {
                    "type": TurnEventKind.Story.value,
                    "sentences": regrouped.sentences,
                },
            )
        return regrouped.sentences

    def _send(self, event: dict) -> None:
        """Tell whoever is watching, as it happens."""
        if event["type"] == TurnEventKind.Text.value:
            self.streamed += event["text"]
        elif event["type"] == TurnEventKind.TextReset.value:
            self.streamed = ""
        if self.sink:
            self.sink(event)

    def _note(self, events: list[dict], event: dict) -> None:
        """What the turn returns at the end and what it says as it goes are the
        same events, in the same order. The record's own edits are kept in the
        change log, so they are not kept twice."""
        events.append(event)
        if event["type"] != TurnEventKind.RecordPatch.value:
            self.kept.append(event)
        self._send(event)

    def _picked_up(self) -> list[dict]:
        """A failed turn going on from where it stopped: the page is told again
        what was already done, and the model gets its own rounds of tool calls
        back, so it finishes the turn rather than starting it over."""
        messages = []
        for event in turnstore.kept({self.turn_id}).get(self.turn_id, []):
            if event["type"] == TurnEventKind.ToolCall.value:
                self._send(event)
            elif event["type"] == TurnEventKind.Step.value:
                messages.append({"role": "assistant", "content": event["blocks"]})
                messages.append({"role": "user", "content": event["results"]})
        return messages

    def _say(self, system, messages: list[dict], tools: list[dict], stream=False):
        """One model call. The words go out as they arrive; a step that ends in
        a tool call was the coach thinking aloud, so those words are dropped."""
        words = self.model.turn(system, messages, tools, self.turn_id)
        sent = False
        while True:
            try:
                piece = next(words)
                if stream:
                    self._send({"type": TurnEventKind.Text.value, "text": piece})
                    sent = True
            except StopIteration as stop:
                if sent and stop.value.calls:
                    self._send({"type": TurnEventKind.TextReset.value})
                return stop.value

    def _history(self) -> list[dict]:
        """The chat so far, with the new message and what its chips point at.
        Each past coach reply comes with the tool calls its turn made, so the
        coach knows what it has already done to the record."""
        prior = sorted(
            [s for s in self.discussion.statements if s.text],
            key=lambda s: (s.order or 0, s.id or 0),
        )[:-1]
        did = turnstore.kept(
            {
                s.turn_id
                for s in prior
                if s.turn_id and s.speaker_id == self.discussion.chat_ai_speaker_id
            }
        )
        messages = []
        for s in prior:
            coach = s.speaker_id == self.discussion.chat_ai_speaker_id
            if coach:
                _say(messages, *_calls(s.turn_id, did.get(s.turn_id, [])))
            _say(messages, ("assistant" if coach else "user", s.text))
        if messages and messages[0]["role"] == "assistant":
            messages.insert(0, {"role": "user", "content": "Hello"})

        spoken = self.statement
        pointed = chips.context(self.statement, self.data)
        if pointed:
            spoken = f"{spoken}\n\n{pointed}"
        _say(messages, ("user", spoken))
        return messages


def _calls(turn_id: str, events: list[dict]) -> list[tuple[str, list[dict]]]:
    """A past turn's tool calls as the model made them, and what each answered."""
    asked = [e for e in events if e["type"] == TurnEventKind.ToolCall.value]
    if not asked:
        return []
    ids = [f"past_{turn_id}_{i}" for i in range(len(asked))]
    return [
        (
            "assistant",
            [
                {"type": "tool_use", "id": id, "name": e["name"], "input": e["args"]}
                for id, e in zip(ids, asked)
            ],
        ),
        (
            "user",
            [
                {
                    "type": "tool_result",
                    "tool_use_id": id,
                    "content": e.get("result") or NOT_KEPT,
                    "is_error": bool(e.get("refusal")),
                }
                for id, e in zip(ids, asked)
            ],
        ),
    ]


def _say(messages: list[dict], *said: tuple[str, str | list[dict]]) -> None:
    """Add to the chat, running two in a row from one side into one message."""
    for role, content in said:
        if not messages or messages[-1]["role"] != role:
            messages.append({"role": role, "content": content})
        elif isinstance(content, str) and isinstance(messages[-1]["content"], str):
            messages[-1]["content"] += "\n\n" + content
        else:
            messages[-1]["content"] = _blocks(messages[-1]["content"]) + _blocks(
                content
            )


def _blocks(content: str | list[dict]) -> list[dict]:
    return [{"type": "text", "text": content}] if isinstance(content, str) else content
