from sqlalchemy import (
    JSON,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


def _owned(table: str) -> ForeignKey:
    return ForeignKey(f"{table}.id", ondelete="CASCADE")


class ShadowTurn(db.Model, ModelMixin):
    """A real turn run again on one shadow model over a copy of the record, kept
    only for comparison; one row per real turn and model. `snapshot` is the
    record as the real turn found it, cleared when the run ends; the counts stay
    null until then."""

    __tablename__ = "shadow_turns"
    __table_args__ = (
        UniqueConstraint("turn_id", "model", name="uq_shadow_turns_turn_model"),
    )

    turn_id = Column(String(64), nullable=False)
    user_id = Column(Integer, _owned("users"), nullable=False, index=True)
    diagram_id = Column(Integer, _owned("diagrams"), nullable=False)
    discussion_id = Column(Integer, _owned("discussions"), nullable=False)
    statement_id = Column(Integer, _owned("statements"), nullable=False)
    model = Column(String(64), nullable=False)
    snapshot = Column(Text, nullable=True)
    text = Column(Text, nullable=True)
    tool_calls = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cache_creation_tokens = Column(Integer, nullable=True)
    cache_read_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
