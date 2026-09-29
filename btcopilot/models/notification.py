import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class NotificationChannel(enum.StrEnum):
    Push = "push"
    Email = "email"


class Notification(db.Model, ModelMixin):
    """A pointer to a coach message already in the thread, sent by push or by
    email, and when its person opened it."""

    __tablename__ = "notifications"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    statement_id = Column(
        Integer, ForeignKey("statements.id", ondelete="CASCADE"), nullable=False
    )
    channel = Column(
        Enum(NotificationChannel, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    opened_at = Column(DateTime)

    statement = relationship("Statement")
