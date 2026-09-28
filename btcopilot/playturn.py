"""The play-by-play for one cluster, told by the coach as snapshots [R-0542].

The coach picks the point, the dates and the words; the page draws each
snapshot from the record. It tells the case through one tool call, checked
against the cluster before anything is kept: a call the cluster does not bear
out is handed back to the coach with what is wrong, and a coach that never
tells it fails the turn.

The case is a message in the session like any other, marked as a play, so
coming back a week later shows it where it happened and opens it again.
"""

import logging
import uuid

from btcopilot.extensions import db
from btcopilot import recordtext
from btcopilot.case import Case, RecordFault, Tool, Untold, faults, tool
from btcopilot.coachmodel import CoachModel
from btcopilot.coachturn import Metered
from btcopilot.llmutil import ANTHROPIC_TIMEOUT
from btcopilot.models import Discussion, Statement, StatementKind
from btcopilot import prompts
from btcopilot.schema import DiagramData

_log = logging.getLogger(__name__)

# How many times a case the cluster does not bear out is handed back.
TRIES = 3
# What an answer in words gets back: the coach's model refuses a forced call.
ASK = "Answer only by calling play_by_play once, with the pictures."
# The longest the server takes to answer, every try timing out at the model's
# own limit, and the page's wait for it (web/src/api.ts PLAY_WAIT_S) with a
# little over, so a slow model fails with the server's error, not the page's.
WAIT = TRIES * ANTHROPIC_TIMEOUT + 30


class Untellable(Exception):
    """The coach did not tell the case: no call at all, or none the cluster bore
    out in every try. The page is told so in plain words (R-0182)."""

    def __init__(self, why: str):
        super().__init__("untold: The coach couldn't tell this one; try again.")
        self.why = why


class PlayTurn:
    """One cluster in, one told case out."""

    def __init__(
        self,
        data: DiagramData,
        cluster: dict,
        *,
        discussion: Discussion | None = None,
        model: CoachModel | None = None,
    ):
        self.data = data
        self.cluster = cluster
        self.discussion = discussion
        self.turn_id = uuid.uuid4().hex
        self.model = model or CoachModel(timeout=ANTHROPIC_TIMEOUT)
        # Asked for in a session, the calls are charged to its owner like a turn's.
        if discussion is not None:
            self.model = Metered(
                self.model, discussion.user_id, discussion.diagram_id, self.turn_id
            )

    @classmethod
    def stored(cls, data: DiagramData, cluster_id: str, **kwargs) -> "PlayTurn":
        for cluster in data.clusters:
            if isinstance(cluster, dict) and str(cluster.get("id")) == str(cluster_id):
                return cls(data, cluster, **kwargs)
        raise ValueError(f"No cluster {cluster_id!r} in the record")

    @property
    def events(self) -> list[dict]:
        wanted = set(self.cluster.get("eventIds") or [])
        found = [
            e
            for e in self.data.events
            if isinstance(e, dict) and e.get("id") in wanted
        ]
        return sorted(
            found,
            key=lambda e: (recordtext.date_text(e.get("dateTime")) or "", e["id"]),
        )

    def run(self) -> dict:
        events = self.events
        if not events:
            raise ValueError(f"Cluster {self.cluster['id']} has no events to play")
        wrong = faults(self.data)
        if wrong:
            raise RecordFault(f"record fault: {'; '.join(wrong)}. Correct the record first.")
        prompt = prompts.PLAY_BY_PLAY_PROMPT.format(
            cluster=recordtext.cluster_line(self.cluster),
            events="\n".join(recordtext.event_line(e) for e in events),
        )
        system = prompts.get_agent_prompt(record=recordtext.render(self.data))
        messages = [{"role": "user", "content": prompt}]
        told = self._tell(system, messages, events)
        return {
            "kind": StatementKind.Play.value,
            "cluster_id": told.cluster_id,
            "statement": told.point,
            "statement_id": self._persist(told),
            "case": told.asdict(),
        }

    def _tell(self, system: str, messages: list[dict], events: list[dict]) -> Case:
        try:
            return self._tries(system, messages, events)
        finally:
            # every call is charged, the ones that told nothing too
            db.session.commit()

    def _tries(self, system: str, messages: list[dict], events: list[dict]) -> Case:
        for _ in range(TRIES):
            turn = self._call(system, messages)
            call = next((c for c in turn.calls if c.name == Tool.PlayByPlay), None)
            if call is None:
                # an answer in words: asked again for the one call it must make
                _log.info("Play answered in words; asked for the call")
                messages = messages + [
                    {"role": "assistant", "content": turn.blocks},
                    {"role": "user", "content": ASK},
                ]
                continue
            try:
                return Case.told(call.args, self.cluster, events)
            except Untold as untold:
                _log.info(f"Case handed back: {untold}")
                messages = messages + [
                    {"role": "assistant", "content": turn.blocks},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": call.id,
                                "content": str(untold),
                                "is_error": True,
                            }
                        ],
                    },
                ]
        raise Untellable(f"not told in {TRIES} tries")

    def _call(self, system: str, messages: list[dict]):
        words = self.model.turn(system, messages, [tool()])
        while True:
            try:
                next(words)
            except StopIteration as stop:
                return stop.value

    def _persist(self, told: Case) -> int | None:
        if self.discussion is None:
            return None
        statement = Statement(
            discussion_id=self.discussion.id,
            text=told.point,
            speaker=self.discussion.chat_ai_speaker,
            order=self.discussion.next_order(),
            kind=StatementKind.Play,
            cluster_id=told.cluster_id,
            told_case=told.asdict(),
            turn_id=self.turn_id,
        )
        db.session.add(statement)
        db.session.commit()
        return statement.id
