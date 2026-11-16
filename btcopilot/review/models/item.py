import enum

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, JSON, String, Text
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


class PairingConfidence(enum.StrEnum):
    Sure = "sure"
    Likely = "likely"
    Unsure = "unsure"


class Item(db.Model, ModelMixin):
    """One event, person or pair bond as every coder saw it: a pairing.

    `opinions` is the list of {coding_id, item_id, item} the pairing call put
    together across the codings, each item the schema's own dict; one coder may
    hold several entries. Patrick may join or split pairings before the vote
    opens; once open the row is never maintained afterwards (R-0275, R-0963).
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
    #: The pairing call's one line on why these versions are one thing, and
    #: how sure it was; for Patrick before the vote, never for coders (R-0961).
    pairing_reason = Column(Text, nullable=True)
    pairing_confidence = Column(
        Enum(PairingConfidence, values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )

    cut = relationship("Cut", back_populates="items")
    votes = relationship("Vote", back_populates="item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Item {self.id}: {self.item_kind} {self.status}>"
