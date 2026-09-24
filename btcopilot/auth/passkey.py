import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, JSON
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Passkey(db.Model, ModelMixin):
    """One key held by one device — Face ID, a fingerprint, a security key —
    that signs a reader in without an email round trip. Signing in with one
    starts a WebSession exactly as the emailed code and the invite link do."""

    __tablename__ = "passkeys"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User")

    credential_id = Column(String(255), nullable=False, unique=True, index=True)
    public_key = Column(LargeBinary, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0, server_default="0")
    transports = Column(JSON, nullable=False, default=list)
    name = Column(String(255), nullable=False, server_default="")
    last_used_at = Column(DateTime)
    revoked_at = Column(DateTime)

    @staticmethod
    def live_for(user) -> list["Passkey"]:
        return [
            x
            for x in Passkey.query.filter_by(user_id=user.id, revoked_at=None).order_by(
                Passkey.created_at.desc()
            )
        ]

    @staticmethod
    def by_credential_id(credential_id: str) -> "Passkey | None":
        found = Passkey.query.filter_by(credential_id=credential_id).first()
        return found if found and found.revoked_at is None else None

    def used(self, sign_count: int):
        self.sign_count = sign_count
        self.last_used_at = datetime.datetime.utcnow()
        db.session.commit()

    def revoke(self):
        self.revoked_at = datetime.datetime.utcnow()
        db.session.commit()

    def as_row(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
