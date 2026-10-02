import enum

from sqlalchemy import JSON, Boolean, Column, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin

NOTE_CAP = 200


class PickSource(enum.StrEnum):
    Shadow = "shadow"
    Replay = "replay"
    Chat = "chat"


class PickChoice(enum.StrEnum):
    Left = "left"
    Right = "right"
    Tie = "tie"


def _enum(kind: type[enum.StrEnum]) -> Enum:
    return Enum(kind, values_callable=lambda e: [x.value for x in e])


class Pick(db.Model, ModelMixin):
    """Patrick's blind pick between two replies to the same words (R-0599).

    The row is made when the pair is first served, which fixes its random side
    order; `choice` stays null until he picks. `pair` names the two replies so
    a pair is served once. The refs hold the model names, which never leave
    the server before the pick. The texts are the two replies as served, kept
    here so a deleted replay or shadow row never loses what he judged.
    """

    __tablename__ = "model_picks"

    pair = Column(String(64), nullable=False, unique=True)
    source = Column(_enum(PickSource), nullable=False)
    left_ref = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    right_ref = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    left_text = Column(Text, nullable=False)
    right_text = Column(Text, nullable=False)
    choice = Column(_enum(PickChoice), nullable=True)
    left_acceptable = Column(Boolean, nullable=True)
    right_acceptable = Column(Boolean, nullable=True)
    note = Column(String(NOTE_CAP), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
