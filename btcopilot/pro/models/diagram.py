import pickle
from dataclasses import asdict

from sqlalchemy import Column, Boolean, String, Integer, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship

import vedana
import btcopilot.schema
from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


class Diagram(db.Model, ModelMixin):
    """A user's diagram file."""

    __tablename__ = "diagrams"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship(
        "User", primaryjoin="Diagram.user_id == User.id", back_populates="diagrams"
    )

    name = Column(String)
    alias = Column(String)
    use_real_names = Column(Boolean)
    require_password_for_real_names = Column(Boolean)

    data = Column(LargeBinary)
    name = Column(String)

    access_rights = relationship(
        "AccessRight",
        primaryjoin="Diagram.id == AccessRight.diagram_id",
        back_populates="diagram",
    )

    discussions = relationship("Discussion", back_populates="diagram")

    def get_dataclass(self) -> "btcopilot.schema.Diagram":
        from btcopilot.schema import Diagram

        return Diagram(**self.data)

    def set_dataclass(self, diagram: "btcopilot.schema.Diagram"):
        self.data = asdict(diagram)

    def grant_access(self, user, right, _commit=False):
        from btcopilot.pro.models import AccessRight

        AccessRight.query.filter_by(diagram_id=self.id, user_id=user.id).delete()
        access_right = AccessRight(diagram_id=self.id, user_id=user.id, right=right)
        db.session.add(access_right)
        if _commit:
            db.session.commit()

    def check_write_access(self, user):
        from btcopilot.pro.models import AccessRight

        if user.id == self.user_id:
            return True
        for access_right in AccessRight.query.filter_by(
            diagram_id=self.id, user_id=user.id
        ):
            if access_right.right == vedana.ACCESS_READ_WRITE:
                return True
        return False

    def check_read_access(self, user):
        from btcopilot.pro.models import AccessRight

        if user.id == self.user_id:
            return True
        for access_right in AccessRight.query.filter_by(
            diagram_id=self.id, user_id=user.id
        ):
            if access_right.right in (
                vedana.ACCESS_READ_ONLY,
                vedana.ACCESS_READ_WRITE,
            ):
                return True
        return False

    def saved_at(self):
        return self.updated_at if self.updated_at else self.created_at

    def as_dict(self, update={}, include=[], exclude=[]):
        if not include:
            include = ["user", "access_rights", "saved_at"]
        return super().as_dict(update=update, include=include, exclude=exclude)
