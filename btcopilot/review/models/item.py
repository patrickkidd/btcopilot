import enum

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin
from btcopilot.schema import ItemKind


class ReviewStatus(enum.StrEnum):
    Agreed = "agreed"
    Disputed = "disputed"
    Decided = "decided"
    Unresolved = "unresolved"


class Item(db.Model, ModelMixin):
    """One event, person or pair bond as every coder saw it.

    `opinions` is the list of {coding_id, item_id, item} the matcher paired across
    the codings, each item the schema's own dict. It is a snapshot taken when
    the vote opens and is never maintained afterwards.
    """

    __tablename__ = "review_items"

    cut_id = Column(Integer, ForeignKey("review_cuts.id"), nullable=False, index=True)
    item_kind = Column(
        Enum(ItemKind, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    item_id = Column(String(64), nullable=True)
    opinions = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    status = Column(
        Enum(ReviewStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    #: The matcher could not tell which person of another coding this is, so the
    #: room decides who is who rather than the match being guessed (R-0326).
    ambiguous = Column(Boolean, nullable=False, default=False, server_default="0")
    decision_change_id = Column(
        Integer, ForeignKey("diagram_changes.id"), nullable=True
    )
    #: Which coding's version the room kept, so a decided item opens with that
    #: row lit however long after the meeting it is read (R-0339). The record
    #: keeps the words, not where they came from, so the choice lives here.
    kept_coding_id = Column(
        Integer, ForeignKey("review_codings.id"), nullable=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    cut = relationship("Cut", back_populates="items")
    votes = relationship("Vote", back_populates="item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Item {self.id}: {self.item_kind} {self.status}>"
