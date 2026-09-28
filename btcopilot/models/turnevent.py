from sqlalchemy import Column, Integer, String, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class TurnEvent(db.Model, ModelMixin):
    """What a coach turn did, kept after its live log in Redis expires, so the
    thread shows every tool call in every session and a failed turn can pick up
    where it stopped. `kind` is a TurnEventKind value."""

    __tablename__ = "turn_events"
    __table_args__ = (UniqueConstraint("turn_id", "seq", name="uq_turn_events_seq"),)

    turn_id = Column(String(64), nullable=False, index=True)
    discussion_id = Column(
        Integer, ForeignKey("discussions.id"), nullable=False, index=True
    )
    seq = Column(Integer, nullable=False)
    kind = Column(String(32), nullable=False)
    payload = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)

    def __repr__(self):
        return f"<TurnEvent {self.turn_id}#{self.seq} {self.kind}>"
