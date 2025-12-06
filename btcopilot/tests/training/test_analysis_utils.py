import pytest

from btcopilot.schema import (
    Person,
    Event,
    EventKind,
    RelationshipKind,
    PairBond,
    PDPDeltas,
    asdict,
)
from btcopilot.extensions import db
from btcopilot.personal.models import Statement, Discussion, Speaker, SpeakerType
from btcopilot.training.models import Feedback
from btcopilot.training.analysis_utils import (
    calculate_statement_match_breakdown,
    EntityMatchDetail,
    SARFMatchDetail,
    StatementMatchBreakdown,
)


def create_test_statement(discussion, ai_pdp, gt_pdp=None, approved=True):
    """Helper to create statement with speaker and optional approved feedback"""

    speaker = Speaker(discussion=discussion, name="Expert", type=SpeakerType.Expert)
    db.session.add(speaker)
    db.session.commit()

    statement = Statement(
        discussion=discussion,
        speaker=speaker,
        text="Test",
        pdp_deltas=asdict(ai_pdp) if ai_pdp else None,
    )
    db.session.add(statement)
    db.session.commit()

    if gt_pdp and approved:
        feedback = Feedback(
            statement_id=statement.id,
            feedback_type="extraction",
            edited_extraction=asdict(gt_pdp),
            approved=True,
            approved_by="admin",
            auditor_id="auditor1",
        )
        db.session.add(feedback)
        db.session.commit()

    return statement


def test_calculate_statement_match_breakdown_no_statement(flask_app):
    result = calculate_statement_match_breakdown(99999)
    assert result is None


def test_calculate_statement_match_breakdown_no_pdp_deltas(flask_app, test_user):
    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    statement = create_test_statement(discussion, None)

    result = calculate_statement_match_breakdown(statement.id)
    assert result is None


def test_calculate_statement_match_breakdown_no_approved_feedback(flask_app, test_user):
    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ai_pdp = PDPDeltas(
        people=[Person(id=1, name="John")], events=[], pair_bonds=[], delete=[]
    )

    statement = create_test_statement(discussion, ai_pdp, approved=False)

    result = calculate_statement_match_breakdown(statement.id)
    assert result is None


def test_calculate_statement_match_breakdown_with_perfect_match(flask_app, test_user):
    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ai_pdp = PDPDeltas(
        people=[Person(id=1, name="John", last_name="Doe")],
        events=[
            Event(
                id=2,
                kind=EventKind.Shift,
                person=1,
                description="Depression started",
                symptom="Down",
            )
        ],
        pair_bonds=[],
        delete=[],
    )

    gt_pdp = PDPDeltas(
        people=[Person(id=1, name="John", last_name="Doe")],
        events=[
            Event(
                id=2,
                kind=EventKind.Shift,
                person=1,
                description="Depression started",
                symptom="Down",
            )
        ],
        pair_bonds=[],
        delete=[],
    )

    statement = create_test_statement(discussion, ai_pdp, gt_pdp)

    result = calculate_statement_match_breakdown(statement.id)

    assert result is not None
    assert isinstance(result, StatementMatchBreakdown)
    assert result.statement_id == statement.id

    assert len(result.people_matches) == 1
    assert result.people_matches[0].match_type == "TP"
    assert result.people_matches[0].entity_type == "person"
    assert result.people_matches[0].ai_entity["name"] == "John"

    assert len(result.event_matches) == 1
    assert result.event_matches[0].match_type == "TP"
    assert result.event_matches[0].entity_type == "event"

    assert len(result.pair_bond_matches) == 0

    assert len(result.sarf_matches) > 0
    symptom_matches = [m for m in result.sarf_matches if m.variable_name == "symptom"]
    assert len(symptom_matches) == 1
    assert symptom_matches[0].detection_match == "TP"
    assert symptom_matches[0].value_match == "match"

    assert result.f1_metrics.people_f1 == 1.0
    assert result.f1_metrics.events_f1 == 1.0
    assert result.f1_metrics.aggregate_micro_f1 == 1.0


def test_calculate_statement_match_breakdown_with_fp_person(flask_app, test_user):
    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ai_pdp = PDPDeltas(
        people=[
            Person(id=1, name="John", last_name="Doe"),
            Person(id=2, name="Hallucinated Person"),
        ],
        events=[],
        pair_bonds=[],
        delete=[],
    )

    gt_pdp = PDPDeltas(
        people=[Person(id=1, name="John", last_name="Doe")],
        events=[],
        pair_bonds=[],
        delete=[],
    )

    statement = create_test_statement(discussion, ai_pdp, gt_pdp)

    result = calculate_statement_match_breakdown(statement.id)

    assert result is not None
    assert len(result.people_matches) == 2

    tp_matches = [m for m in result.people_matches if m.match_type == "TP"]
    fp_matches = [m for m in result.people_matches if m.match_type == "FP"]

    assert len(tp_matches) == 1
    assert tp_matches[0].ai_entity["name"] == "John"

    assert len(fp_matches) == 1
    assert fp_matches[0].ai_entity["name"] == "Hallucinated Person"
    assert fp_matches[0].gt_entity is None
    assert "hallucinated" in fp_matches[0].mismatch_reasons[0].lower()

    assert result.f1_metrics.people_f1 < 1.0


