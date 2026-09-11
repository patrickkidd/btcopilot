import enum

from sqlalchemy import Column, DateTime, Enum, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class RuleSource(enum.StrEnum):
    Ai = "ai"
    Migration = "migration"
    Human = "human"


class Rule(db.Model, ModelMixin):
    """One coding guideline. Never deleted; retired instead (R-0275).

    `source` is the item and cut it came from, or last year's meeting number
    for a migrated row. `flags` holds who flagged it for the next meeting and
    who closed their own flag.
    """

    __tablename__ = "review_rules"

    text = Column(Text, nullable=False)
    source = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict)
    drafted_by = Column(
        Enum(RuleSource, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    flags = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list)
    ratified_at = Column(DateTime, nullable=True)
    retired_at = Column(DateTime, nullable=True)

    def open_flags(self) -> list[dict]:
        return [f for f in (self.flags or []) if not f.get("closed_at")]

    def __repr__(self):
        return f"<Rule {self.id}: {self.drafted_by} {self.text[:40]!r}>"
