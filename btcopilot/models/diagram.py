import secrets

from sqlalchemy import Column, Boolean, String, Integer, LargeBinary, ForeignKey, false
from sqlalchemy import update as sql_update
from sqlalchemy.orm import relationship
from dataclasses import fields as dc_fields


import btcopilot
from btcopilot import diagramjson
from btcopilot.schema import DiagramData, PDP, asdict, from_dict
from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin

# What a diagram's public id is made of: letters and digits that cannot be
# mistaken for one another when read aloud (no 0 and o, no 1, l and i).
PUBLIC_ID_LETTERS = "abcdefghjkmnpqrstuvwxyz23456789"
PUBLIC_ID_LENGTH = 10


def new_public_id() -> str:
    """The id a diagram is named by in every address and every read of the
    page: short, random and opaque, never its row number."""
    return "".join(secrets.choice(PUBLIC_ID_LETTERS) for _ in range(PUBLIC_ID_LENGTH))


def diagram_data(data: dict) -> DiagramData:
    pdp_dict = data.get("pdp", {})
    known = {f.name for f in dc_fields(DiagramData)} - {"pdp"}
    kwargs = {k: data[k] for k in known if k in data}
    kwargs["pdp"] = from_dict(PDP, pdp_dict) if pdp_dict else PDP()
    return DiagramData(**kwargs)


class Diagram(db.Model, ModelMixin):
    """A user's diagram file."""

    __tablename__ = "diagrams"

    # the id the address bar and the page's reads name the diagram by; the row
    # number never leaves the server
    public_id = Column(
        String(12), nullable=False, unique=True, index=True, default=new_public_id
    )

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user = relationship(
        "User", primaryjoin="Diagram.user_id == User.id", back_populates="diagrams"
    )

    name = Column(String)
    alias = Column(String)
    use_real_names = Column(Boolean)
    require_password_for_real_names = Column(Boolean)

    data = Column(LargeBinary)
    version = Column(Integer, nullable=False, default=1)
    # a copy a shadow turn writes on and throws away; never listed to anyone
    scratch = Column(Boolean, nullable=False, default=False, server_default=false())

    access_rights = relationship(
        "AccessRight",
        primaryjoin="Diagram.id == AccessRight.diagram_id",
        back_populates="diagram",
    )

    discussions = relationship("Discussion", back_populates="diagram")

    @classmethod
    def by_public_id(cls, key: str | None) -> "Diagram | None":
        """The diagram an address or a read names, or None for a key no
        diagram has."""
        if not key:
            return None
        return cls.query.filter_by(public_id=key).one_or_none()

    def get_diagram_data(self) -> DiagramData:
        return diagram_data(diagramjson.loads(self.data))

    def set_diagram_data(self, diagram_data: DiagramData):
        data = diagramjson.loads(self.data)

        data["pdp"] = asdict(diagram_data.pdp)
        data["lastItemId"] = diagram_data.lastItemId

        data["people"] = diagram_data.people
        data["events"] = diagram_data.events
        data["pair_bonds"] = diagram_data.pair_bonds
        data["clusters"] = diagram_data.clusters
        data["clusterCacheKey"] = diagram_data.clusterCacheKey

        self.data = diagramjson.encode(data, self.data)

    def grant_access(self, user, right, _commit=False):
        from btcopilot.models import AccessRight

        AccessRight.query.filter_by(diagram_id=self.id, user_id=user.id).delete()
        access_right = AccessRight(diagram_id=self.id, user_id=user.id, right=right)
        db.session.add(access_right)
        if _commit:
            db.session.commit()

    def check_write_access(self, user):
        from btcopilot.models import AccessRight

        if user.id == self.user_id:
            return True
        for access_right in AccessRight.query.filter_by(
            diagram_id=self.id, user_id=user.id
        ):
            if access_right.right == btcopilot.ACCESS_READ_WRITE:
                return True
        return False

    def check_read_access(self, user):
        from btcopilot.models import AccessRight

        if user.id == self.user_id:
            return True
        for access_right in AccessRight.query.filter_by(
            diagram_id=self.id, user_id=user.id
        ):
            if access_right.right in (
                btcopilot.ACCESS_READ_ONLY,
                btcopilot.ACCESS_READ_WRITE,
            ):
                return True
        return False

    def saved_at(self):
        return self.updated_at if self.updated_at else self.created_at

    def update_with_version_check(self, expected_version, diagram_data):
        data = diagramjson.loads(self.data)
        data["pdp"] = asdict(diagram_data.pdp)
        data["lastItemId"] = diagram_data.lastItemId
        data["people"] = diagram_data.people
        data["events"] = diagram_data.events
        data["pair_bonds"] = diagram_data.pair_bonds
        data_to_save = diagramjson.encode(data, self.data)

        stmt = (
            sql_update(Diagram)
            .where(Diagram.id == self.id)
            .values(data=data_to_save, version=Diagram.version + 1)
        )

        if expected_version is not None:
            stmt = stmt.where(Diagram.version == expected_version)

        result = db.session.execute(stmt)

        if result.rowcount == 0:
            return (False, None)

        db.session.flush()
        db.session.refresh(self)
        return (True, self.version)
