"""Small fictional desktop .fd bundles, pickled without Qt: each Qt value is
written through sip's _unpickle_type, the way the desktop app writes it."""

import pickle
from pathlib import Path

from btcopilot.fdfile import PICKLE


def _unpickle_type(module, name, args):
    raise AssertionError("only ever written, never called")


OURS = f"c{__name__}\n_unpickle_type\n".encode()
SIP = b"csip\n_unpickle_type\n"


class Qt:
    def __init__(self, name: str, *args, module: str = "PyQt5.QtCore"):
        self.module, self.name, self.args = module, name, args

    def __reduce__(self):
        return _unpickle_type, (self.module, self.name, self.args)


def when(y, m, d) -> Qt:
    return Qt("QDateTime", y, m, d, 0, 0, 0, 0, 0)


def dumps(data: dict) -> bytes:
    return pickle.dumps(data, protocol=3).replace(OURS, SIP)


def bundle(folder: Path, data: dict, name: str = "Lund family.fd") -> Path:
    path = folder / name
    path.mkdir()
    (path / PICKLE).write_bytes(dumps(data))
    return path


def person(id, name, gender, **more) -> dict:
    return {
        "kind": "Person",
        "id": id,
        "name": name,
        "lastName": "Lund",
        "gender": gender,
        "primary": False,
        "itemPos": Qt("QPointF", 10.0, 20.0),
        "color": Qt("QColor", 255, 0, 0, 255, module="PyQt5.QtGui"),
        "size": 5,
        "tags": [],
        **more,
    }


def event(id, kind, **more) -> dict:
    return {
        "kind": kind,
        "id": id,
        "person": None,
        "spouse": None,
        "child": None,
        "description": "",
        "notes": "",
        "location": "",
        "dateTime": None,
        "endDateTime": None,
        "unsure": False,
        "dateCertainty": None,
        "nodal": False,
        "symptom": None,
        "anxiety": None,
        "functioning": None,
        "relationship": None,
        "relationshipTargets": [],
        "relationshipTriangles": [],
        "relationshipIntensity": 3,
        "dynamicProperties": {},
        "includeOnDiagram": True,
        "color": None,
        "tags": [],
        **more,
    }


def scene(**more) -> dict:
    """Ada and Bo Lund, married, with a son Cy: a family the record's rules
    accept as it stands."""
    return {
        "version": "2.1.23b2",
        "versionCompat": "1.3.0",
        "name": "",
        "tags": ["family", "work"],
        "lastItemId": 40,
        "people": [
            person(
                1,
                "Ada",
                "female",
                primary=True,
                alias="Mara",
                nickName="Addie",
                middleName="Jo",
                birthName="Berg",
                notes="Eldest of four.",
            ),
            person(2, "Bo", "male"),
            person(3, "Cy", "male", parents=10),
        ],
        "pair_bonds": [
            {
                "kind": "Marriage",
                "id": 10,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "itemPos": Qt("QPointF", 0.0, 0.0),
            }
        ],
        "events": [
            event(20, "birth", child=3, person=1, spouse=2, dateTime=when(1990, 5, 11), nodal=True, tags=["family"]),
            event(21, "married", person=1, spouse=2, dateTime=when(1985, 6, 1), unsure=True),
            event(22, "death", person=2, dateTime=when(2010, 1, 2), dateCertainty="approximate"),
        ],
        "emotions": [],
        "layers": [{"kind": "Layer", "id": 30, "name": "Work"}],
        "layerItems": [],
        "multipleBirths": [],
        "items": [],
        "pruned": [],
        "centerPoint": Qt("QPointF", 0.0, 0.0),
        "currentDateTime": when(2020, 1, 1),
        "loggedDate": Qt("QDate", 2020, 1, 1),
        "search_dateStart": Qt("QDate", 0, 0, 0),
        "pencilColor": Qt("QColor", 0, 0, 0, 255, module="PyQt5.QtGui"),
        "legendSize": Qt("QSize", 100, 50),
        "hideNames": False,
        **more,
    }


def shift(id, **more) -> dict:
    return event(id, "shift", person=1, description="Lost the job", dateTime=when(2000, 3, 4), **more)
