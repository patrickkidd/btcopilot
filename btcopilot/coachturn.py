"""One agent loop per user message. No modes, no staging [Oracle: R-0086].

The coach gets the record, the recent chat, what the user has been looking at,
and the tools. It talks and calls tools until it stops; every edit is already
in the record by the time the reply lands.

The turn returns the coach's words plus the typed events behind them, so the
page can move the picture with the same reply it types out.
"""

import datetime
import hashlib
import itertools
import logging
import uuid
from typing import Callable

import regex
from opentelemetry import trace

from btcopilot.extensions import ai_log, db
from btcopilot import (
    chips,
    clock,
    clusters,
    coverage,
    profile,
    record,
    recordtext,
    turnlog,
    turnstore,
)
from btcopilot.coachmodel import CoachModel, marked_ends
from btcopilot.discussions import SITTING_GAP, previous
from btcopilot.llmutil import UNANSWERED
from btcopilot.metered import Metered
from btcopilot.models import (
    Change,
    Discussion,
    DiscussionKind,
    ProactiveMessage,
    Purpose,
    Statement,
    StatementKind,
    TokenMeter,
    TurnEvent,
)
from btcopilot.prompts import agent_prompt, back, get_agent_prompt, note_register, onboarding
from btcopilot.interactions import recent
from btcopilot.toolbox import (
    LOOKUPS,
    ToolError,
    ToolName,
    Toolbox,
    said_before,
    schemas,
)
from btcopilot.toolnames import toolcall
from btcopilot.turnlog import TurnEventKind
from btcopilot.schema import DiagramData, ItemKind, QuestionState

_log = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

MAX_STEPS = 20
RECENT_INTERACTIONS = 50
# The family's latest words, from every one of the user's sessions on it, that
# the coach reads back each turn; older ones it finds with the chat search.
RECENT_STATEMENTS = 20
RECENT_STEP = 10

# What the coach is told when it has used every step and is still working. The
# turn has to end in words, so the last call is made with no tools at all.
FINISH = (
    "You have used all the tool calls this turn allows. Stop working and reply "
    "to the person now, in your own voice: what you have put in the record, and "
    "what you want to know next."
)


# What the coach is told when it stops after its tool calls without a word to
# the person: it was working, not done, so it is asked once to reply.
SPEAK = (
    "You stopped without saying anything to the person. Reply to them now, in "
    "your own voice."
)


SHORTEN = (
    "These chips have labels too long for the chip they go on: {chips}. Send "
    "back only these chips, one per line, with the same kind and id and a label "
    "of at most {limit} characters — a noun phrase, not a clause. Write nothing "
    "else: the rest of your reply stays as it is."
)


# Where the sentences the regrouping wrote are put for the coach to read: after
# the tool answer of the step that moved an event, so the system prompt stays
# the same for every call in the turn and the wire keeps it. The
# coach_story_shape fragment in its system prompt says what to do with them.
STORY = "**What changed in the story since last time**\n\n{sentences}"

# What a call's event tells the page, by the key it carries; anything else it
# tells is the record changing.
TOLD = {
    "view": TurnEventKind.View,
    "address": TurnEventKind.Navigate,
    "report": TurnEventKind.Report,
}


NARRATE = (
    "That reply is a list of chips, not something you said. Write it again as "
    "sentences: name the people, say what happened in order and what it meant, "
    "and put each chip inside a sentence that is already talking about that "
    "event. Keep the same ids and the same events."
)


class EmptyReply(Exception):
    """The coach finished a turn without saying anything. A statement with no
    words is a bare bubble on the page, so the turn fails instead."""


class Stopped(Exception):
    """The person stopped the turn; it ends at its next model or tool call."""


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
    """Ask the coach once more, with no tools."""
    asked = messages + [
        {"role": "assistant", "content": spoken},
        {"role": "user", "content": ask},
    ]
    return drain(model.turn(system, asked, [], turn_id)).text


def _shown(match) -> str:
    return (match.group(3) or match.group(2)).strip()


