from sqlalchemy import Column, Boolean, String, Integer, Float
from sqlalchemy.orm import relationship

import btcopilot
from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


## TODO: Refactor to 'Plan'?? Though this is both a product and a plan here by virtue of `product`
class Policy(db.Model, ModelMixin):
    """A license type that is for sale. Stripe: Product+Plan."""

    __tablename__ = "policies"

    code = Column(String(255), unique=True)
    interval = Column(String(32))  # value matches stripe.Plan.interval
    product = Column(String(128))  # value matches stripe.Plan.interval
    maxActivations = Column(Integer, default=2)
    name = Column(String(64))
    description = Column(String(2048))

    amount = Column(Float(precision=2), default=0.0)
    active = Column(
        Boolean, default=False
    )  # not advertised but working (like alpha|beta), or not working (like forcing to buy a new one)
    public = Column(Boolean, default=False)  # advertised

    licenses = relationship("License", back_populates="policy")

    POLICIES = []
