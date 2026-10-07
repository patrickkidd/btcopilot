import enum

from sqlalchemy import (
    Column,
    Text,
    Integer,
    ForeignKey,
    JSON,
    String,
    Boolean,
    DateTime,
    Enum,
)
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class StatementKind(enum.StrEnum):
    """What kind of message this is, which is how the page routes a tap on its
    chips: a chip in a play-by-play steps the board, a chip anywhere else
    selects the moment it names."""

    Turn = "turn"
    Play = "play"


class Statement(db.Model, ModelMixin):

    __tablename__ = "statements"

    text = Column(Text)
    discussion_id = Column(Integer, ForeignKey("discussions.id"))
    speaker_id = Column(Integer, ForeignKey("speakers.id"))
    # What the coach aimed the picture at on this turn: a list of views, each a
    # view kind plus parameters whose every id resolves in the record (R-0085).
    views = Column(JSON)
    kind = Column(
        Enum(StatementKind, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=StatementKind.Turn,
    )
    # The cluster a play-by-play narrates. Null on every other kind.
    cluster_id = Column(String(64))
    # A play-by-play's snapshots as the coach told them (btcopilot.case). Null
    # on every other kind, and on a play told before snapshots.
    told_case = Column(JSON)
    # What the play was told from: the digest of the cluster's contents as the
    # coach was shown them (btcopilot.playturn). A play told from what the
    # cluster holds now opens with no new call.
    digest = Column(String(64))
    custom_prompts = Column(JSON)  # Store custom prompts used for this statement
    order = Column(Integer)  # Order within discussion for reliable sorting
    # The coach turn this statement started or answered; its tool calls are the
    # turn events with the same id.
    turn_id = Column(String(64), index=True)
    prompt_version = Column(String(16), nullable=True)
    # A file attached to the words: its name, and the text a model read from it
    # once. The file itself is not kept; the coach sees only this text.
    attachment_name = Column(String(255))
    attachment_text = Column(Text)

    # Approval fields for test case generation
    approved = Column(Boolean, default=False)
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    exported_at = Column(DateTime)  # Track when exported as test case

    discussion = relationship("Discussion", back_populates="statements")
    speaker = relationship("Speaker", back_populates="statements")

    @property
    def spoken(self) -> str:
        """The words as the coach reads them: what was typed, then what the
        attached file holds [Oracle: R-0828, R-0829]."""
        if self.attachment_name is None:
            return self.text
        return (
            f"{self.text}\n\nFrom the file {self.attachment_name} (enter every "
            f"person and every dated event in it, births too, before you reply):\n"
            f"{self.attachment_text}"
        )

    @property
    def is_approved(self):
        """Check if this statement's extraction is approved"""
        return bool(self.approved)

    def __repr__(self):
        return f"<Statement {self.id}: {self.text[:50]}...>"
