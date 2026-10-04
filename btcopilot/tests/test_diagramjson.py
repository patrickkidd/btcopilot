import pytest

from btcopilot import diagramjson


def test_encode_rejects_unknown_type():
    # R-0453
    with pytest.raises(TypeError):
        diagramjson.to_json({"x": object()})


def test_dict_carrying_the_tag_key_survives():
    # R-0083
    data = {"a": {diagramjson.TAG: 1, "b": 2}, "c": {3: "x"}}
    assert diagramjson.from_json(diagramjson.to_json(data)) == data
