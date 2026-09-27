import pytest

from btcopilot.schema import Event, from_dict


@pytest.mark.parametrize("field", ["relationshipTargets", "relationshipTriangles"])
def test_a_list_field_refuses_null(field):
    # R-0453
    with pytest.raises(ValueError, match=f"Event.{field} is a list and cannot be null"):
        from_dict(Event, {"id": 1, "kind": "shift", field: None})


def test_a_missing_list_field_is_empty():
    # R-0453
    event = from_dict(Event, {"id": 1, "kind": "shift", "relationshipTargets": [2]})
    assert event.relationshipTargets == [2]
    assert event.relationshipTriangles == []
