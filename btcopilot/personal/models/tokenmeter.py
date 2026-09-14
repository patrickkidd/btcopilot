from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class TokenMeter(db.Model, ModelMixin):
    """What one reader has spent with the coach in one month, and the ceiling
    they were given. The cap is per month per reader so a top-up raises this row
    and nothing else."""

    __tablename__ = "token_meters"
    __table_args__ = (UniqueConstraint("user_id", "period", name="one_meter_a_month"),)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    period = Column(String(7), nullable=False)  # YYYY-MM
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cap = Column(Integer, nullable=True)

    user = relationship("User")

    def __repr__(self):
        return f"<TokenMeter {self.user_id} {self.period} {self.input_tokens}/{self.output_tokens}>"
