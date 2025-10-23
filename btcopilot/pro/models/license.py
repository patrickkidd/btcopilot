import uuid, datetime

from sqlalchemy import (
    Column,
    Boolean,
    String,
    Integer,
    ForeignKey,
    DateTime,
    Index,
)
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class License(db.Model, ModelMixin):
    """A license key that a user purchases, which is an instance of a policy."""

    __tablename__ = "licenses"

    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    user = relationship("User", back_populates="licenses")

    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    policy = relationship("Policy", uselist=False, back_populates="licenses")

    activations = relationship("Activation", back_populates="license")
    key = Column(String(64), nullable=False, unique=True)

    # License allows use on machine
    activated_at = Column(
        DateTime, nullable=True
    )  # allows importing unclaimed licenses by key
    active = Column(
        Boolean, nullable=False, default=True
    )  # Synonymous with 'expired'. An inactive license doesn't allow use in the app

    # License subscription has been canceled but can run on machine until plan interval expires
    canceled_at = Column(DateTime, nullable=True)
    canceled = Column(Boolean, default=False)

    stripe_id = Column(String(64))

    index = Index(user_id, key)

    @staticmethod
    def generate_key():
        key = uuid.uuid4()
        unique = False
        while not unique:
            key = str(uuid.uuid4())
            if License.query.filter_by(key=key).count() == 0:
                unique = True
        return key

    def __init__(self, *args, **kwargs):
        key = self.generate_key()  # before ctor
        db.Model.__init__(self, *args, **kwargs)
        self.key = key

    def __str__(self):
        return "<License id: %i, %s, key: %s, active: %s>" % (
            self.id,
            self.policy.code,
            self.key,
            self.active,
        )

    def days_old(self):
        if self.activated_at:
            return (datetime.datetime.utcnow() - self.activated_at).days
        return 0
