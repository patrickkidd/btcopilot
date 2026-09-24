from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Coding(db.Model, ModelMixin):
    """One coder's reading of one cut, on their own record of the case.

    `agent` is set only when the coach did the coding — the model and the
    prompt version it ran. A coding with no agent is a person's (R-0242).
    """

    __tablename__ = "review_codings"
    __table_args__ = (
        UniqueConstraint("cut_id", "user_id", name="uq_review_codings_cut_user"),
    )

    cut_id = Column(Integer, ForeignKey("review_cuts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=False)
    agent = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    done_at = Column(DateTime, nullable=True)

    cut = relationship("Cut", back_populates="codings")

    def __repr__(self):
        return f"<Coding {self.id}: cut {self.cut_id} by user {self.user_id}>"
