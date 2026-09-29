import enum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    or_,
)

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Audience(enum.StrEnum):
    Everyone = "everyone"
    Role = "role"
    People = "people"


class NoticeLink(enum.StrEnum):
    """The screen a notice opens; no link opens nothing."""

    Account = "account"
    CoachSettings = "coach_settings"
    Task = "task"
    Agenda = "agenda"


class Notice(db.Model, ModelMixin):
    """A product message written once with who it is for. Each person it
    reaches gets their own notification row the next time they open the app,
    so someone who joins its audience later still gets it while it runs."""

    __tablename__ = "notices"
    __table_args__ = (
        CheckConstraint(
            "(audience = 'role') = (role IS NOT NULL)"
            " AND (audience = 'people') = (user_ids IS NOT NULL)",
            name="notice_names_its_audience",
        ),
    )

    title = Column(String(100), nullable=False)
    body = Column(String(300), nullable=False)
    link = Column(Enum(NoticeLink, values_callable=lambda e: [x.value for x in e]))
    audience = Column(
        Enum(Audience, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    role = Column(String(32))
    user_ids = Column(JSON(none_as_null=True))
    starts_at = Column(DateTime)
    ends_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    @classmethod
    def live(cls, now):
        return cls.query.filter(
            or_(cls.starts_at.is_(None), cls.starts_at <= now),
            or_(cls.ends_at.is_(None), cls.ends_at > now),
        ).order_by(cls.id)

    def reaches(self, user) -> bool:
        if self.audience == Audience.Everyone:
            return True
        if self.audience == Audience.Role:
            return user.has_role(self.role)
        return user.id in self.user_ids
