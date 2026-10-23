from sqlalchemy import Column, Boolean, String, Integer, LargeBinary, ForeignKey, false
from sqlalchemy import event
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session, relationship
from dataclasses import fields as dc_fields


import btcopilot
from btcopilot import diagramjson
from btcopilot.schema import DiagramData, PDP, asdict, from_dict
from btcopilot.extensions import db
from btcopilot.models.etc import AccessRight
from btcopilot.modelmixin import ModelMixin

# grant_access keeps the person a user already is on the case unless told
KEEP = object()


def owner_row(user_id: int, person_id: int | None) -> AccessRight:
    """The owner's row on a diagram being made, written by whoever makes it:
    the person they are in it, or no one for a human coach (FD-387)."""
    return AccessRight(
        user_id=user_id, right=btcopilot.ACCESS_READ_WRITE, person_id=person_id
    )


def diagram_data(data: dict) -> DiagramData:
    pdp_dict = data.get("pdp", {})
    known = {f.name for f in dc_fields(DiagramData)} - {"pdp"}
    kwargs = {k: data[k] for k in known if k in data}
    kwargs["pdp"] = from_dict(PDP, pdp_dict) if pdp_dict else PDP()
    return DiagramData(**kwargs)


class Diagram(db.Model, ModelMixin):
    """A user's diagram file."""

    __tablename__ = "diagrams"

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
    # out of date apart from the change-date check until a Refresh writes the
    # cards, set by the FD-381 catch-up (R-0772)
    case_report_forced_out_of_date = Column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    access_rights = relationship(
        "AccessRight",
        primaryjoin="Diagram.id == AccessRight.diagram_id",
        back_populates="diagram",
        # every diagram has its owner's row, so a diagram deleted takes its rows
        cascade="all, delete-orphan",
    )

    discussions = relationship("Discussion", back_populates="diagram")

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

    def grant_access(self, user, right, _commit=False, person_id=KEEP):
        """The user's one row on the case with this right. `person_id` is who
        they are on the case; left out, the person their row already names."""
        if person_id is KEEP:
            had = self.access_right(user)
            person_id = had.person_id if had is not None else None
        self.revoke_access(user)
        self.access_rights.append(
            AccessRight(user_id=user.id, right=right, person_id=person_id)
        )
        if _commit:
            db.session.commit()

    def revoke_access(self, user):
        """Take the user's rows off the case, through the case's own list of
        them so that list never names a row that is gone."""
        for row in [r for r in self.access_rights if r.user_id == user.id]:
            self.access_rights.remove(row)

    def access_right(self, user) -> AccessRight | None:
        """The user's row on the case, or None."""
        return AccessRight.query.filter_by(diagram_id=self.id, user_id=user.id).first()

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


@event.listens_for(Session, "before_flush")
def _owner_rows(session, flush_context, instances):
    """Every user on a case has a row, the owner included: read-write, on the
    primary person, or on no one while the diagram has none."""
    for diagram in [d for d in session.new if isinstance(d, Diagram)]:
        primary = diagram_data(diagramjson.loads(diagram.data)).primary_person()
        person_id = primary["id"] if primary else None
        # an owner row the caller wrote is kept as written: an empty person
        # there is a human coach, never a person still to fill in
        had = [
            r
            for r in diagram.access_rights
            if (r.user_id is not None and r.user_id == diagram.user_id)
            or (r.user is not None and r.user is diagram.user)
        ]
        if had:
            continue
        row = AccessRight(
            user_id=diagram.user_id,
            right=btcopilot.ACCESS_READ_WRITE,
            person_id=person_id,
        )
        # a diagram made with its owner as an object has no user_id until now
        if diagram.user is not None:
            row.user = diagram.user
        diagram.access_rights.append(row)
