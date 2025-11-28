import pickle
import re

from flask import g
from sqlalchemy import Column, Boolean, String, Integer, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship

import btcopilot
from btcopilot.schema import DiagramData
from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin


# TODO: Remove once pro version adoption gets past 2.1.11
# Minimum client versions that support specific fields.
# Fields not in this dict are always included.
# Fields with version None are always excluded (obsolete fields).
FIELD_MIN_VERSIONS = {
    "version": "2.1.11",
    "database": None,  # obsolete, remove from all responses
}


def parseVersion(text: str) -> tuple[int, int, int]:
    if not text:
        return (0, 0, 0)
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def clientSupportsField(field: str) -> bool:
    if field not in FIELD_MIN_VERSIONS:
        return True  # Field not version-gated, always include

    minVersion = FIELD_MIN_VERSIONS[field]
    if minVersion is None:
        return False  # None means always exclude (obsolete field)

    # Personal app sets this flag - always include versioned fields
    if getattr(g, "fd_include_all_fields", False):
        return True

    clientVersion = getattr(g, "fd_client_version", None)
    if not clientVersion:
        return False

    clientParsed = parseVersion(clientVersion)
    minParsed = parseVersion(minVersion)
    return clientParsed >= minParsed


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
    version = Column(Integer, nullable=False, default=1)

    access_rights = relationship(
        "AccessRight",
        primaryjoin="Diagram.id == AccessRight.diagram_id",
        back_populates="diagram",
    )

    discussions = relationship("Discussion", back_populates="diagram")

    def get_diagram_data(self) -> DiagramData:
        import PyQt5.sip  # Required for unpickling QtCore objects
        from btcopilot.schema import DiagramData, PDP, from_dict

        data = pickle.loads(self.data) if self.data else {}

        # Return outer people/events/pair_bonds as raw dicts (READ-ONLY, may contain QtCore objects)
        people = data.get("people", [])
        events = data.get("events", [])
        pair_bonds = data.get("pair_bonds", [])

        # Convert PDP dict to dataclass
        pdp_dict = data.get("pdp", {})
        pdp = from_dict(PDP, pdp_dict) if pdp_dict else PDP()

        return DiagramData(
            people=people,
            events=events,
            pair_bonds=pair_bonds,
            pdp=pdp,
            lastItemId=data.get("lastItemId", 0),
        )

    def set_diagram_data(self, diagram_data: DiagramData):
        import PyQt5.sip  # Required for pickling QtCore objects
        from btcopilot.schema import asdict

        data = pickle.loads(self.data) if self.data else {}

        # Convert PDP dataclass to dict before pickling (JSON-compatible)
        data["pdp"] = asdict(diagram_data.pdp)
        data["lastItemId"] = diagram_data.lastItemId

        # Write outer people/events/pair_bonds as raw dicts (if provided)
        # Pro app: btcopilot never modifies these (FD manages them)
        # Personal app: btcopilot may write to these after commits
        if diagram_data.people:
            data["people"] = diagram_data.people
        if diagram_data.events:
            data["events"] = diagram_data.events
        if diagram_data.pair_bonds:
            data["pair_bonds"] = diagram_data.pair_bonds

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
            if access_right.right == btcopilot.ACCESS_READ_WRITE:
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
                btcopilot.ACCESS_READ_ONLY,
                btcopilot.ACCESS_READ_WRITE,
            ):
                return True
        return False

    def saved_at(self):
        return self.updated_at if self.updated_at else self.created_at

    def update_with_version_check(
        self, expected_version, new_data=None, diagram_data=None
    ):
        """Update diagram with optimistic locking using atomic database operation.

        Args:
            expected_version: The version the client thinks is current
            new_data: Raw pickled data (for Pro app)
            diagram_data: DiagramData object (for Personal app)

        Returns:
            (True, new_version) on success, (False, None) on version conflict
        """
        from sqlalchemy import update as sql_update

        if new_data is not None:
            data_to_save = new_data
        elif diagram_data is not None:
            import PyQt5.sip
            from btcopilot.schema import asdict

            data = pickle.loads(self.data) if self.data else {}
            data["pdp"] = asdict(diagram_data.pdp)
            data["lastItemId"] = diagram_data.lastItemId
            if diagram_data.people:
                data["people"] = diagram_data.people
            if diagram_data.events:
                data["events"] = diagram_data.events
            if diagram_data.pair_bonds:
                data["pair_bonds"] = diagram_data.pair_bonds
            data_to_save = pickle.dumps(data)
        else:
            return (False, None)

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

    def as_dict(self, update=None, include=None, exclude=None):
        if not include:
            include = ["user", "access_rights", "saved_at"]
        if update is None:
            update = {}
        if exclude is None:
            exclude = []

        # Backward compatibility: exclude fields unsupported by client
        exclude = list(exclude)
        for field in FIELD_MIN_VERSIONS:
            if not clientSupportsField(field):
                exclude.append(field)

        return super().as_dict(update=update, include=include, exclude=exclude)
