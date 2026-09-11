from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Cut(db.Model, ModelMixin):
    """A window of one session's turns, frozen and put on the table (R-0296).

    The window is two cursors so any stretch of turns can be a cut later. The
    app sets the start to the previous cut's end plus one and refuses overlap
    in code, never in the schema.
    """

    __tablename__ = "review_cuts"

    discussion_id = Column(
        Integer, ForeignKey("discussions.id"), nullable=False, index=True
    )
    start_statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    end_statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    meeting_date = Column(Date, nullable=True)
    vote_opened_at = Column(DateTime, nullable=True)
    ratified_at = Column(DateTime, nullable=True)
    agreement = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)

    codings = relationship(
        "Coding", back_populates="cut", cascade="all, delete-orphan"
    )
    items = relationship("Item", back_populates="cut", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Cut {self.id}: session {self.discussion_id} "
            f"{self.start_statement_id}..{self.end_statement_id}>"
        )
