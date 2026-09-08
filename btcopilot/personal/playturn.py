"""The play-by-play for one cluster, written by the coach [Oracle: R-0074].

The moves are data and animate deterministically. The coach picks which ones to
speak about and in what order, makes each one a chip, and cannot invent one:
the events it is given are the only ids it sees, and every chip it writes is
checked against the record before the words go out.

The walk is a message in the session like any other, marked as a play so the
page knows a tap on its chips steps the board rather than selecting a moment.
"""

import logging

from btcopilot.extensions import db
from btcopilot.personal import chips, recordtext
from btcopilot.personal.coachmodel import CoachModel
from btcopilot.personal.coachturn import shorten_labels
from btcopilot.personal.models import Discussion, Statement, StatementKind
from btcopilot.personal.prompts import PLAY_BY_PLAY_PROMPT, get_agent_prompt
from btcopilot.schema import DiagramData

_log = logging.getLogger(__name__)


class PlayTurn:
    """One cluster in, one coach message whose chips are its events."""

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
        self.model = model or CoachModel()

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
        prompt = PLAY_BY_PLAY_PROMPT.format(
            cluster=recordtext.cluster_line(self.cluster),
            events="\n".join(recordtext.event_line(e) for e in events),
        )
        system = get_agent_prompt(record=recordtext.render(self.data))
        messages = [{"role": "user", "content": prompt}]
        words = self.model.turn(system, messages, [])
        while True:
            try:
                next(words)
            except StopIteration as stop:
                turn = stop.value
                break

        spoken = shorten_labels(
            self.model, system, messages, turn.text.strip(), self.data
        )
        walk = chips.validate(spoken, self.data)
        return {
            "kind": StatementKind.Play.value,
            "cluster_id": self.cluster["id"],
            "statement": walk,
            "statement_id": self._persist(walk),
        }

    def _persist(self, walk: str) -> int | None:
        """The walk joins the session it was asked for, so coming back a week
        later shows it where it happened."""
        if self.discussion is None:
            return None
        statement = Statement(
            discussion_id=self.discussion.id,
            text=walk,
            speaker=self.discussion.chat_ai_speaker,
            order=self.discussion.next_order(),
            kind=StatementKind.Play,
            cluster_id=self.cluster["id"],
        )
        db.session.add(statement)
        db.session.commit()
        return statement.id
