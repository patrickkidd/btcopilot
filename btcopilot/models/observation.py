import enum

from sqlalchemy import Column, Integer, String, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import JSONB

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class ObservationKind(enum.StrEnum):
    """What shows the coach or the app needing tuning. It changes nothing; each
    row is a candidate case for the coach's regression evals, and the rows are
    grouped into the queue Patrick accepts or rejects [Oracle: R-0517]."""

    DuplicatePerson = "duplicate_person"
    DuplicateEvent = "duplicate_event"
    AddWithoutRead = "add_without_read"
    QuestionUnsaid = "question_unsaid"
    ToolRefused = "tool_refused"
    StepCap = "step_cap"
    TurnFailed = "turn_failed"
    TurnDeclined = "turn_declined"
    PlayRefused = "play_refused"
    PlayFailed = "play_failed"
    EarlierEdit = "earlier_edit"
    # How a message the coach wrote first fared.
    ProactiveSent = "proactive_sent"
    ProactiveOpened = "proactive_opened"
    ProactiveReplied = "proactive_replied"
    ProactiveReturned = "proactive_returned"
    # The words for a message the coach writes first broke its shape.
    ProactiveRefused = "proactive_refused"
    # What a person sent from the app: a turn or the page that broke, or what
    # they want changed in it [Oracle: R-0056].
    Bug = "bug"
    Feedback = "feedback"


REPORTS = (ObservationKind.Bug, ObservationKind.Feedback)


class Observation(db.Model, ModelMixin):
    __tablename__ = "observations"

    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=False, index=True)
    turn_id = Column(String(64), nullable=False, index=True)
    kind = Column(
        Enum(ObservationKind, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    detail = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)

    def __repr__(self):
        return f"<Observation {self.id}: {self.kind} turn {self.turn_id}>"
