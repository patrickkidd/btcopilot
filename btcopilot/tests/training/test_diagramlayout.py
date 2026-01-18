"""
Tests for the family diagram layout algorithm.

Test cases from FAMILY_DIAGRAM_LAYOUT_ALGORITHM.md specification.
"""

from btcopilot.training.diagramlayout import (
    compute,
    arrangeSelection,
    PERSON_SPACING,
    GENERATION_GAP,
    BASE_X,
    BASE_Y,
    PERSON_SIZE,
)


def test_tc1_simple_nuclear_family():
    """TC-1: Simple Nuclear Family - Father, Mother, and one Child."""
    data = {
        "people": [
            {"id": 1, "name": "Father", "gender": "male", "parents": None},
            {"id": 2, "name": "Mother", "gender": "female", "parents": None},
            {"id": 3, "name": "Child", "gender": "male", "parents": 100},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            }
        ],
        "parent_child": [{"child_id": 3, "pair_bond_id": 100}],
    }

    layout = compute(data)

    assert 1 in layout["people"]
    assert 2 in layout["people"]
    assert 3 in layout["people"]

    father = layout["people"][1]
    mother = layout["people"][2]
    child = layout["people"][3]

    assert father["y"] == BASE_Y
    assert mother["y"] == BASE_Y
    assert child["y"] == BASE_Y + GENERATION_GAP

    assert abs(mother["x"] - father["x"]) == PERSON_SPACING
    assert child["x"] >= father["x"]
    assert child["x"] <= mother["x"]


def test_tc2_two_married_couples():
    """TC-2: Two Married Couples with no children."""
    data = {
        "people": [
            {"id": 1, "name": "M1", "gender": "male", "parents": None},
            {"id": 2, "name": "F1", "gender": "female", "parents": None},
            {"id": 3, "name": "M2", "gender": "male", "parents": None},
            {"id": 4, "name": "F2", "gender": "female", "parents": None},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            },
            {
                "id": 101,
                "person_a": 3,
                "person_b": 4,
                "married": True,
                "separated": False,
                "divorced": False,
            },
        ],
        "parent_child": [],
    }

    layout = compute(data)

    m1 = layout["people"][1]
    f1 = layout["people"][2]
    m2 = layout["people"][3]
    f2 = layout["people"][4]

    assert m1["y"] == f1["y"] == m2["y"] == f2["y"]
    assert abs(f1["x"] - m1["x"]) == PERSON_SPACING
    assert abs(f2["x"] - m2["x"]) == PERSON_SPACING


def test_inv1_no_collisions():
    """INV-1: No two people may occupy overlapping positions."""
    data = {
        "people": [
            {"id": 1, "name": "A", "gender": "male", "parents": None},
            {"id": 2, "name": "B", "gender": "female", "parents": None},
            {"id": 3, "name": "C", "gender": "male", "parents": 100},
            {"id": 4, "name": "D", "gender": "female", "parents": 100},
            {"id": 5, "name": "E", "gender": "male", "parents": 100},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            }
        ],
        "parent_child": [
            {"child_id": 3, "pair_bond_id": 100},
            {"child_id": 4, "pair_bond_id": 100},
            {"child_id": 5, "pair_bond_id": 100},
        ],
    }

    layout = compute(data)

    by_gen: dict[float, list[tuple[int, float]]] = {}
    for pid, pos in layout["people"].items():
        by_gen.setdefault(pos["y"], []).append((pid, pos["x"]))

    for y, people in by_gen.items():
        people_sorted = sorted(people, key=lambda x: x[1])
        for i in range(1, len(people_sorted)):
            prev_x = people_sorted[i - 1][1]
            curr_x = people_sorted[i][1]
            assert curr_x - prev_x >= PERSON_SPACING, f"Collision at y={y}"


def test_inv2_couple_adjacency():
    """INV-2: Partners must be adjacent with correct spacing."""
    data = {
        "people": [
            {"id": 1, "name": "Father", "gender": "male", "parents": None},
            {"id": 2, "name": "Mother", "gender": "female", "parents": None},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            }
        ],
        "parent_child": [],
    }

    layout = compute(data)

    father = layout["people"][1]
    mother = layout["people"][2]
    assert abs(mother["x"] - father["x"]) == PERSON_SPACING


