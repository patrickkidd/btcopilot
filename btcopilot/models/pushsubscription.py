from sqlalchemy import Column, ForeignKey, Integer, String, Text

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class PushSubscription(db.Model, ModelMixin):
    """One browser's address for web push, made when its person asked the
    coach to message first."""

    __tablename__ = "push_subscriptions"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(String(255), nullable=False)
    auth = Column(String(255), nullable=False)

    def info(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.p256dh, "auth": self.auth},
        }
