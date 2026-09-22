import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin
from btcopilot.personal.coachmodel import Spent


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
    cache_creation_tokens = Column(Integer, nullable=False, default=0)
    cache_read_tokens = Column(Integer, nullable=False, default=0)
    cap = Column(Integer, nullable=True)

    user = relationship("User")

    @classmethod
    def charge(cls, user_id: int, spent: Spent, period: str | None = None) -> "TokenMeter":
        period = period or datetime.date.today().strftime("%Y-%m")
        meter = cls.query.filter_by(user_id=user_id, period=period).one_or_none()
        if meter is None:
            meter = cls(
                user_id=user_id,
                period=period,
                input_tokens=0,
                output_tokens=0,
                cache_creation_tokens=0,
                cache_read_tokens=0,
            )
            db.session.add(meter)
        meter.input_tokens += spent.input
        meter.output_tokens += spent.output
        meter.cache_creation_tokens += spent.cache_creation
        meter.cache_read_tokens += spent.cache_read
        return meter

    def __repr__(self):
        return f"<TokenMeter {self.user_id} {self.period} {self.input_tokens}/{self.output_tokens}>"