def test_inv2_divorced_couple_spacing():
    """INV-2: Divorced couples get 1.5× spacing."""
    data = {
        "people": [
            {"id": 1, "name": "ExHusband", "gender": "male", "parents": None},
            {"id": 2, "name": "ExWife", "gender": "female", "parents": None},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": True,
            }
        ],
        "parent_child": [],
    }

    layout = compute(data)

    ex1 = layout["people"][1]
    ex2 = layout["people"][2]
    expected_spacing = int(PERSON_SPACING * 1.5)
    assert abs(ex2["x"] - ex1["x"]) == expected_spacing


def test_inv4_generation_alignment():
    """INV-4: All people in same generation have same Y coordinate."""
    data = {
        "people": [
            {"id": 1, "name": "GP1", "gender": "male", "parents": None},
            {"id": 2, "name": "GP2", "gender": "female", "parents": None},
            {"id": 3, "name": "Parent1", "gender": "male", "parents": 100},
            {"id": 4, "name": "Parent2", "gender": "female", "parents": None},
            {"id": 5, "name": "Child1", "gender": "male", "parents": 101},
            {"id": 6, "name": "Child2", "gender": "female", "parents": 101},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            },
            {
                "id": 101,
                "person_a": 3,
                "person_b": 4,
                "married": True,
                "separated": False,
                "divorced": False,
            },
        ],
        "parent_child": [
            {"child_id": 3, "pair_bond_id": 100},
            {"child_id": 5, "pair_bond_id": 101},
            {"child_id": 6, "pair_bond_id": 101},
        ],
    }

    layout = compute(data)

    gen0_y = layout["people"][1]["y"]
    gen1_y = layout["people"][3]["y"]
    gen2_y = layout["people"][5]["y"]

    assert layout["people"][2]["y"] == gen0_y
    assert layout["people"][4]["y"] == gen1_y
    assert layout["people"][6]["y"] == gen2_y
    assert gen1_y == gen0_y + GENERATION_GAP
    assert gen2_y == gen1_y + GENERATION_GAP


def test_complete_worked_example():
    """Complete worked example from spec: three-generation family."""
    data = {
        "people": [
            {"id": 1, "name": "Grandfather", "gender": "male", "parents": None},
            {"id": 2, "name": "Grandmother", "gender": "female", "parents": None},
            {"id": 3, "name": "Father", "gender": "male", "parents": 100},
            {"id": 4, "name": "Mother", "gender": "female", "parents": None},
            {"id": 5, "name": "Son", "gender": "male", "parents": 101},
            {"id": 6, "name": "Daughter", "gender": "female", "parents": 101},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            },
            {
                "id": 101,
                "person_a": 3,
                "person_b": 4,
                "married": True,
                "separated": False,
                "divorced": False,
            },
        ],
        "parent_child": [
            {"child_id": 3, "pair_bond_id": 100},
            {"child_id": 5, "pair_bond_id": 101},
            {"child_id": 6, "pair_bond_id": 101},
        ],
    }

    layout = compute(data)

    assert layout["people"][1]["y"] == 100
    assert layout["people"][2]["y"] == 100
    assert layout["people"][3]["y"] == 210
    assert layout["people"][4]["y"] == 210
    assert layout["people"][5]["y"] == 320
    assert layout["people"][6]["y"] == 320

    assert 100 in layout["pairBonds"]
    assert 101 in layout["pairBonds"]


def test_pairbond_positions():
    """Pair bond positions are calculated correctly."""
    data = {
        "people": [
            {"id": 1, "name": "Father", "gender": "male", "parents": None},
            {"id": 2, "name": "Mother", "gender": "female", "parents": None},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            }
        ],
        "parent_child": [],
    }

    layout = compute(data)

    pb = layout["pairBonds"][100]
    father = layout["people"][1]
    mother = layout["people"][2]

    assert pb["x1"] == min(father["x"], mother["x"])
    assert pb["x2"] == max(father["x"], mother["x"])
    assert pb["coupleX1"] == pb["x1"]
    assert pb["coupleX2"] == pb["x2"]
    assert pb["y"] > father["y"]


