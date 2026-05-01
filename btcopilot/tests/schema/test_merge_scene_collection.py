from btcopilot.schema import DiagramData


def test_identical_lists_returns_same_items():
    server = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
    local = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
    merged = DiagramData.merge_scene_collection(server, local)
    assert merged == server


def test_server_has_extra_items_keep_them():
    server = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
    local = [{"id": 1, "name": "A"}]
    merged = DiagramData.merge_scene_collection(server, local)
    ids = [item["id"] for item in merged]
    assert ids == [1, 2]


def test_local_has_extra_items_keep_them():
    server = [{"id": 1, "name": "A"}]
    local = [{"id": 1, "name": "A"}, {"id": 99, "name": "LocalNew"}]
    merged = DiagramData.merge_scene_collection(server, local)
    ids = [item["id"] for item in merged]
    assert ids == [1, 99]


def test_both_sides_have_extra_items_union_preserved():
    server = [{"id": 1}, {"id": 2}, {"id": 5}]
    local = [{"id": 1}, {"id": 3}]
    merged = DiagramData.merge_scene_collection(server, local)
    ids = sorted(item["id"] for item in merged)
    assert ids == [1, 2, 3, 5]


def test_id_conflict_local_wins():
    server = [{"id": 1, "name": "ServerVersion"}]
    local = [{"id": 1, "name": "LocalVersion"}]
    merged = DiagramData.merge_scene_collection(server, local)
    assert merged == [{"id": 1, "name": "LocalVersion"}]


def test_empty_server_list_returns_local():
    server = []
    local = [{"id": 1}, {"id": 2}]
    merged = DiagramData.merge_scene_collection(server, local)
    assert merged == local


def test_empty_local_list_returns_server():
    server = [{"id": 1}, {"id": 2}]
    local = []
    merged = DiagramData.merge_scene_collection(server, local)
    assert merged == server


def test_both_empty_returns_empty():
    assert DiagramData.merge_scene_collection([], []) == []


def test_server_order_preserved_local_only_appended():
    server = [{"id": 5}, {"id": 2}, {"id": 8}]
    local = [{"id": 5}, {"id": 99}, {"id": 2}]
    merged = DiagramData.merge_scene_collection(server, local)
    ids = [item["id"] for item in merged]
    assert ids == [5, 2, 8, 99]


def test_scene_collection_fields_constant_complete():
    expected = {
        "people",
        "events",
        "pair_bonds",
        "emotions",
        "multipleBirths",
        "layers",
        "layerItems",
        "items",
        "pruned",
    }
    assert set(DiagramData.SCENE_COLLECTION_FIELDS) == expected


def test_scene_collection_fields_match_dataclass_fields():
    """Every entry in SCENE_COLLECTION_FIELDS must be an actual DiagramData attribute."""
    dd = DiagramData()
    for fname in DiagramData.SCENE_COLLECTION_FIELDS:
        assert hasattr(dd, fname), f"{fname} not on DiagramData"
        assert isinstance(getattr(dd, fname), list), f"{fname} not a list"
