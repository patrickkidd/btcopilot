"""
Training data models for AI auditing web application.

These models are designed to work with any SQLAlchemy database session
provided by the parent application. No direct database dependencies.

Standalone SQLAlchemy models that can be imported and used by any Flask
application that provides the database session.
"""

import enum
from sqlalchemy import Column, Text, Integer, ForeignKey, JSON, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
# Import database infrastructure and base mixins from btcopilot
from ..extensions import db
from ..modelmixin import ModelMixin


class SpeakerType(enum.StrEnum):
    """Enum for speaker types in discussions"""
    Expert = "expert"
    Subject = "subject"


class Statement(db.Model, ModelMixin):
    """Individual statements in a discussion with extraction data"""

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
        return f"<Statement {self.id}: {self.text[:50] if self.text else 'None'}...>"


class Discussion(db.Model, ModelMixin):
    """A discussion thread containing multiple statements"""

    __tablename__ = "discussions"

    user_id = Column(Integer)  # References User from parent app
    diagram_id = Column(Integer)  # References Diagram from parent app  
    summary = Column(Text)
    last_topic = Column(
        Text,
        comment="A the topic that the model should follow the user on, e.g. presenting problem, new issue",
    )
    extracting = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether background extraction job should run for this discussion's statements",
    )
    
    # Note: user and diagram relationships will be handled by parent app
    statements = relationship(
        "Statement", back_populates="discussion", order_by="Statement.order"
    )
    speakers = relationship(
        "Speaker", foreign_keys="Speaker.discussion_id", back_populates="discussion"
    )

    chat_user_speaker_id = Column(
        Integer,
        ForeignKey("speakers.id"),
        nullable=True,
        comment="The user speaker in a chat context",
    )
    chat_user_speaker = relationship(
        "Speaker",
        foreign_keys=[chat_user_speaker_id],
        back_populates="user_discussion",
        uselist=False,
    )

    chat_ai_speaker_id = Column(
        Integer,
        ForeignKey("speakers.id"),
        nullable=True,
        comment="The AI speaker in a chat context",
    )
    chat_ai_speaker = relationship(
        "Speaker",
        foreign_keys=[chat_ai_speaker_id],
        back_populates="ai_discussion",
        uselist=False,
    )

    def conversation_history(self) -> str:
        """
        Returns a string of the conversation history for this discussion.
        """
        return (
            "\n".join(
                [
                    f"{s.speaker.name if s.speaker else 'Unknown'}: {s.text}"
                    for s in self.statements
                ]
            )
            if self.statements
            else "(No statements in this discussion yet)"
        )

    def next_order(self) -> int:
        """Get the next order number for this discussion."""
        # Note: Parent app will need to provide session for this query
        # This is a placeholder - actual implementation depends on session access
        max_order = 0
        if self.statements:
            max_order = max(s.order or 0 for s in self.statements)
        return max_order + 1

    def __repr__(self):
        return f"<Discussion {self.id}: {self.summary[:50] if self.summary else 'None'}...>"


class Speaker(db.Model, ModelMixin):
    """Speakers in discussions (e.g., user, AI, family members)"""

    __tablename__ = "speakers"

    discussion_id = Column(Integer, ForeignKey("discussions.id"))
    person_id = Column(
        Integer
    )  # References a Person in therapist.database.Database JSON data
    name = Column(String(255))  # Speaker name/identifier
    type = Column(Enum(SpeakerType))  # 'expert' or 'subject'

    discussion = relationship(
        "Discussion", foreign_keys=[discussion_id], back_populates="speakers"
    )
    statements = relationship("Statement", back_populates="speaker")

    # Back references for specific speaker roles in discussions
    user_discussion = relationship(
        "Discussion",
        foreign_keys="Discussion.chat_user_speaker_id",
        back_populates="chat_user_speaker",
    )
    ai_discussion = relationship(
        "Discussion",
        foreign_keys="Discussion.chat_ai_speaker_id",
        back_populates="chat_ai_speaker",
    )

    def __repr__(self):
        return f"<Speaker {self.id}: {self.name} ({self.type})>"


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


# Export all models for easy import
__all__ = [
    'Statement',
    'Discussion', 
    'Speaker',
    'SpeakerType',
    'Feedback'
]