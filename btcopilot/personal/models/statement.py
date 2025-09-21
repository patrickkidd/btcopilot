from sqlalchemy import (
    Column,
    Text,
    Integer,
    ForeignKey,
    JSON,
    String,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Statement(db.Model, ModelMixin):

    __tablename__ = "statements"

    text = Column(Text)
    discussion_id = Column(Integer, ForeignKey("discussions.id"))
    speaker_id = Column(Integer, ForeignKey("speakers.id"))
    pdp_deltas = Column(JSON)
    custom_prompts = Column(JSON)  # Store custom prompts used for this statement
    order = Column(Integer)  # Order within discussion for reliable sorting

    # Approval fields for test case generation
    approved = Column(Boolean, default=False)
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    exported_at = Column(DateTime)  # Track when exported as test case

    discussion = relationship("Discussion", back_populates="statements")
    speaker = relationship("Speaker", back_populates="statements")

    @property
    def is_approved(self):
        """Check if this statement's extraction is approved"""
        return bool(self.approved)

    @property
    def can_export(self):
        """Check if this statement can be exported as a test case"""
        return self.approved and not self.exported_at and self.pdp_deltas

    def __repr__(self):
        return f"<Statement {self.id}: {self.text[:50]}...>"