def test_unconnected_people():
    """Unconnected people are positioned on the perimeter."""
    data = {
        "people": [
            {"id": 1, "name": "Father", "gender": "male", "parents": None},
            {"id": 2, "name": "Mother", "gender": "female", "parents": None},
            {"id": 3, "name": "Child", "gender": "male", "parents": 100},
            {"id": 4, "name": "Loner", "gender": "male", "parents": None},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            }
        ],
        "parent_child": [{"child_id": 3, "pair_bond_id": 100}],
    }

    layout = compute(data)

    father = layout["people"][1]
    mother = layout["people"][2]
    loner = layout["people"][4]

    maxConnectedX = max(father["x"], mother["x"])
    assert loner["x"] > maxConnectedX


def test_male_left_convention():
    """Males are positioned on the left in couples (gender convention)."""
    data = {
        "people": [
            {"id": 1, "name": "Wife", "gender": "female", "parents": None},
            {"id": 2, "name": "Husband", "gender": "male", "parents": None},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            }
        ],
        "parent_child": [],
    }

    layout = compute(data)

    wife = layout["people"][1]
    husband = layout["people"][2]
    assert husband["x"] < wife["x"]


def test_empty_data():
    """Empty input returns empty layout."""
    data = {"people": [], "pair_bonds": [], "parent_child": []}

    layout = compute(data)

    assert layout["people"] == {}
    assert layout["pairBonds"] == {}


def test_single_person():
    """Single person with no relationships."""
    data = {
        "people": [{"id": 1, "name": "Solo", "gender": "male", "parents": None}],
        "pair_bonds": [],
        "parent_child": [],
    }

    layout = compute(data)

    assert 1 in layout["people"]
    assert layout["people"][1]["x"] == BASE_X
    assert layout["people"][1]["y"] == BASE_Y


def test_constrained_fixed_positions_preserved():
    """Fixed positions should be preserved exactly."""
    data = {
        "people": [
            {"id": 1, "name": "Fixed1", "gender": "male", "parents": None},
            {"id": 2, "name": "Fixed2", "gender": "female", "parents": None},
            {"id": 3, "name": "Movable", "gender": "male", "parents": 100},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            }
        ],
        "parent_child": [{"child_id": 3, "pair_bond_id": 100}],
    }

    constraints = {
        "fixed": {
            1: {"x": 500.0, "y": 200.0},
            2: {"x": 700.0, "y": 200.0},
        }
    }

    layout = compute(data, constraints)

    assert layout["people"][1]["x"] == 500.0
    assert layout["people"][1]["y"] == 200.0
    assert layout["people"][2]["x"] == 700.0
    assert layout["people"][2]["y"] == 200.0
    assert 3 in layout["people"]


def test_constrained_child_uses_parent_y():
    """Child's Y should be based on fixed parent's Y."""
    data = {
        "people": [
            {"id": 1, "name": "Father", "gender": "male", "parents": None},
            {"id": 2, "name": "Mother", "gender": "female", "parents": None},
            {"id": 3, "name": "Child", "gender": "male", "parents": 100},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            }
        ],
        "parent_child": [{"child_id": 3, "pair_bond_id": 100}],
    }

    constraints = {"fixed": {1: {"x": 0.0, "y": 0.0}, 2: {"x": 200.0, "y": 0.0}}}

    layout = compute(data, constraints)

    assert layout["people"][3]["y"] == GENERATION_GAP


def test_constrained_movable_positioned_after_fixed():
    """Movable people should be positioned after fixed people in same generation."""
    data = {
        "people": [
            {"id": 1, "name": "Fixed", "gender": "male", "parents": None},
            {"id": 2, "name": "Movable", "gender": "female", "parents": None},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            }
        ],
        "parent_child": [],
    }

    constraints = {"fixed": {1: {"x": 300.0, "y": 100.0}}}

    layout = compute(data, constraints)

    assert layout["people"][1]["x"] == 300.0
    assert layout["people"][2]["x"] > layout["people"][1]["x"]


