import enum

from sqlalchemy import (
    Column,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class VoteChoice(enum.StrEnum):
    Take = "take"
    Change = "change"
    Drop = "drop"


class Vote(db.Model, ModelMixin):
    """One coder's vote on one item before the meeting.

    `value` is {coding_id} for take, or the coder's own item dict for change.
    Names are never shown until the meeting (R-0272).
    """

    __tablename__ = "review_votes"
    __table_args__ = (
        UniqueConstraint("review_item_id", "user_id", name="uq_review_votes_item_user"),
    )

    review_item_id = Column(
        Integer, ForeignKey("review_items.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    choice = Column(
        Enum(VoteChoice, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    value = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    reason = Column(Text, nullable=True)

    item = relationship("Item", back_populates="votes")

    def __repr__(self):
        return f"<Vote {self.id}: item {self.review_item_id} {self.choice}>"
