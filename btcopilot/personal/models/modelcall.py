from sqlalchemy import Column, Integer, String, ForeignKey, Numeric

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class ModelCall(db.Model, ModelMixin):
    """One call to the model: who it was for, what it spent and what it cost."""

    __tablename__ = "model_calls"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=False)
    turn_id = Column(String(64), nullable=False, index=True)
    model = Column(String(64), nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cache_creation_tokens = Column(Integer, nullable=False)
    cache_read_tokens = Column(Integer, nullable=False)
    cost_usd = Column(Numeric(10, 6), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    tool_calls = Column(Integer, nullable=False)
