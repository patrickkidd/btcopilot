import datetime
import secrets

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class WebSession(db.Model, ModelMixin):
    """A browser sign-in for the chat app, listable and revocable server-side.
    The seam for passkeys: a passkey login creates one of these exactly as the
    invite link and the emailed code do."""

    __tablename__ = "web_sessions"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User")

    token = Column(String(64), nullable=False, unique=True, index=True)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime)
    user_agent = Column(String(255), nullable=False, server_default="")

    @staticmethod
    def start(user, days: int, user_agent: str) -> "WebSession":
        now = datetime.datetime.utcnow()
        web_session = WebSession(
            user_id=user.id,
            token=secrets.token_urlsafe(32),
            last_seen_at=now,
            expires_at=now + datetime.timedelta(days=days),
            user_agent=(user_agent or "")[:255],
        )
        db.session.add(web_session)
        db.session.commit()
        return web_session

    @staticmethod
    def live_for(user) -> list["WebSession"]:
        return [
            x
            for x in WebSession.query.filter_by(user_id=user.id).order_by(
                WebSession.created_at.desc()
            )
            if x.live()
        ]

    def live(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.datetime.utcnow()

    def touch(self):
        self.last_seen_at = datetime.datetime.utcnow()
        db.session.commit()

    def revoke(self):
        self.revoked_at = datetime.datetime.utcnow()
        db.session.commit()
