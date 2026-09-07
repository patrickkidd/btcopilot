import enum

from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin
from btcopilot.schema import ItemKind


class InteractionKind(enum.StrEnum):
    Look = "look"
    Say = "say"
    ChipTap = "chip_tap"
    Play = "play"


class Interaction(db.Model, ModelMixin):
    """Who looked at, spoke about, tapped or played an item of the record."""

    __tablename__ = "interactions"

    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(64), nullable=True)
    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=True)
    kind = Column(
        Enum(InteractionKind, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    item_kind = Column(
        Enum(ItemKind, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    item_id = Column(String(64), nullable=True)

    diagram = relationship("Diagram")
    statement = relationship("Statement")

    def __repr__(self):
        return f"<Interaction {self.id}: {self.kind} {self.item_kind} {self.item_id}>"
