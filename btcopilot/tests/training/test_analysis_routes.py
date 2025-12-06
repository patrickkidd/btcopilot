import pytest

from btcopilot.schema import Person, Event, EventKind, PDPDeltas, asdict
from btcopilot.extensions import db
from btcopilot.personal.models import Statement, Discussion, Speaker, SpeakerType
from btcopilot.training.models import Feedback
from btcopilot.training.routes.analysis import (
    _calculate_discussion_f1,
    _parse_metric_to_filters,
    _get_metric_display_name,
    _statement_matches_filters,
    _statement_matches_metric_filter,
)
from btcopilot.training.analysis_utils import calculate_statement_match_breakdown


def create_discussion_with_gt(test_user):
    """Helper to create discussion with approved ground truth"""
    discussion = Discussion(user=test_user)
    db.session.add(discussion)
    db.session.commit()

    speaker = Speaker(discussion=discussion, name="Expert", type=SpeakerType.Expert)
    db.session.add(speaker)
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

    statement = Statement(
        discussion=discussion,
        speaker=speaker,
        text="Patient reports depression",
        pdp_deltas=asdict(ai_pdp),
    )
    db.session.add(statement)
    db.session.commit()

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

    return discussion, statement


def test_calculate_discussion_f1(flask_app, test_user):
    discussion, statement = create_discussion_with_gt(test_user)

    breakdown = calculate_statement_match_breakdown(statement.id)
    statement_breakdowns = [{"breakdown": breakdown}]

    result = _calculate_discussion_f1(statement_breakdowns)
    assert result is not None
    assert "aggregate_micro_f1" in result
    assert "people_f1" in result
    assert "events_f1" in result
    assert result["people_f1"] == 1.0
    assert result["events_f1"] == 1.0


def test_calculate_discussion_f1_empty():
    result = _calculate_discussion_f1([])
    assert result is None


def test_parse_metric_to_filters():
    assert _parse_metric_to_filters("aggregate_micro_f1") == {
        "entity_type": "all",
        "match_types": ["FP", "FN"],
    }
    assert _parse_metric_to_filters("people_f1") == {
        "entity_type": "people",
        "match_types": ["FP", "FN"],
    }
    assert _parse_metric_to_filters("symptom_detection") == {
        "entity_type": "all",
        "sarf_variable": "symptom",
        "sarf_level": "detection",
        "match_types": ["FP", "FN"],
    }


def test_get_metric_display_name():
    assert _get_metric_display_name("aggregate_micro_f1") == "Overall F1"
    assert _get_metric_display_name("people_f1") == "People Detection F1"
    assert _get_metric_display_name("symptom_detection") == "Symptom Detection F1"


def test_statement_matches_filters_people(flask_app, test_user):
    discussion, statement = create_discussion_with_gt(test_user)
    breakdown = calculate_statement_match_breakdown(statement.id)

    filters = {
        "entity_type": "people",
        "match_types": ["TP"],
        "sarf_variable": "all",
        "sarf_level": "all",
    }

    assert _statement_matches_filters(breakdown, filters) is True


def test_statement_matches_filters_sarf(flask_app, test_user):
    discussion, statement = create_discussion_with_gt(test_user)
    breakdown = calculate_statement_match_breakdown(statement.id)

    filters = {
        "entity_type": "all",
        "match_types": ["TP"],
        "sarf_variable": "symptom",
        "sarf_level": "detection",
    }

    assert _statement_matches_filters(breakdown, filters) is True


def test_statement_matches_metric_filter_people_f1(flask_app, test_user):
    discussion, statement = create_discussion_with_gt(test_user)
    breakdown = calculate_statement_match_breakdown(statement.id)

    filters = {"entity_type": "people", "match_types": ["FP", "FN"]}

    assert _statement_matches_metric_filter(breakdown, filters) is False


def test_statement_matches_metric_filter_symptom_detection(flask_app, test_user):
    discussion, statement = create_discussion_with_gt(test_user)
    breakdown = calculate_statement_match_breakdown(statement.id)

    filters = {
        "entity_type": "all",
        "sarf_variable": "symptom",
        "sarf_level": "detection",
        "match_types": ["FP", "FN"],
    }

    assert _statement_matches_metric_filter(breakdown, filters) is False
