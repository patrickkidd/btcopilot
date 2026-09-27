import enum

from sqlalchemy import Column, DateTime, Enum, Float, String, Text, UniqueConstraint

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class QualityKind(enum.StrEnum):
    EvalPassRate = "eval_pass_rate"
    ExtractionF1 = "extraction_f1"
    CodingF1 = "coding_f1"


class QualityRun(db.Model, ModelMixin):
    """One measured value of one recorded run, for the quality dashboard. The
    release loads every run recorded in the repository (R-0517)."""

    __tablename__ = "quality_runs"
    __table_args__ = (
        UniqueConstraint("kind", "ran_at", "commit", "metric", name="uq_quality_runs_run"),
    )

    ran_at = Column(DateTime, nullable=False)
    commit = Column(String(64), nullable=False)
    model = Column(String(64), nullable=True)
    kind = Column(
        Enum(QualityKind, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    metric = Column(String(255), nullable=False)
    value = Column(Float, nullable=False)
    note = Column(Text, nullable=True)
