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

    POLICIES = [
        {
            "code": btcopilot.LICENSE_FREE,
            "product": btcopilot.LICENSE_FREE,
            "name": "Free",
            "amount": 0.0,
            "active": True,
            "public": False,
            "description": "Editing a single digram without export ability. Makes it possible to research your own family.",
        },
        {
            "code": btcopilot.LICENSE_BETA,
            "product": btcopilot.LICENSE_BETA,
            "name": "Beta",
            "amount": 0.0,
            "active": True,
            "public": False,
            "description": "Full functionality for beta releases only. Requires entering a license key provided by Vedanā Media",
        },
        {
            "code": btcopilot.LICENSE_ALPHA,
            "product": btcopilot.LICENSE_ALPHA,
            "name": "Alpha",
            "amount": 0.0,
            "active": True,
            "public": False,
            "description": "Full functionality for alpha releases only. Requires entering a license key provided by Vedanā Media",
        },
        {
            "code": btcopilot.LICENSE_CLIENT_ONCE,
            "product": btcopilot.LICENSE_CLIENT,
            "name": "Client",
            "amount": 19.99,
            "active": True,
            "public": True,
            "description": "Free license plus sharing the free diagram with other one account, e.g. a coach.",
        },
        {
            "code": btcopilot.LICENSE_PROFESSIONAL_MONTHLY,
            "product": btcopilot.LICENSE_PROFESSIONAL,
            "name": "Professional Monthly",
            "amount": 19.99,
            "interval": "month",
            "active": True,
            "public": True,
            "description": "Unlimited family diagrams with full functonality.",
        },
        {
            "code": btcopilot.LICENSE_PROFESSIONAL_ANNUAL,
            "product": btcopilot.LICENSE_PROFESSIONAL,
            "name": "Professional Annual",
            "amount": 199.99,
            "interval": "year",
            "active": True,
            "public": True,
            "description": "Unlimited family diagrams with full functionality.",
        },
    ]
