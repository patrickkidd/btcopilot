from sqlalchemy import Column, String, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Machine(db.Model, ModelMixin):
    __tablename__ = "machines"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", uselist=False, back_populates="machines")

    code = Column(String(36), unique=True, index=True, nullable=False)
    name = Column(String(255))

    activations = relationship("Activation", uselist=False, back_populates="machine")


class Activation(db.Model, ModelMixin):
    """One machine activated on a license."""

    __tablename__ = "activations"

    license_id = Column(Integer, ForeignKey("licenses.id"), nullable=False)
    license = relationship("License", uselist=False, back_populates="activations")

    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    machine = relationship("Machine", uselist=False, back_populates="activations")

    index = Index("index_activations", license_id, machine_id)

    def __str__(self):
        return "<Activation id: %i, Machine: %s, created: %s>" % (
            self.id,
            self.machine.name,
            self.created_at,
        )


class AccessRight(db.Model, ModelMixin):
    """Added as a list to control users' access to a diagram."""

    __tablename__ = "access_rights"

    diagram_id = Column(Integer, ForeignKey("diagrams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
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
