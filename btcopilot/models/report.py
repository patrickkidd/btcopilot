import enum

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Text

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class ReportKind(enum.StrEnum):
    """What the coach offered to send from the conversation: the app or the
    coach behaving wrongly as the person experienced it, or what they want
    changed in the app [Oracle: R-0056]."""

    Bug = "bug"
    Feedback = "feedback"


class ReportStatus(enum.StrEnum):
    Sent = "sent"
    Declined = "declined"


def _enum(kind):
    return Enum(kind, values_callable=lambda e: [x.value for x in e])


class Report(db.Model, ModelMixin):
    """One bug or piece of feedback the coach offered and the person
    answered. An error in the code is never a row: it is Grafana's."""

    __tablename__ = "reports"

    kind = Column(_enum(ReportKind), nullable=False)
    status = Column(_enum(ReportStatus), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    diagram_id = Column(Integer, ForeignKey("diagrams.id", ondelete="SET NULL"), index=True)
    turn_id = Column(String(64))
    statement_id = Column(Integer)
    release = Column(String(64), nullable=False)
    # the screen the page was on
    address = Column(String(300))
    # the words the coach offered to send
    words = Column(Text)

    def __repr__(self):
        return f"<Report {self.id}: {self.kind} {self.status}>"
