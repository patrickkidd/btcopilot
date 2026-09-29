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
from btcopilot.place import APP


class Audience(enum.StrEnum):
    Everyone = "everyone"
    Role = "role"
    People = "people"


class NoticeLink(enum.StrEnum):
    """The fixed screens a notice opens by name. A link may instead be any
    address in the app, starting with /app/ (R-0055); no link opens nothing."""

    Account = "account"
    CoachSettings = "coach_settings"
    Task = "task"
    Agenda = "agenda"


LINKS = ", ".join(f"'{link.value}'" for link in NoticeLink)


class Notice(db.Model, ModelMixin):
    """A product message written once with who it is for. Each person it is
    for gets their own notification row when it is sent; someone who joins
    its audience later gets one the next time they open the app, while it
    runs."""

    __tablename__ = "notices"
    __table_args__ = (
        CheckConstraint(
            "(audience = 'role') = (role IS NOT NULL)"
            " AND (audience = 'people') = (user_ids IS NOT NULL)",
            name="notice_names_its_audience",
        ),
        CheckConstraint(
            f"link IN ({LINKS}) OR link LIKE '{APP}%'",
            name="notice_link_is_a_screen_or_an_address",
        ),
    )

    title = Column(String(100), nullable=False)
    body = Column(String(300), nullable=False)
    link = Column(String(200))
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
