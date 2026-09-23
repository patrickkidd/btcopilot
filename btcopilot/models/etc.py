from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class AccessRight(db.Model, ModelMixin):
    """Added as a list to control users' access to a diagram."""

    __tablename__ = "access_rights"

    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    right = Column(String, nullable=False)

    diagram = relationship(
        "Diagram",
        primaryjoin="AccessRight.diagram_id == Diagram.id",
        back_populates="access_rights",
    )
    user = relationship(
        "User",
        primaryjoin="AccessRight.user_id == User.id",
    )
