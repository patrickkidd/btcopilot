import enum

from sqlalchemy import Column, Integer, String, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Author(enum.StrEnum):
    User = "user"
    Coach = "coach"
    Pro = "pro"


class Change(db.Model, ModelMixin):
    """One command against a diagram's record, with the deltas it applied.

    A turn groups the commands of one macro: a coach reply, or a Pro save.
    """

    __tablename__ = "changes"

    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=False, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=True)
    turn_id = Column(String(64), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(64), nullable=True)
    author = Column(
        Enum(Author, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    deltas = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)

    diagram = relationship("Diagram")
    statement = relationship("Statement")

    def __repr__(self):
        return f"<Change {self.id}: {self.author} turn {self.turn_id}, {len(self.deltas)} deltas>"
