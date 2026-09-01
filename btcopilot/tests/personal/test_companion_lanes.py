from btcopilot.companion.lanes import lanes_diagram_data
from btcopilot.companion.timeline import build_timeline
from btcopilot.schema import DateCertainty, EventKind, RelationshipKind

LANES_DOC = {
    "entries": [
        {"t": 1996.5, "t_end": None, "certainty": "year", "who": "Owner",
         "others": [], "desc": "insomnia onset", "variable": "symptom",
         "direction": "up", "ongoing": True},
        {"t": 2005.2, "t_end": None, "certainty": "day", "who": "Owner",
         "others": [], "desc": "slept badly", "variable": "symptom",
         "direction": "up", "ongoing": False},
        {"t": 2010.5, "t_end": None, "certainty": "month", "who": "Owner",
         "others": [], "desc": "sleep eased", "variable": "symptom",
         "direction": "down", "ongoing": False},
        {"t": 2011.0, "t_end": None, "certainty": "day", "who": "Owner",
         "others": [], "desc": "sleep unchanged while traveling",
         "variable": "symptom", "direction": None, "ongoing": False},
        {"t": None, "t_end": None, "certainty": "unknown", "who": "Rita",
         "others": [], "desc": "insomnia managed with medication",
         "variable": "symptom", "direction": None, "ongoing": True},
        {"t": 2004.0, "t_end": None, "certainty": "year", "who": "Owner",
         "others": ["Mara"], "desc": "chronic arguing began",
         "variable": "relationship", "direction": "down", "ongoing": True},
        {"t": 2015.0, "t_end": None, "certainty": "year", "who": "Bobby (dad)",
         "others": [], "desc": "retired well", "variable": "functioning",
         "direction": "up", "ongoing": False},
    ],
    "structure": [
        {"fact": "mother of owner", "people": ["Mara", "Owner"], "t": None},
        {"fact": "owner born", "people": ["Owner"], "t": 1980.33},
        {"fact": "owner married", "people": ["Owner", "Wren"], "t": 2020.21},
        {"fact": "parents separated", "people": ["Mara", "Bobby (dad)"], "t": 1990.3},
        {"fact": "maternal grandmother died", "people": ["Gran"], "t": 2011.0},
    ],
    "notes": "chat polarity",
}

JOURNAL_DOC = {
    "entries": [
        {"t": 2025.5, "t_end": None, "certainty": "day", "who": "Owner",
         "others": ["Wren"], "desc": "mutual closeness on a trip",
         "variable": "relationship", "direction": "down", "ongoing": False},
    ],
    "notes": "polarity: symptom/anxiety/relationship up = more/worse",
}


def test_people_and_bonds_from_structure():
    data = lanes_diagram_data([LANES_DOC])
    names = {p["name"] for p in data.people}
    assert names == {"Owner", "Assistant", "Mara", "Wren", "Bobby (dad)", "Gran", "Rita"}
    primary = next(p for p in data.people if p.get("primary"))
    assert primary["name"] == "Owner"
    pairs = {
        frozenset((b["person_a"], b["person_b"])) for b in data.pair_bonds
    }
    by_name = {p["name"]: p["id"] for p in data.people}
    assert frozenset((by_name["Owner"], by_name["Wren"])) in pairs
    assert frozenset((by_name["Mara"], by_name["Bobby (dad)"])) in pairs


def test_certainty_grades_map_to_schema():
    data = lanes_diagram_data([LANES_DOC])
    by_desc = {e["description"]: e for e in data.events if e.get("description")}
    assert by_desc["insomnia onset"]["dateCertainty"] == DateCertainty.Approximate.value
    assert by_desc["slept badly"]["dateCertainty"] == DateCertainty.Certain.value
    assert by_desc["sleep eased"]["dateCertainty"] == DateCertainty.Certain.value
    undated = by_desc["insomnia managed with medication"]
    assert undated["dateTime"] is None
    assert undated["dateCertainty"] == DateCertainty.Unknown.value


def test_structure_events_created():
    data = lanes_diagram_data([LANES_DOC])
    kinds = [e["kind"] for e in data.events]
    assert EventKind.Birth.value in kinds
    assert EventKind.Married.value in kinds
    assert EventKind.Separated.value in kinds
    assert EventKind.Death.value in kinds


def test_same_direction_only_for_unchanged_descriptions():
    data = lanes_diagram_data([LANES_DOC])
    by_desc = {e["description"]: e for e in data.events if e.get("description")}
    assert by_desc["sleep unchanged while traveling"]["symptom"] == "same"
    assert by_desc["insomnia managed with medication"]["symptom"] is None


def test_relationship_polarity_normalized_per_doc():
    data = lanes_diagram_data([LANES_DOC, JOURNAL_DOC])
    by_desc = {e["description"]: e for e in data.events if e.get("description")}
    assert by_desc["chronic arguing began"]["relationship"] == (
        RelationshipKind.Conflict.value
    )
    # journal polarity: relationship down = closer, normalized to Toward
    assert by_desc["mutual closeness on a trip"]["relationship"] == (
        RelationshipKind.Toward.value
    )


def test_strip_prefers_primary_symptom_then_household():
    data = lanes_diagram_data([LANES_DOC, JOURNAL_DOC])
    timeline = build_timeline(data)
    strip = timeline["strip"]["lanes"]
    assert strip[0]["key"].endswith(":symptom")
    assert strip[0]["label"].startswith("Owner")
    assert strip[1]["key"].startswith("b")


def test_relationship_events_stamp_household_lane():
    data = lanes_diagram_data([LANES_DOC, JOURNAL_DOC])
    timeline = build_timeline(data)
    owner_wren = next(
        l for l in timeline["bond_lanes"] if "Wren" in l["label"]
    )
    sentences = [m["sentence"] for m in owner_wren["marks"]]
    assert any("Mutual closeness" in s for s in sentences)


def test_eras_split_on_long_silence():
    data = lanes_diagram_data([LANES_DOC, JOURNAL_DOC])
    timeline = build_timeline(data)
    eras = timeline["eras"]
    assert len(eras) >= 2
    assert sum(e["count"] for e in eras) > 0
    for a, b in zip(eras, eras[1:]):
        assert a["b"] < b["a"]
