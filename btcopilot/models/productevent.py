from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class ProductEvent(db.Model, ModelMixin):
    """A screen a person opened or a named control they tapped, for reading
    which features get used, by whom, over time."""

    __tablename__ = "product_events"
    __table_args__ = (Index("ix_product_events_user_id_created_at", "user_id", "created_at"),)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=False)
    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=True)
    screen = Column(String(32), nullable=False)
    name = Column(String(64), nullable=False)
    item_kind = Column(String(32), nullable=True)
    item_id = Column(String(64), nullable=True)
    client_at = Column(DateTime, nullable=False)
