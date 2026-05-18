from PyQt5.QtCore import QDate, QDateTime

from btcopilot.personal.intake import (
    CoverageStatus,
    DataCategory,
    coverage,
    format_coverage_for_prompt,
    outstanding_categories,
    roster_for_prompt,
)
from btcopilot.schema import DiagramData


def _qdt(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return QDateTime(QDate(y, m, d))


def _diagram(people=None, pair_bonds=None, events=None):
    return DiagramData(
        people=people or [],
        pair_bonds=pair_bonds or [],
        events=events or [],
    )


def test_no_diagram_all_not_covered_except_presenting_problem():
    cov = coverage(None)
    for cat in DataCategory:
        if cat == DataCategory.PresentingProblem:
            assert cov[cat].status == CoverageStatus.Covered
        else:
            assert cov[cat].status == CoverageStatus.NotCovered


def test_empty_diagram_outstanding_excludes_presenting_problem():
    out = outstanding_categories(_diagram())
    cats = {c.category for c in out}
    assert DataCategory.PresentingProblem not in cats
    assert DataCategory.Mother in cats
    assert DataCategory.Father in cats


def test_full_picture():
    # Speaker (User=1, primary), parents Mary+John, siblings Sarah, maternal
    # grandparents Linda+Tom, paternal grandparents Anne+Bob, spouse Lisa,
    # child Emma, plus 3 nodal events.
    people = [
        {"id": 1, "name": "User", "primary": True, "parents": 100},
        {"id": 2, "name": "Mary", "gender": "female", "parents": 200},
        {"id": 3, "name": "John", "gender": "male", "parents": 300},
        {"id": 4, "name": "Sarah", "parents": 100},
        {"id": 5, "name": "Linda", "gender": "female"},
        {"id": 6, "name": "Tom", "gender": "male"},
        {"id": 7, "name": "Anne", "gender": "female"},
        {"id": 8, "name": "Bob", "gender": "male"},
        {"id": 9, "name": "Lisa", "gender": "female"},
        {"id": 10, "name": "Emma", "parents": 400},
        {"id": 11, "name": "Karen", "parents": 200},  # Mary's sister (aunt)
    ]
    pair_bonds = [
        {"id": 100, "person_a": 2, "person_b": 3},  # parents of user
        {"id": 200, "person_a": 5, "person_b": 6},  # maternal grandparents
        {"id": 300, "person_a": 7, "person_b": 8},  # paternal grandparents
        {"id": 400, "person_a": 1, "person_b": 9},  # user-spouse
    ]
    events = [
        {"id": 500, "kind": "married", "person": 2, "spouse": 3, "dateTime": "1980-01-01"},
        {"id": 501, "kind": "death", "person": 6, "dateTime": "2010-01-01"},
        {"id": 502, "kind": "moved", "person": 1, "dateTime": "2018-01-01"},
        # Shift events with SARF + dates near structural anchors
        {"id": 503, "kind": "shift", "person": 1, "symptom": "up", "dateTime": "2010-04-01"},
        {"id": 504, "kind": "shift", "person": 1, "symptom": "up", "dateTime": "2018-03-01"},
        {"id": 505, "kind": "shift", "person": 1, "relationship": "distance",
         "relationshipTargets": [3], "dateTime": "2018-06-01"},
        {"id": 506, "kind": "shift", "person": 1, "relationship": "conflict",
         "relationshipTargets": [3], "dateTime": "2018-09-01"},
    ]
    cov = coverage(_diagram(people, pair_bonds, events))
    assert cov[DataCategory.Mother].status == CoverageStatus.Covered
    assert cov[DataCategory.Mother].detail == "Mary"
    assert cov[DataCategory.Father].status == CoverageStatus.Covered
    assert cov[DataCategory.ParentsStatus].status == CoverageStatus.Covered
    assert cov[DataCategory.Siblings].status == CoverageStatus.Covered
    assert "Sarah" in cov[DataCategory.Siblings].detail
    assert cov[DataCategory.MaternalGrandparents].status == CoverageStatus.Covered
    assert cov[DataCategory.PaternalGrandparents].status == CoverageStatus.Covered
    assert cov[DataCategory.Spouse].status == CoverageStatus.Covered
    assert cov[DataCategory.Children].status == CoverageStatus.Covered
    assert cov[DataCategory.NodalEvents].status == CoverageStatus.Covered
    assert outstanding_categories(_diagram(people, pair_bonds, events)) == []


def test_partial_grandparents_when_parent_known_but_no_grandparent_bond():
    # Mother known but no maternal-grandparents PairBond → maternal GP not_covered
    people = [
        {"id": 1, "name": "User", "primary": True, "parents": 100},
        {"id": 2, "name": "Mary", "gender": "female"},
        {"id": 3, "name": "John", "gender": "male"},
    ]
    pair_bonds = [{"id": 100, "person_a": 2, "person_b": 3}]
    cov = coverage(_diagram(people, pair_bonds))
    assert cov[DataCategory.Mother].status == CoverageStatus.Covered
    assert cov[DataCategory.MaternalGrandparents].status == CoverageStatus.NotCovered


def test_functioning_coverage_thin_when_no_shift_events():
    people = [{"id": 1, "name": "User", "primary": True}]
    cov = coverage(_diagram(people))
    assert cov[DataCategory.FamilyFunctioning].status == CoverageStatus.NotCovered
    assert cov[DataCategory.RelationshipPatterns].status == CoverageStatus.NotCovered
    assert cov[DataCategory.SymptomTimeline].status == CoverageStatus.NotCovered
    assert cov[DataCategory.EventSymptomConnections].status == CoverageStatus.NotCovered


def test_functioning_coverage_rich_when_sarf_and_timeline_present():
    people = [{"id": 1, "name": "User", "primary": True}]
    events = [
        # Structural anchor
        {"id": 100, "kind": "death", "person": 99, "dateTime": "2019-01-01"},
        # Shift events with varied SARF coding, dated near the anchor
        {"id": 101, "kind": "shift", "person": 1, "symptom": "up", "dateTime": "2019-03-15"},
        {"id": 102, "kind": "shift", "person": 1, "symptom": "up", "dateTime": "2019-06-01"},
        {"id": 103, "kind": "shift", "person": 1, "relationship": "distance",
         "relationshipTargets": [99], "dateTime": "2019-08-01"},
        {"id": 104, "kind": "shift", "person": 1, "relationship": "conflict",
         "relationshipTargets": [99], "dateTime": "2020-01-01"},
    ]
    cov = coverage(_diagram(people, events=events))
    assert cov[DataCategory.FamilyFunctioning].status == CoverageStatus.Covered
    assert cov[DataCategory.RelationshipPatterns].status == CoverageStatus.Covered
    assert "distance" in cov[DataCategory.RelationshipPatterns].detail
    assert "conflict" in cov[DataCategory.RelationshipPatterns].detail
    assert cov[DataCategory.SymptomTimeline].status == CoverageStatus.Covered
    assert cov[DataCategory.EventSymptomConnections].status == CoverageStatus.Covered


def test_format_coverage_renders_known_and_outstanding():
    out = format_coverage_for_prompt(coverage(None))
    assert "Already known" not in out  # nothing known
    assert "Still outstanding" in out
    assert "mother" in out


def test_format_coverage_empty_when_only_presenting_problem():
    # All categories covered → empty/known-only prompt
    cov = {DataCategory.PresentingProblem: coverage(None)[DataCategory.PresentingProblem]}
    assert format_coverage_for_prompt(cov) == ""


def test_roster_lists_all_named_people_even_without_speaker_links():
    # Speaker (Marcus, id 1) has NO parents link and is not primary — coverage()
    # goes blank on the family, but the roster must still name everyone. This is
    # the FD-325 graceful-degradation contract: extraction connectivity is
    # imperfect; the coach still gets who is on file by name.
    people = [
        {"id": 1, "name": "Marcus", "gender": "male"},
        {"id": 2, "name": "Assistant", "gender": "male"},
        {"id": 3, "name": "William", "gender": "male"},
        {"id": 4, "name": "Dorothy", "gender": "female"},
        {"id": 5, "name": "Uncle Jim", "gender": "male"},
        {"id": 6, "name": "Lily's spouse", "gender": "None"},
        {"id": 7, "name": "Unknown"},
        {"id": 8, "name": "Jennifer", "gender": "female"},
    ]
    pair_bonds = [
        {"id": 100, "person_a": 3, "person_b": 4},   # William + Dorothy
        {"id": 101, "person_a": 1, "person_b": 8},   # Marcus + Jennifer
    ]
    events = [
        {"id": 200, "kind": "death", "person": 3, "dateTime": "2015-01-01"},
        {"id": 201, "kind": "birth", "child": 8, "dateTime": "1985-03-04"},
    ]
    out = roster_for_prompt(_diagram(people, pair_bonds, events))
    assert out.startswith("People on file:")
    for name in ("Marcus", "William", "Dorothy", "Uncle Jim", "Jennifer"):
        assert name in out
    assert "Assistant" not in out      # chat bot excluded
    assert "Unknown" not in out        # placeholder excluded
    assert "Lily's spouse" not in out  # structural stub excluded
    assert "Marcus (male) — the user" in out
    assert "William (male) — partner of Dorothy [d. 2015-01-01]" in out
    assert "Jennifer (female) — partner of the user [b. 1985-03-04]" in out
    # Coverage is blind here (no speaker links) — roster is the safety net.
    assert coverage(_diagram(people, pair_bonds))[DataCategory.Father].status == \
        CoverageStatus.NotCovered


def test_real_desktop_quirks_dont_crash():
    # Regression for two crashes found only on real desktop-synced diagrams
    # (synthetic fixtures missed both): a scene-stub person with name=None,
    # and a shift event whose `relationship` is a RelationshipKind enum object
    # (desktop stores the enum, not its string). coverage()/roster must not
    # raise and must not leak an enum repr into the prompt.
    from btcopilot.schema import RelationshipKind

    people = [
        {"id": 1, "name": "Marcus", "gender": "male", "primary": True},
        {"id": 2, "name": None, "gender": None, "kind": "Person"},  # scene stub
        {"id": 3, "name": "Dana", "gender": "female"},
    ]
    pair_bonds = [{"id": 50, "person_a": 1, "person_b": 3}]
    events = [
        {"id": 9, "kind": "shift", "person": 1,
         "relationship": RelationshipKind.Distance, "dateTime": "2020-01-01"},
        {"id": 10, "kind": "shift", "person": 1,
         "relationship": RelationshipKind.Conflict, "dateTime": "2020-06-01"},
    ]
    dd = _diagram(people, pair_bonds, events)
    roster = roster_for_prompt(dd)
    cov = coverage(dd)
    rendered = format_coverage_for_prompt(cov)
    assert "Marcus" in roster and "Dana" in roster
    assert "RelationshipKind" not in roster + rendered
    assert "distance" in rendered and "conflict" in rendered
    assert cov[DataCategory.RelationshipPatterns].status == CoverageStatus.Covered


def test_committed_scene_format_contract():
    """Regression: pins the real committed-data contract for the Personal app.

    Committed family data lives in DiagramData.people/events/pair_bonds (Scene
    collections), NOT DiagramData.pdp. pdp.extract_full writes the *pending*
    pool; commit_pdp_items() promotes items into the Scene collections and
    converts dates string→QDateTime, then clears .pdp. Desktop Scene.write()
    populates the same collections (marriages → pair_bonds with
    person_a/person_b; person.parents = a marriage id resolvable in
    pair_bonds) and adds keys intake.py must ignore (kind/marriages/itemPos/
    deceased/layers/detailsText). Dates are always QDateTime here, never ISO.

    A 1924-class regression (intake silently under-reporting on a real
    committed diagram) would fail this test. No linkage rewrite is required:
    the desktop and Personal-commit schemas converge on these collections.
    """
    people = [
        {"id": 1, "name": "User", "primary": True, "parents": 100,
         "kind": "Person", "marriages": [400], "gender": "male",
         "itemPos": [0.0, 0.0], "deceased": False, "layers": [],
         "detailsText": {}},
        {"id": 2, "name": "Mary", "gender": "female", "parents": 200,
         "kind": "Person", "marriages": [100], "itemPos": [10.0, 0.0]},
        {"id": 3, "name": "John", "gender": "male", "parents": 300,
         "kind": "Person", "marriages": [100], "deceased": True},
        {"id": 4, "name": "Sarah", "gender": "female", "parents": 100,
         "kind": "Person"},
        {"id": 5, "name": "Linda", "gender": "female", "kind": "Person"},
        {"id": 6, "name": "Tom", "gender": "male", "kind": "Person"},
        {"id": 7, "name": "Anne", "gender": "female", "kind": "Person"},
        {"id": 8, "name": "Bob", "gender": "male", "kind": "Person"},
        {"id": 9, "name": "Lisa", "gender": "female", "kind": "Person",
         "marriages": [400]},
        {"id": 10, "name": "Emma", "gender": "female", "parents": 400,
         "kind": "Person"},
        {"id": 11, "name": "Karen", "gender": "female", "parents": 200,
         "kind": "Person"},
    ]
    # Desktop Marriage.write → pair_bonds collection with person_a/person_b.
    pair_bonds = [
        {"id": 100, "person_a": 2, "person_b": 3, "kind": "Marriage"},
        {"id": 200, "person_a": 5, "person_b": 6, "kind": "Marriage"},
        {"id": 300, "person_a": 7, "person_b": 8, "kind": "Marriage"},
        {"id": 400, "person_a": 1, "person_b": 9, "kind": "Marriage"},
    ]
    # Post-commit_pdp_items: dateTime is QDateTime, never an ISO string.
    events = [
        {"id": 500, "kind": "married", "person": 2, "spouse": 3,
         "dateTime": _qdt("1980-01-01")},
        {"id": 501, "kind": "death", "person": 6,
         "dateTime": _qdt("2010-01-01")},
        {"id": 502, "kind": "moved", "person": 1,
         "dateTime": _qdt("2018-01-01")},
        {"id": 503, "kind": "shift", "person": 1, "symptom": "up",
         "dateTime": _qdt("2010-04-01")},
        {"id": 504, "kind": "shift", "person": 1, "symptom": "up",
         "dateTime": _qdt("2018-03-01")},
        {"id": 505, "kind": "shift", "person": 1, "relationship": "distance",
         "relationshipTargets": [3], "dateTime": _qdt("2018-06-01")},
        {"id": 506, "kind": "shift", "person": 1, "relationship": "conflict",
         "relationshipTargets": [3], "dateTime": _qdt("2018-09-01")},
    ]
    dd = _diagram(people, pair_bonds, events)
    cov = coverage(dd)
    assert cov[DataCategory.Mother].status == CoverageStatus.Covered
    assert cov[DataCategory.Mother].detail == "Mary"
    assert cov[DataCategory.Father].status == CoverageStatus.Covered
    assert cov[DataCategory.ParentsStatus].status == CoverageStatus.Covered
    assert cov[DataCategory.Siblings].status == CoverageStatus.Covered
    assert "Sarah" in cov[DataCategory.Siblings].detail
    assert cov[DataCategory.MaternalGrandparents].status == CoverageStatus.Covered
    assert cov[DataCategory.PaternalGrandparents].status == CoverageStatus.Covered
    assert cov[DataCategory.AuntsUncles].status == CoverageStatus.Covered
    assert cov[DataCategory.Spouse].status == CoverageStatus.Covered
    assert cov[DataCategory.Children].status == CoverageStatus.Covered
    assert cov[DataCategory.NodalEvents].status == CoverageStatus.Covered
    assert cov[DataCategory.SymptomTimeline].status == CoverageStatus.Covered
    assert outstanding_categories(dd) == []

    # No Qt repr may leak into the prompt fragment (date-label hardening).
    rendered = format_coverage_for_prompt(cov)
    assert "QDateTime" not in rendered
    assert "PyQt5" not in rendered
    assert "2010-04-01 → 2018-03-01" in rendered  # QDateTime rendered as ISO
