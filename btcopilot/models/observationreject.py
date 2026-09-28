from sqlalchemy import Column, String, Text

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class ObservationReject(db.Model, ModelMixin):
    """A group of observations Patrick rejected, so it stays off the queue."""

    __tablename__ = "observation_rejects"

    key = Column(String(8), nullable=False, unique=True)
    kind = Column(String(32), nullable=False)
    reason = Column(Text, nullable=False)
