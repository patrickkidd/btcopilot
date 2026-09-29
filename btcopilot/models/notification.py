import enum

from sqlalchemy import CheckConstraint, Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class NotificationChannel(enum.StrEnum):
    Push = "push"
    Email = "email"


class NotificationKind(enum.StrEnum):
    """What a notification points at, each kind held back only by its own. A
    notice is reserved for a product notice to one person or a class of
    people; nothing sends one yet."""

    Coach = "coach"
    Task = "task"
    Reminder = "reminder"
    Notice = "notice"


class Notification(db.Model, ModelMixin):
    """A pointer sent by push or by email, and when its person opened it: to a
    coach message already in the thread, or to a coding task on the agenda."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'coach') = (statement_id IS NOT NULL)"
            " AND (kind IN ('task', 'reminder')) = (cut_id IS NOT NULL)",
            name="notification_points_at_its_kind",
        ),
    )

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind = Column(
        Enum(NotificationKind, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    statement_id = Column(Integer, ForeignKey("statements.id", ondelete="CASCADE"))
    cut_id = Column(Integer, ForeignKey("review_cuts.id", ondelete="CASCADE"))
    channel = Column(
        Enum(NotificationChannel, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    opened_at = Column(DateTime)

    statement = relationship("Statement")
