"""One table for the values an admin sets by hand: a token cap that belongs to
one person, and switches that belong to the whole room. Scope is the row the
value is about — a user id, or nothing when it is the room's."""

import enum

from sqlalchemy import Column, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class SettingKey(enum.StrEnum):
    TokenCap = "token_cap"
    NudgesOn = "nudges_on"


class Setting(db.Model, ModelMixin):
    __tablename__ = "admin_settings"
    __table_args__ = (
        UniqueConstraint("key", "scope_id", name="uq_admin_settings_key_scope"),
    )

    key = Column(String(64), nullable=False, index=True)
    scope_id = Column(Integer, nullable=True)
    value = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)

    def __repr__(self):
        return f"<Setting {self.key} scope {self.scope_id}: {self.value}>"


def read(key: SettingKey, scope_id: int | None = None, default=None):
    row = Setting.query.filter_by(key=key.value, scope_id=scope_id).first()
    return default if row is None else row.value


def write(key: SettingKey, value, scope_id: int | None = None) -> None:
    row = Setting.query.filter_by(key=key.value, scope_id=scope_id).first()
    if row is None:
        row = Setting(key=key.value, scope_id=scope_id)
        db.session.add(row)
    row.value = value
    db.session.commit()


def nudges_on() -> bool:
    """Whether the app may nudge the coders who are not done."""
    return read(SettingKey.NudgesOn, default=True)
