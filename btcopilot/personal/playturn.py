"""The play-by-play for one cluster, written by the coach [Oracle: R-0074].

The moves are data and animate deterministically. The coach picks which ones to
speak about and in what order, makes each one a chip, and cannot invent one:
the events it is given are the only ids it sees, and every chip it writes is
checked against the record before the words go out.
"""

import logging

from btcopilot.personal import chips, recordtext
from btcopilot.personal.coachmodel import CoachModel
from btcopilot.personal.prompts import PLAY_BY_PLAY_PROMPT, get_agent_prompt
from btcopilot.schema import DiagramData

_log = logging.getLogger(__name__)


class PlayTurn:
    """One cluster in, one coach message whose chips are its events."""

    def __init__(
        self, data: DiagramData, cluster: dict, *, model: CoachModel | None = None
    ):
        self.data = data
        self.cluster = cluster
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
        words = self.model.turn(
            get_agent_prompt(record=recordtext.render(self.data)),
            [{"role": "user", "content": prompt}],
            [],
        )
        while True:
            try:
                next(words)
            except StopIteration as stop:
                turn = stop.value
                break
        return {
            "cluster_id": self.cluster["id"],
            "statement": chips.validate(turn.text.strip(), self.data),
        }
