from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Feedback(db.Model, ModelMixin):
    """Stores feedback from domain experts on AI responses"""

    __tablename__ = "feedbacks"

    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    auditor_id = Column(String(100), nullable=False)
    feedback_type = Column(String(20), nullable=False)  # 'conversation' or 'extraction'
    thumbs_down = Column(Boolean, default=False)
    comment = Column(Text, nullable=True)
    edited_extraction = Column(JSON, nullable=True)

    # Approval fields for test case generation
    approved = Column(Boolean, default=False)
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    exported_at = Column(DateTime)  # Track when exported as test case
    rejection_reason = Column(Text)  # Admin notes on why feedback wasn't approved

    # Relationships
    statement = relationship("Statement", backref="feedbacks")

    @property
    def is_approved(self):
        """Check if this feedback is approved as ground truth"""
        return bool(self.approved)

    @property
    def can_export(self):
        """Check if this feedback can be exported as a test case"""
        return self.approved and not self.exported_at and self.edited_extraction

    def __repr__(self):
        return f"<Feedback {self.id}: {self.feedback_type} for statement {self.statement_id}>"
