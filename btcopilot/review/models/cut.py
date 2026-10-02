from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Cut(db.Model, ModelMixin):
    """A range of lines in a family's thread, frozen and put on the agenda
    (R-0296): a first and a last line, in one sitting or across several. The
    sitting each line belongs to is that line's own. A new one continues right
    after the last one ended by default; code, not the table definition, blocks
    overlapping ranges.
    """

    __tablename__ = "review_cuts"

    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=False, index=True)
    start_statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    end_statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    meeting_date = Column(Date, nullable=True)
    vote_opened_at = Column(DateTime, nullable=True)
    nudged_at = Column(DateTime, nullable=True)
    ratified_at = Column(DateTime, nullable=True)
    agreement = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    #: Where the coach read this cut differently from the room, written once at
    #: ratification because it costs a model call to say why (R-0254).
    audit = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)

    codings = relationship(
        "Coding", back_populates="cut", cascade="all, delete-orphan"
    )
    items = relationship("Item", back_populates="cut", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Cut {self.id}: family {self.diagram_id} "
            f"{self.start_statement_id}..{self.end_statement_id}>"
        )
