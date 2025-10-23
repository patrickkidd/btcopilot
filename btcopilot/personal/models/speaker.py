import enum
from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class SpeakerType(enum.StrEnum):
    Expert = "expert"
    Subject = "subject"


class Speaker(db.Model, ModelMixin):

    __tablename__ = "speakers"

    discussion_id = Column(Integer, ForeignKey("discussions.id"))
    person_id = Column(Integer)  # References a Person in btco[ilot.schema JSON data
    name = Column(String(255))  # Speaker name/identifier
    type = Column(Enum(SpeakerType))  # 'expert' or 'family'

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
