import pickle

from sqlalchemy import Column, Boolean, String, Integer, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship

import vedana
from btcopilot.schema import DiagramData
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

    def get_diagram_data(self) -> DiagramData:
        import PyQt5.sip
        from btcopilot.schema import DiagramData

        data = pickle.loads(self.data) if self.data else {}
        return DiagramData(
            people=data.get("people", []),
            events=data.get("events", []),
            pdp=data.get("pdp", {}),
            last_id=data.get("last_id", 0),
        )

    def set_diagram_data(self, diagram_data: DiagramData):
        import PyQt5.sip

        data = pickle.loads(self.data) if self.data else {}
        data["people"] = diagram_data.people
        data["events"] = diagram_data.events
        data["pdp"] = diagram_data.pdp
        data["last_id"] = diagram_data.last_id
        self.data = pickle.dumps(data)

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
