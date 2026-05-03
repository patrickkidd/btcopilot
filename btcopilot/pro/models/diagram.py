import pickle
import re

from flask import g
from sqlalchemy import Column, Boolean, String, Integer, LargeBinary, ForeignKey
from sqlalchemy import update as sql_update
from sqlalchemy.orm import relationship
from dataclasses import fields as dc_fields


import btcopilot
from btcopilot.schema import DiagramData, PDP, from_dict
from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin
from btcopilot.pro.safe_pickle import safe_loads_diagram


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

    access_rights = relationship(
        "AccessRight",
        primaryjoin="Diagram.id == AccessRight.diagram_id",
        back_populates="diagram",
    )

    discussions = relationship("Discussion", back_populates="diagram")

    def get_diagram_data(self) -> DiagramData:
        import PyQt5.sip  # Required for unpickling QtCore objects

        data = safe_loads_diagram(self.data) if self.data else {}
        pdp_dict = data.get("pdp", {})
        known = {f.name for f in dc_fields(DiagramData)} - {"pdp"}
        kwargs = {k: data[k] for k in known if k in data}
        kwargs["pdp"] = from_dict(PDP, pdp_dict) if pdp_dict else PDP()
        return DiagramData(**kwargs)

    def set_diagram_data(self, diagram_data: DiagramData):
        import PyQt5.sip  # Required for pickling QtCore objects
        from btcopilot.schema import asdict

        data = safe_loads_diagram(self.data) if self.data else {}

        # Convert PDP dataclass to dict before pickling (JSON-compatible)
        data["pdp"] = asdict(diagram_data.pdp)
        data["lastItemId"] = diagram_data.lastItemId

        data["people"] = diagram_data.people
        data["events"] = diagram_data.events
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

    def reserve_id_block(self, count: int, max_retries: int = 32) -> tuple[int, int, int]:
        """
        Atomically reserve `count` ids in the diagram's lastItemId space.

        Returns (start, end, new_version) where ids in [start, end] inclusive
        are reserved for the caller. Bumps `lastItemId` in the pickled blob
        and the row's `version`.

        Concurrency: uses SELECT FOR UPDATE row lock (works on PostgreSQL)
        plus optimistic locking on `version` as a backstop. The
        `with_for_update()` SELECT acquires the row lock; subsequent
        readers from other transactions block until our COMMIT.
        SQLite doesn't honor FOR UPDATE so the optimistic check
        (`WHERE version=N`) is the actual serializer there.

        Used by the Pro app's ServerBlockAllocator to prevent client-side
        id collisions across concurrent writers (see
        2026-05-01--mvp-merge-fix). Personal app does NOT call this — it
        allocates server-side via commit_pdp_items.
        """
        if count <= 0:
            raise ValueError(f"count must be > 0, got {count}")

        import PyQt5.sip  # noqa: F401  side-effect: registers QtCore unpickle types

        for _ in range(max_retries):
            db.session.expire(self)
            # Acquire row lock (PostgreSQL); on SQLite this is a no-op but
            # the optimistic version check below is the real serializer.
            locked = (
                db.session.query(Diagram)
                .filter(Diagram.id == self.id)
                .with_for_update()
                .one()
            )
            expected_version = locked.version
            if not locked.data:
                data = {}
            else:
                data = pickle.loads(locked.data)
            last_id = int(data.get("lastItemId", 0) or 0)
            start = last_id + 1
            end = last_id + count
            data["lastItemId"] = end

            new_data = pickle.dumps(data)
            stmt = (
                sql_update(Diagram)
                .where(Diagram.id == self.id)
                .where(Diagram.version == expected_version)
                .values(data=new_data, version=Diagram.version + 1)
            )
            result = db.session.execute(stmt)
            if result.rowcount == 1:
                db.session.commit()
                db.session.expire(self)
                db.session.refresh(self)
                return (start, end, self.version)
            # rowcount==0 means another writer bumped version. Roll back
            # this transaction and retry from a fresh read.
            db.session.rollback()

        raise RuntimeError(
            f"reserve_id_block failed for diagram {self.id} after "
            f"{max_retries} retries (concurrent contention)"
        )

    def update_with_version_check(
        self, expected_version, new_data=None, diagram_data=None
    ):
        if new_data is not None:
            data_to_save = new_data
        elif diagram_data is not None:
            import PyQt5.sip
            from btcopilot.schema import asdict

            data = safe_loads_diagram(self.data) if self.data else {}
            data["pdp"] = asdict(diagram_data.pdp)
            data["lastItemId"] = diagram_data.lastItemId
            data["people"] = diagram_data.people
            data["events"] = diagram_data.events
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
        if include is None:
            include = ["user", "access_rights", "saved_at"]
        if update is None:
            update = {}
        if exclude is None:
            exclude = []
        elif isinstance(exclude, str):
            exclude = [exclude]
        else:
            exclude = list(exclude)
        for field in FIELD_MIN_VERSIONS:
            if not clientSupportsField(field):
                exclude.append(field)

        return super().as_dict(update=update, include=include, exclude=exclude)