def cut(label: str) -> str:
    """The label within the limit, ended at the last whole word that fits, or
    at the limit when no word does."""
    shown = regex.findall(r"\X", label)
    if len(shown) <= chips.CHIP_MAX:
        return label
    head = "".join(shown[: chips.CHIP_MAX])
    if not (head[-1].isspace() or shown[chips.CHIP_MAX].isspace()):
        words = head.rsplit(None, 1)
        head = words[0] if len(words) > 1 else head
    return head.rstrip(" ,;:—–-")


def shorten_labels(
    model, system, messages: list[dict], spoken: str, data, diagram_id: int | None, turn_id=""
) -> str:
    """Ask once for shorter labels for the chips that will not fit, and only
    for those labels: the words and the events around them stay as they are.
    A label still too long after that is cut at a word."""

    def over(match) -> bool:
        kind, target = chips.ChipKind(match.group(1)), match.group(2).strip()
        return (
            chips.resolves(kind, target, data, diagram_id)
            and chips.length(_shown(match)) > chips.CHIP_MAX
        )

    long = [m.group(0) for m in chips.TOKEN.finditer(spoken) if over(m)]
    if not long:
        return spoken
    _log.warning(f"Chip labels too long, asking for new ones: {long}")
    told = _again(
        model,
        system,
        messages,
        spoken,
        SHORTEN.format(chips="; ".join(long), limit=chips.CHIP_MAX),
        turn_id,
    )
    given: dict[tuple[str, str], list[str]] = {}
    for m in chips.TOKEN.finditer(told):
        if (m.group(3) or "").strip():
            given.setdefault((m.group(1), m.group(2).strip()), []).append(
                m.group(3).strip()
            )

    def relabel(match) -> str:
        if not over(match):
            return match.group(0)
        kind, target = match.group(1), match.group(2).strip()
        offered = given.get((kind, target))
        label = offered.pop(0) if offered else _shown(match)
        if chips.length(label) > chips.CHIP_MAX:
            _log.warning(f"Chip label still too long, cut at a word: {label!r}")
            label = cut(label)
        return chips.token(chips.ChipKind(kind), target, label)

    return chips.TOKEN.sub(relabel, spoken)


def narrate(model, system, messages: list[dict], spoken: str, turn_id="") -> str:
    """Ask once for sentences when the reply is a bare run of chips."""
    if not chips.bare_list(spoken):
        return spoken
    _log.warning("Reply is a bare list of chips, asking again")
    told = _again(model, system, messages, spoken, NARRATE, turn_id)
    if chips.bare_list(told):
        raise BareList("Reply is still a bare list of chips after asking again")
    return told


def prompt_version() -> str:
    """The coach's prompt as the replay ledger names it: its text with nothing
    filled in, hashed."""
    return hashlib.sha256(get_agent_prompt().encode()).hexdigest()[:12]


def record_of(discussion: Discussion) -> DiagramData:
    """The record a session is about; a session with no record has an empty
    one, which is what a first message lands in."""
    return (
        discussion.diagram.get_diagram_data() if discussion.diagram else DiagramData()
    )


