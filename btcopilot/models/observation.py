import enum

from sqlalchemy import Column, Integer, String, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import JSONB

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class ObservationKind(enum.StrEnum):
    """What the watcher after a turn noticed. It changes nothing; each row is a
    candidate case for the coach's regression evals."""

    DuplicatePerson = "duplicate_person"
    DuplicateEvent = "duplicate_event"
    AddWithoutRead = "add_without_read"


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
