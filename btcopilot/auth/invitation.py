import datetime
import secrets

from sqlalchemy import Column, DateTime, String

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Invitation(db.Model, ModelMixin):
    """A pre-authorized, single-use sign-in link for one email address. Opening
    it is both the login and the signup."""

    __tablename__ = "invitations"

    email = Column(String(255), nullable=False, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)

    @staticmethod
    def issue(email: str, days: int) -> "Invitation":
        invitation = Invitation(
            email=email,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=days),
        )
        db.session.add(invitation)
        db.session.commit()
        return invitation

    def live(self) -> bool:
        return self.used_at is None and self.expires_at > datetime.datetime.utcnow()

    def consume(self):
        self.used_at = datetime.datetime.utcnow()
        db.session.commit()
