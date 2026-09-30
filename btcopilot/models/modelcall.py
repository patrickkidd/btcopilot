import enum

from sqlalchemy import JSON, Column, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Purpose(enum.StrEnum):
    """What a call was for, so shadow and replay spend is kept apart from what
    the coach spends on the people it talks to."""

    Coach = "coach"
    Shadow = "shadow"
    Proactive = "proactive"
    Replay = "replay"
    Play = "play"
    Backfill = "backfill"
    Summary = "summary"


class ModelCall(db.Model, ModelMixin):
    """One call to the model: who it was for, what it spent and what it cost.
    `model` is the model that answered; `fallback` is every hop the fallbacks
    made to get there, or null when the requested model answered."""

    __tablename__ = "model_calls"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=False)
    turn_id = Column(String(64), nullable=False, index=True)
    purpose = Column(
        Enum(Purpose, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    model = Column(String(64), nullable=False)
    fallback = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cache_creation_tokens = Column(Integer, nullable=False)
    cache_read_tokens = Column(Integer, nullable=False)
    cost_usd = Column(Numeric(10, 6), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    tool_calls = Column(Integer, nullable=False)
