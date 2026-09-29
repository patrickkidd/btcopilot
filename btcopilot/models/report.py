import enum

from sqlalchemy import JSON, CheckConstraint, Column, Enum, ForeignKey, Integer, String, Text

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class ReportKind(enum.StrEnum):
    """What a report is: something that broke, or what a person wants changed
    in the app [Oracle: R-0056]."""

    Bug = "bug"
    Feedback = "feedback"


class ReportStatus(enum.StrEnum):
    Sent = "sent"
    Declined = "declined"


class ReportSource(enum.StrEnum):
    """Where a bug was caught: the page, the server itself, or the page's
    service worker."""

    Page = "page"
    Server = "server"
    Worker = "worker"


def _enum(kind):
    return Enum(kind, values_callable=lambda e: [x.value for x in e])


class Report(db.Model, ModelMixin):
    """One bug or piece of feedback. A bug is counted, not repeated: the same
    fault for the same person in the same release on the same day adds to
    `count` rather than making a row."""

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "kind = 'bug' OR (source IS NULL AND signature IS NULL AND error IS NULL"
            " AND frames IS NULL AND request_id IS NULL)",
            name="report_feedback_carries_no_fault",
        ),
    )

    kind = Column(_enum(ReportKind), nullable=False)
    status = Column(_enum(ReportStatus), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    diagram_id = Column(Integer, ForeignKey("diagrams.id", ondelete="SET NULL"), index=True)
    turn_id = Column(String(64))
    statement_id = Column(Integer)
    release = Column(String(64), nullable=False)
    # the screen the page was on, or the address the server was asked for
    address = Column(String(300))
    count = Column(Integer, nullable=False, default=1)
    # a bug's only
    source = Column(_enum(ReportSource))
    signature = Column(Text, index=True)
    error = Column(Text)
    frames = Column(JSON(none_as_null=True))
    request_id = Column(String(32), index=True)
    # the person's own words, which the coach offered to send
    words = Column(Text)

    def __repr__(self):
        return f"<Report {self.id}: {self.kind} {self.status}>"
