from sqlalchemy import Column, ForeignKey, Integer, String, Text

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Note(db.Model, ModelMixin):
    """What a coder typed about one turn, kept so their own words stay in the
    thread under the line they coded (R-0270)."""

    __tablename__ = "review_notes"

    coding_id = Column(
        Integer, ForeignKey("review_codings.id"), nullable=False, index=True
    )
    statement_id = Column(Integer, nullable=False, index=True)
    text = Column(Text, nullable=False)
    # The scribe's own id for this utterance, which it stamps on every change
    # it makes from it, so the lines it wrote sit under the right words.
    turn_id = Column(String(64), nullable=False, index=True)

    def __repr__(self):
        return f"<Note {self.id}: coding {self.coding_id} turn {self.statement_id}>"