class CoachTurn:
    """One user message in, one coach statement and its edits out."""

    def __init__(
        self,
        discussion: Discussion,
        statement: str,
        *,
        purpose: Purpose,
        model: CoachModel | None = None,
        statement_id: int | None = None,
        sink: Callable[[dict], None] | None = None,
        turn_id: str | None = None,
        resume: bool = False,
        scratch: bool = False,
        zone: str | None = None,
    ):
        """A scratch turn runs on a copy: it charges no one's monthly cap and
        leaves the user's profile alone."""
        self.discussion = discussion
        self.statement = statement
        # The person's IANA zone, sent by the page with the message: "today"
        # is their day, not the server's. None, as on a resumed turn, is the
        # zone kept on their row, and with none kept, UTC.
        self.zone = zone
        # The route stores the user's words before the turn is handed to the
        # worker, so the turn is told which statement it is answering.
        self.statement_id = statement_id
        self.resume = resume
        self.scratch = scratch
        self.sink = sink
        # Everything the database keeps of this turn once it ends: what the page
        # was told, less the words, plus each round of tool calls as sent.
        self.kept: list[dict] = []
        self.streamed = ""
        self.turn_id = turn_id or uuid.uuid4().hex
        self.diagram = discussion.diagram
        self.model = Metered(
            discussion.user_id,
            self.diagram.id,
            self.turn_id,
            purpose,
            model=model or CoachModel(),
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
            answered = Statement(
                discussion_id=self.discussion.id,
                text=chips.validate(self.statement, data, self.discussion.diagram_id),
                speaker=self.discussion.chat_user_speaker,
                order=self.discussion.next_order(),
                kind=StatementKind.Turn,
                turn_id=self.turn_id,
            )
            # Flushed, not committed: a turn that fails before the coach answers
            # leaves no words behind, so a retry does not store them twice.
            db.session.add(answered)
            db.session.flush()
        else:
            answered = db.session.get(Statement, self.statement_id)
        self.toolbox = Toolbox(
            self.diagram.id,
            self.turn_id,
            user_id=self.discussion.user_id,
            session_id=self.discussion.id,
            said=answered,
            zone=self.zone,
        )

        # The coaching text is the same every turn and the rest is not, so the
        # rest goes after the chat, heading the new message, and the chat before
        # it is read back from the wire instead of written to it again.
        # In a note the clinician is writing, not the person whose entry it is.
        note = DiscussionKind(self.discussion.kind) is DiscussionKind.Note
        own = profile.own(data)
        system, tail = agent_prompt(
            record=recordtext.outline(
                data, self.diagram.version, None if note or not own else own["id"]
            ),
            interactions=recordtext.interactions(
                recent(self.diagram.id, RECENT_INTERACTIONS)
            ),
            today=clock.today(self.toolbox.zone).isoformat(),
            coverage=coverage.block(data, plateau(answered, self.diagram.id)),
        )
        last = last_notes(answered)
        if last:
            notes = recordtext.notes(last.payload["args"], last.created_at)
            tail = f"{tail}\n\n{notes}"
        if note:
            tail = f"{tail}\n\n{note_register()}"
        pairs = recordtext.pairs(
            data,
            chips.plain(self.statement),
            chips.people(self.statement, data, self.discussion.diagram_id),
        )
        if pairs:
            tail = f"{tail}\n\n{pairs}"
        gaps = profile.missing(data)
        if gaps:
            tail = f"{tail}\n\n{onboarding(gaps, own['id'] if own else 1)}"
        gone = None if note else away(answered)
        if gone is not None and gone > SITTING_GAP:
            tail = f"{tail}\n\n{back(max(1, gone.days), todos(data))}"
        messages = self._history(tail, answered)
        if self.resume:
            messages += self._picked_up()
        spoken = ""
        events = []
        silent = False

        for step in range(MAX_STEPS):
            turn = self._say(
                system, messages, schemas(self.toolbox.coder), stream=True
            )
            # A turn ends on words, never on a tool call. Text written before a
            # call is the model working out what to do and the user never sees
            # it, so only a step that calls nothing is the coach speaking.
            spoken = turn.text
            if not turn.calls:
                if spoken.strip() or step == 0 or silent:
                    break
                _log.warning(f"Turn {self.turn_id} step {step} stopped with no words")
                silent = True
                _say(messages, ("user", SPEAK))
                continue
            if turn.text:
                _log.info(f"Turn {self.turn_id} step {step} thought aloud: {turn.text}")

            results = []
            for call in turn.calls:
                self._halt()
                asked = toolcall(self.toolbox.data, call.name, call.args)
                text, event, refusal = run_call(self.toolbox, call)
                asked["refusal"] = refusal
                # a read changes nothing, so which events it read rides on the
                # call itself, for the page to grey them (R-0540)
                if call.name in LOOKUPS and event:
                    asked.update(event)
                self._note(events, asked)
                # Kept after the page was told, so only the database holds what
                # it answered; a read's answer is too long to keep and goes stale.
                if call.name not in LOOKUPS:
                    asked["result"] = text
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": text,
                        "is_error": refusal is not None,
                    }
                )
                if event and call.name not in LOOKUPS:
                    kind = next(
                        (kind for key, kind in TOLD.items() if key in event),
                        TurnEventKind.RecordPatch,
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

        self._halt()
        if not spoken.strip():
            raise EmptyReply(f"Turn {self.turn_id} produced no words for the user")
        spoken = shorten_labels(
            self.model, system, messages, spoken, self.data, self.discussion.diagram_id, self.turn_id
        )
        spoken = narrate(self.model, system, messages, spoken, self.turn_id)
        self._halt()

        reply = chips.validate(spoken.strip(), self.data, self.discussion.diagram_id)
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
            prompt_version=prompt_version(),
        )
        db.session.add(coach_statement)
        db.session.flush()
        Change.query.filter_by(diagram_id=self.diagram.id, turn_id=self.turn_id).update(
            {"statement_id": coach_statement.id}
        )
        if self.discussion.title is None:
            self._title()
        self._halt()
        if not self.scratch:
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

    def _title(self) -> None:
        """Naming the sitting is not the reply: when that call fails the
        sitting stays unnamed and the next turn names it, whether Gemini
        answered with an error, could not be reached or took too long. The
        summary is written first, so a named sitting always has one. A
        sitting is named from its opening words, so the one before it, now
        over, is named once more from all of it; when that call fails its
        title stays."""
        summary = self.model.aside(Purpose.Summary)
        try:
            self.discussion.update_summary(summary)
            self.discussion.update_title(summary)
            before = previous(self.discussion)
            if before:
                before.update_title(summary)
        except UNANSWERED as failed:
            _log.warning(f"Turn {self.turn_id} left a sitting's title as it was: {failed}")

    def _regroup(self, events: list[dict]) -> list[str]:
        """Re-group the line when the turn has moved an event, before the coach
        speaks, so the grouping it points at is stored. Returns the sentences
        saying what changed, for the coach to read in the tool answer."""
        if not any(
            delta["item_kind"] == ItemKind.Event.value for delta in self.toolbox.deltas
        ):
            return []
        # Refused answers are handled inside the regrouping; what reaches here is
        # the record refusing a grouping at the write, which keeps the groups
        # already there rather than kill the turn [Oracle: R-0410, R-0371].
        try:
            regrouped = clusters.sync(
                self.diagram.id,
                turn_id=self.turn_id,
                user_id=self.discussion.user_id,
                session_id=self.discussion.id,
                metered=self.model.aside(Purpose.Cluster),
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

    def _halt(self) -> None:
        if turnlog.halted(self.turn_id):
            raise Stopped(f"turn {self.turn_id} was stopped")

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
        self._halt()
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

    def _history(self, tail: str, answered: Statement) -> list[dict]:
        """The words said before the ones this turn answers, then the record,
        the coach's last notes and the day, then the new message and what its
        chips point at. No past tool call is given back: what the
        coach did is in the record, and the map is how it sees it (R-0481). The
        chat is marked where it stood before this message and before the last
        one: what this turn writes to the wire, the next reads."""
        messages = []
        ends = []
        for s in _recent(answered):
            coach = s.speaker_id == s.discussion.chat_ai_speaker_id
            if not coach:
                ends.append(_settled(messages))
            _say(messages, ("assistant" if coach else "user", s.text))
        if messages and messages[0]["role"] == "assistant":
            messages.insert(0, {"role": "user", "content": "Hello"})
            ends = [end + 1 for end in ends]
        ends.append(_settled(messages))
        messages = marked_ends(messages, ends[-2:])

        spoken = self.statement
        pointed = chips.context(self.statement, self.data, self.discussion.diagram_id)
        if pointed:
            spoken = f"{spoken}\n\n{pointed}"
        _say(messages, ("user", _blocks(tail) + _blocks(spoken)))
        return messages


def away(said: Statement) -> datetime.timedelta | None:
    """How long the family was quiet before these words; a message the coach
    sent unasked is not the family speaking. None for the thread's first
    words (R-0783)."""
    sent = db.session.query(ProactiveMessage.statement_id).filter(
        ProactiveMessage.statement_id.isnot(None)
    )
    last = (
        said_before(said)
        .filter(Statement.id.notin_(sent))
        .order_by(Statement.created_at.desc(), Statement.id.desc())
        .first()
    )
    return None if last is None else said.created_at - last.created_at


def todos(data: DiagramData) -> str:
    """The person's own open todos, oldest first, as the coach reads them."""
    open_ = [
        recordtext.note_line(q)
        for q in sorted(data.questions, key=recordtext.question_order)
        if record.note(q) is record.TODO and q["state"] != QuestionState.Resolved
    ]
    return "; ".join(open_) or "none"


def _recent(said: Statement) -> list[Statement]:
    """The last words before these, oldest first. A shadow turn answers the
    real turn's words, so it reads the same ones. The first word read moves
    on only RECENT_STEP at a time, so between RECENT_STATEMENTS and
    RECENT_STATEMENTS + RECENT_STEP - 1 are read, and the chat before the
    newest turns stays the same, and cached, until the next step."""
    before = said_before(said)
    start = max(0, (before.count() - RECENT_STATEMENTS) // RECENT_STEP * RECENT_STEP)
    return before.order_by(Statement.created_at, Statement.id).offset(start).all()


def _family(said: Statement):
    """The turn rows before these words, from any of that user's sessions on
    the family."""
    family = said.discussion
    return TurnEvent.query.join(
        Discussion, Discussion.id == TurnEvent.discussion_id
    ).filter(
        Discussion.diagram_id == family.diagram_id,
        Discussion.user_id == family.user_id,
        TurnEvent.created_at < said.created_at,
    )


def _notes(said: Statement):
    """The coach's notes before these words, newest first."""
    return (
        _family(said)
        .filter(
            TurnEvent.kind == TurnEventKind.ToolCall.value,
            TurnEvent.payload["name"].as_string() == ToolName.CoachNotes.value,
            TurnEvent.payload["refusal"].as_string().is_(None),
        )
        .order_by(TurnEvent.id.desc())
    )


def last_notes(said: Statement) -> TurnEvent | None:
    """The coach's latest notes before these words, from whichever of that
    user's sessions on the family."""
    return _notes(said).first()


def plateau(said: Statement, diagram_id: int) -> int | None:
    """The turn the coach's plateau note is on while it holds. It starts at
    the first of the coach's unbroken notes saying the plateau is reached and
    lapses after PLATEAU_TURNS turns, or once a person or event is added."""
    run = list(
        itertools.takewhile(
            lambda row: row.payload["args"]["plateau"]["reached"],
            _notes(said).limit(coverage.PLATEAU_TURNS + 1),
        )
    )
    if not run or len(run) > coverage.PLATEAU_TURNS:
        return None
    start = run[-1]
    turns = (
        _family(said)
        .filter(
            TurnEvent.kind == TurnEventKind.Done.value,
            TurnEvent.created_at > start.created_at,
        )
        .count()
    )
    added = any(
        delta["field"] is None
        and delta["before"] is None
        and ItemKind(delta["item_kind"]) in (ItemKind.Person, ItemKind.Event)
        for change in Change.query.filter(
            Change.diagram_id == diagram_id,
            Change.created_at > start.created_at,
            Change.turn_id != start.turn_id,
        )
        for delta in change.deltas
    )
    return None if added or turns > coverage.PLATEAU_TURNS else turns


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


def _settled(messages: list[dict]) -> int:
    """How many messages a user's words would leave as they are: they join a
    user message already last, so that one is not settled."""
    return len(messages) - (1 if messages and messages[-1]["role"] == "user" else 0)


def _blocks(content: str | list[dict]) -> list[dict]:
    return [{"type": "text", "text": content}] if isinstance(content, str) else content