def test_arrangeSelection_basic():
    """arrangeSelection returns new positions for movable people only."""
    diagram = {
        "people": [
            {
                "id": 1,
                "center": {"x": 0, "y": 0},
                "isMovable": False,
                "partners": [2],
                "parent_a": None,
                "parent_b": None,
            },
            {
                "id": 2,
                "center": {"x": 200, "y": 0},
                "isMovable": False,
                "partners": [1],
                "parent_a": None,
                "parent_b": None,
            },
            {
                "id": 3,
                "center": {"x": 500, "y": 500},
                "isMovable": True,
                "partners": [],
                "parent_a": 1,
                "parent_b": 2,
            },
        ]
    }

    result = arrangeSelection(diagram)

    assert len(result["people"]) == 1
    assert result["people"][0]["id"] == 3
    assert "center" in result["people"][0]
    assert result["people"][0]["center"]["y"] == GENERATION_GAP


def test_arrangeSelection_all_movable():
    """arrangeSelection with all people movable computes full layout."""
    diagram = {
        "people": [
            {
                "id": 1,
                "center": {"x": 500, "y": 500},
                "isMovable": True,
                "partners": [2],
                "parent_a": None,
                "parent_b": None,
            },
            {
                "id": 2,
                "center": {"x": 600, "y": 600},
                "isMovable": True,
                "partners": [1],
                "parent_a": None,
                "parent_b": None,
            },
        ]
    }

    result = arrangeSelection(diagram)

    assert len(result["people"]) == 2
    ids = [p["id"] for p in result["people"]]
    assert 1 in ids
    assert 2 in ids


def test_arrangeSelection_empty():
    """arrangeSelection with empty diagram returns empty result."""
    result = arrangeSelection({"people": []})
    assert result == {"people": []}


def test_multiple_marriages():
    """F-0005: Person with multiple marriages has both spouses positioned adjacently.

    George has two marriages: to Wife1 and to Wife2.
    Both spouses should be adjacent to George (one on each side).
    """
    data = {
        "people": [
            {"id": 1, "name": "George", "gender": "male", "parents": None},
            {"id": 2, "name": "Wife1", "gender": "female", "parents": None},
            {"id": 3, "name": "Wife2", "gender": "female", "parents": None},
        ],
        "pair_bonds": [
            {
                "id": 100,
                "person_a": 1,
                "person_b": 2,
                "married": True,
                "separated": False,
                "divorced": False,
            },
            {
                "id": 101,
                "person_a": 1,
                "person_b": 3,
                "married": True,
                "separated": False,
                "divorced": False,
            },
        ],
        "parent_child": [],
    }

    layout = compute(data)

    george = layout["people"][1]
    wife1 = layout["people"][2]
    wife2 = layout["people"][3]

    # All three should be in the same generation
    assert george["y"] == wife1["y"] == wife2["y"]

    # Both wives should be adjacent to George (PERSON_SPACING apart)
    george_wife1_gap = abs(george["x"] - wife1["x"])
    george_wife2_gap = abs(george["x"] - wife2["x"])

    assert george_wife1_gap == PERSON_SPACING
    assert george_wife2_gap == PERSON_SPACING

    # Wives should be on opposite sides of George
    if wife1["x"] > george["x"]:
        assert wife2["x"] < george["x"]
    else:
        assert wife2["x"] > george["x"]

    # INV-3: No one between George and either wife
    min_wife1_george = min(george["x"], wife1["x"])
    max_wife1_george = max(george["x"], wife1["x"])
    min_wife2_george = min(george["x"], wife2["x"])
    max_wife2_george = max(george["x"], wife2["x"])

    for pid, pos in layout["people"].items():
        if pid == 1:
            continue
        if pid == 2:
            assert not (min_wife2_george < pos["x"] < max_wife2_george)
        elif pid == 3:
            assert not (min_wife1_george < pos["x"] < max_wife1_george)
