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
    # who this user is on the case: the id of a person in the diagram, or None
    # for someone who is not in the family, such as a human coach consulting
    person_id = Column(Integer, nullable=True)

    diagram = relationship(
        "Diagram",
        primaryjoin="AccessRight.diagram_id == Diagram.id",
        back_populates="access_rights",
    )
    user = relationship(
        "User",
        primaryjoin="AccessRight.user_id == User.id",
    )