def test_calculate_statement_match_breakdown_with_fn_person(flask_app, test_user):
    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ai_pdp = PDPDeltas(
        people=[Person(id=1, name="John", last_name="Doe")],
        events=[],
        pair_bonds=[],
        delete=[],
    )

    gt_pdp = PDPDeltas(
        people=[
            Person(id=1, name="John", last_name="Doe"),
            Person(id=2, name="Missed Person"),
        ],
        events=[],
        pair_bonds=[],
        delete=[],
    )

    statement = create_test_statement(discussion, ai_pdp, gt_pdp)

    result = calculate_statement_match_breakdown(statement.id)

    assert result is not None
    assert len(result.people_matches) == 2

    tp_matches = [m for m in result.people_matches if m.match_type == "TP"]
    fn_matches = [m for m in result.people_matches if m.match_type == "FN"]

    assert len(tp_matches) == 1
    assert len(fn_matches) == 1
    assert fn_matches[0].gt_entity["name"] == "Missed Person"
    assert fn_matches[0].ai_entity is None
    assert "missed" in fn_matches[0].mismatch_reasons[0].lower()

    assert result.f1_metrics.people_f1 < 1.0


def test_sarf_value_mismatch(flask_app, test_user):
    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ai_pdp = PDPDeltas(
        people=[Person(id=1, name="John")],
        events=[
            Event(
                id=2,
                kind=EventKind.Shift,
                person=1,
                description="Depression",
                symptom="Up",
            )
        ],
        pair_bonds=[],
        delete=[],
    )

    gt_pdp = PDPDeltas(
        people=[Person(id=1, name="John")],
        events=[
            Event(
                id=2,
                kind=EventKind.Shift,
                person=1,
                description="Depression",
                symptom="Down",
            )
        ],
        pair_bonds=[],
        delete=[],
    )

    statement = create_test_statement(discussion, ai_pdp, gt_pdp)

    result = calculate_statement_match_breakdown(statement.id)

    assert result is not None
    symptom_matches = [m for m in result.sarf_matches if m.variable_name == "symptom"]
    assert len(symptom_matches) == 1
    assert symptom_matches[0].detection_match == "TP"
    assert symptom_matches[0].value_match == "mismatch"
    assert symptom_matches[0].ai_value == "Up"
    assert symptom_matches[0].gt_value == "Down"


def test_sarf_detection_fp_fn(flask_app, test_user):
    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ai_pdp = PDPDeltas(
        people=[Person(id=1, name="John"), Person(id=2, name="Mary")],
        events=[
            Event(
                id=3,
                kind=EventKind.Shift,
                person=1,
                description="AI hallucinated anxiety",
                anxiety="Up",
            )
        ],
        pair_bonds=[],
        delete=[],
    )

    gt_pdp = PDPDeltas(
        people=[Person(id=1, name="John"), Person(id=2, name="Mary")],
        events=[
            Event(
                id=4,
                kind=EventKind.Shift,
                person=2,
                description="AI missed symptom",
                symptom="Down",
            )
        ],
        pair_bonds=[],
        delete=[],
    )

    statement = create_test_statement(discussion, ai_pdp, gt_pdp)

    result = calculate_statement_match_breakdown(statement.id)

    assert result is not None

    anxiety_john = [
        m
        for m in result.sarf_matches
        if m.variable_name == "anxiety" and m.person_name == "John"
    ]
    assert len(anxiety_john) == 1
    assert anxiety_john[0].detection_match == "FP"
    assert anxiety_john[0].value_match is None

    symptom_mary = [
        m
        for m in result.sarf_matches
        if m.variable_name == "symptom" and m.person_name == "Mary"
    ]
    assert len(symptom_mary) == 1
    assert symptom_mary[0].detection_match == "FN"
    assert symptom_mary[0].value_match is None


def test_relationship_people_match(flask_app, test_user):
    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    ai_pdp = PDPDeltas(
        people=[Person(id=1, name="John"), Person(id=2, name="Mary")],
        events=[
            Event(
                id=3,
                kind=EventKind.Shift,
                person=1,
                description="Conflict with Mary",
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[2],
            )
        ],
        pair_bonds=[],
        delete=[],
    )

    gt_pdp = PDPDeltas(
        people=[Person(id=1, name="John"), Person(id=2, name="Mary")],
        events=[
            Event(
                id=3,
                kind=EventKind.Shift,
                person=1,
                description="Conflict with Mary",
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[2],
            )
        ],
        pair_bonds=[],
        delete=[],
    )

    statement = create_test_statement(discussion, ai_pdp, gt_pdp)

    result = calculate_statement_match_breakdown(statement.id)

    assert result is not None
    relationship_matches = [
        m for m in result.sarf_matches if m.variable_name == "relationship"
    ]
    john_rel = [m for m in relationship_matches if m.person_name == "John"]
    assert len(john_rel) == 1
    assert john_rel[0].detection_match == "TP"
    assert john_rel[0].value_match == "match"
    assert john_rel[0].people_match == "match"
