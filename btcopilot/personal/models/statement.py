import enum

from sqlalchemy import (
    Column,
    Text,
    Integer,
    ForeignKey,
    JSON,
    String,
    Boolean,
    DateTime,
    Enum,
)
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class StatementKind(enum.StrEnum):
    """What kind of message this is, which is how the page routes a tap on its
    chips: a chip in a play-by-play steps the board, a chip anywhere else
    selects the moment it names."""

    Turn = "turn"
    Play = "play"


class Statement(db.Model, ModelMixin):

    __tablename__ = "statements"

    text = Column(Text)
    discussion_id = Column(Integer, ForeignKey("discussions.id"))
    speaker_id = Column(Integer, ForeignKey("speakers.id"))
    pdp_deltas = Column(JSON)
    # What the coach aimed the picture at on this turn: a list of views, each a
    # view kind plus parameters whose every id resolves in the record (R-0085).
    views = Column(JSON)
    kind = Column(
        Enum(StatementKind, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=StatementKind.Turn,
    )
    # The cluster a play-by-play narrates. Null on every other kind.
    cluster_id = Column(String(64))
    custom_prompts = Column(JSON)  # Store custom prompts used for this statement
    order = Column(Integer)  # Order within discussion for reliable sorting

    # Approval fields for test case generation
    approved = Column(Boolean, default=False)
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    exported_at = Column(DateTime)  # Track when exported as test case

    discussion = relationship("Discussion", back_populates="statements")
    speaker = relationship("Speaker", back_populates="statements")

    @property
    def is_approved(self):
        """Check if this statement's extraction is approved"""
        return bool(self.approved)

    @property
    def can_export(self):
        """Check if this statement can be exported as a test case"""
        return self.approved and not self.exported_at and self.pdp_deltas

    def __repr__(self):
        return f"<Statement {self.id}: {self.text[:50]}...>"
