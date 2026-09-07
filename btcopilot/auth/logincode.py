import datetime
import random

import flask_bcrypt
from sqlalchemy import Column, DateTime, Integer, String

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin

MAX_TRIES = 5


class LoginCode(db.Model, ModelMixin):
    """A six-digit code emailed to one address, good once for ten minutes."""

    __tablename__ = "login_codes"

    email = Column(String(255), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)
    tries = Column(Integer, nullable=False, default=0, server_default="0")

    @staticmethod
    def issue(email: str, minutes: int) -> tuple["LoginCode", str]:
        code = f"{random.SystemRandom().randrange(10**6):06d}"
        login_code = LoginCode(
            email=email,
            code_hash=flask_bcrypt.generate_password_hash(code).decode("utf8"),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes),
        )
        db.session.add(login_code)
        db.session.commit()
        return login_code, code

    @staticmethod
    def issued_since(email: str, since: datetime.datetime) -> int:
        return LoginCode.query.filter(
            LoginCode.email == email, LoginCode.created_at >= since
        ).count()

    @staticmethod
    def pending(email: str) -> "LoginCode | None":
        found = (
            LoginCode.query.filter_by(email=email, used_at=None)
            .order_by(LoginCode.created_at.desc())
            .first()
        )
        return found if found and found.live() else None

    def live(self) -> bool:
        return (
            self.used_at is None
            and self.tries < MAX_TRIES
            and self.expires_at > datetime.datetime.utcnow()
        )

    def matches(self, code: str) -> bool:
        self.tries += 1
        db.session.commit()
        return flask_bcrypt.check_password_hash(self.code_hash, code)

    def consume(self):
        self.used_at = datetime.datetime.utcnow()
        db.session.commit()
