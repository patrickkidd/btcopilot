from sqlalchemy import Column, Text, Integer, Boolean
from sqlalchemy.orm import relationship

from btcopilot.extensions import db, llm, LLMFunction
from btcopilot.modelmixin import ModelMixin


class Discussion(db.Model, ModelMixin):

    __tablename__ = "discussions"

    user_id = Column(Integer, db.ForeignKey("users.id"))
    diagram_id = Column(Integer, db.ForeignKey("diagrams.id"))
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
    user = relationship("User")
    diagram = relationship("Diagram", back_populates="discussions")
    statements = relationship(
        "Statement", back_populates="discussion", order_by="Statement.order"
    )
    speakers = relationship(
        "Speaker", foreign_keys="Speaker.discussion_id", back_populates="discussion"
    )

    chat_user_speaker_id = Column(
        Integer,
        db.ForeignKey("speakers.id"),
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
        db.ForeignKey("speakers.id"),
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

    def update_summary(self):
        from btcopilot.personal.prompts import SUMMARIZE_MESSAGES_PROMPT

        self.summary = llm.submit_one(
            LLMFunction.Summarize,
            SUMMARIZE_MESSAGES_PROMPT.format(
                conversation_history=self.conversation_history()
            ),
        )

    def next_order(self) -> int:
        """Get the next order number for this discussion."""
        from btcopilot.personal.models import Statement

        max_order = (
            db.session.query(db.func.max(Statement.order))
            .filter(Statement.discussion_id == self.id)
            .scalar()
        )
        return (max_order or 0) + 1
