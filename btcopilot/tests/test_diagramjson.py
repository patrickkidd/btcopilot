import json
import pickle

import pytest

from btcopilot import diagramjson
from btcopilot.schema import DiagramData

FIXTURES = [
    "/Users/patrick/theapp/familydiagram/pkdiagram/tests/scene/data/UP_TO_2.0.12b1.fd/diagram.pickle",
    "/Users/patrick/theapp/familydiagram/pkdiagram/resources/Legend-Scene.fd/diagram.pickle",
    "/Users/patrick/theapp/familydiagram/pkdiagram/tests/data/stale-refs.fd/diagram.pickle",
]


def _load(path):
    with open(path, "rb") as f:
        return pickle.load(f)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.split("/")[-2])
def test_roundtrip_through_wire_json(path):
    data = _load(path)
    wire = json.loads(json.dumps(diagramjson.to_json(data), allow_nan=False))
    back = diagramjson.from_json(wire)
    for field in DiagramData.SCENE_COLLECTION_FIELDS:
        by_id = {c["id"]: c for c in data.get(field, []) if isinstance(c, dict)}
        back_by_id = {c["id"]: c for c in back.get(field, []) if isinstance(c, dict)}
        assert by_id.keys() == back_by_id.keys(), field
        for id, chunk in by_id.items():
            assert chunk == back_by_id[id], f"{field}[{id}]"
    assert back == data
    assert diagramjson.to_json(back) == wire


def test_encode_rejects_unknown_type():
    with pytest.raises(TypeError):
        diagramjson.to_json({"x": object()})


def test_dict_carrying_the_tag_key_survives():
    data = {"a": {diagramjson.TAG: 1, "b": 2}, "c": {3: "x"}}
    assert diagramjson.from_json(diagramjson.to_json(data)) == data
