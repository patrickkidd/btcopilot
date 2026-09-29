import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Trigger(enum.StrEnum):
    """What made the coach write first."""

    Correlation = "correlation"
    FollowUp = "follow_up"


class ProactiveMessage(db.Model, ModelMixin):
    """A message the coach writes before the person does: a pattern the record
    just made visible, or a follow-up the person agreed to, which waits here
    unsent until it is due. Whether its notification was opened is kept with
    the notification."""

    __tablename__ = "proactive_messages"
    __table_args__ = (
        UniqueConstraint("diagram_id", "key", name="one_message_a_pattern"),
    )

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    diagram_id = Column(
        Integer, ForeignKey("diagrams.id", ondelete="CASCADE"), nullable=False
    )
    # "trigger" alone is a type Postgres already has.
    trigger = Column(
        Enum(
            Trigger,
            name="proactivetrigger",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    # A pattern's identity in the record, so the same one is never written twice.
    key = Column(String(64))
    question = Column(Text)
    due_at = Column(DateTime)
    statement_id = Column(Integer, ForeignKey("statements.id", ondelete="SET NULL"))
    # Kept apart from the statement, so a message whose sitting was deleted is
    # still known to have gone and is never sent again.
    sent_at = Column(DateTime)
    replied_at = Column(DateTime)

    statement = relationship("Statement")

    def __repr__(self):
        return f"<ProactiveMessage {self.id}: {self.trigger} {self.key or self.due_at}>"
