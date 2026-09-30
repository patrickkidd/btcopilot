import enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class NotificationChannel(enum.StrEnum):
    """App: shown only in the app's own list, sent nowhere else."""

    Push = "push"
    Email = "email"
    App = "app"


class NotificationKind(enum.StrEnum):
    """What a notification points at, each kind held back only by its own."""

    Coach = "coach"
    Task = "task"
    Reminder = "reminder"
    Notice = "notice"


class Notification(db.Model, ModelMixin):
    """One delivery to one person, and when they opened or dismissed it: a
    coach message already in the thread, a coding task on the agenda, or a
    product notice."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'coach') = (statement_id IS NOT NULL)"
            " AND (kind IN ('task', 'reminder')) = (cut_id IS NOT NULL)"
            " AND (kind = 'notice') = (notice_id IS NOT NULL)",
            name="notification_points_at_its_kind",
        ),
        UniqueConstraint("user_id", "notice_id", name="notification_one_per_notice"),
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
    notice_id = Column(Integer, ForeignKey("notices.id", ondelete="CASCADE"))
    channel = Column(
        Enum(NotificationChannel, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    opened_at = Column(DateTime)

    statement = relationship("Statement")
    notice = relationship("Notice")
