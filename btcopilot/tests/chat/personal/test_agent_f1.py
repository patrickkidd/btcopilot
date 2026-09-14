"""The agent loop scored against ground truth: a replay that puts the right
person and the right event in the record scores 1.0 on both."""

import pytest

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Speaker, SpeakerType, Statement
from btcopilot.personal.toolbox import ToolName
from btcopilot.training.models import Feedback
from btcopilot.training.run_agent_f1 import run_agent_f1
from btcopilot.tests.personal.conftest import Model, called, said

AUDITOR = "auditor-1"


@pytest.fixture
def gt_discussion(test_user):
    """Two things the person said, and the approved record they should leave:
    one person and one dated event."""
    discussion = Discussion(
        user_id=test_user.id,
        diagram_id=test_user.free_diagram_id,
        title="Ground truth session",
        title_set_by_user=True,
        summary="Ground truth session",
        speakers=[
            Speaker(name="Client", type=SpeakerType.Subject, person_id=1),
            Speaker(name="Coach", type=SpeakerType.Expert),
        ],
    )
    db.session.add(discussion)
    db.session.flush()
    subject, expert = discussion.speakers

    said_first = Statement(
        discussion_id=discussion.id,
        speaker_id=subject.id,
        text="My dad Wren raised me.",
        order=0,
    )
    replied = Statement(
        discussion_id=discussion.id,
        speaker_id=expert.id,
        text="Tell me more about him.",
        order=1,
    )
    said_next = Statement(
        discussion_id=discussion.id,
        speaker_id=subject.id,
        text="He moved out in June of 1994.",
        order=2,
    )
    db.session.add_all([said_first, replied, said_next])
    db.session.flush()

    db.session.add(
        Feedback(
            statement_id=said_next.id,
            auditor_id=AUDITOR,
            feedback_type="extraction",
            approved=True,
            edited_extraction={
                "people": [{"id": 1, "name": "Wren"}],
                "events": [
                    {
                        "id": 2,
                        "kind": "moved",
                        "person": 1,
                        "dateTime": "1994-06-01",
                        "dateCertainty": "certain",
                    }
                ],
                "pair_bonds": [],
            },
        )
    )
    db.session.commit()
    return discussion


def test_a_replay_that_records_the_right_person_and_event_scores_one(gt_discussion):
    coach = Model(
        called(ToolName.EditPerson, name="Wren"),
        said("Wren is in the record now."),
        called(ToolName.EditEvent, kind="moved", date="1994-06-01", person=1),
        said("I put that down."),
    )
    totals = run_agent_f1(discussion_id=gt_discussion.id, model=coach)

    assert totals["count"] == 1
    result = totals["per_discussion"][0]
    assert result["people_f1"] == 1.0
    assert result["events_f1"] == 1.0
    assert (result["turns"], result["tool_calls"], result["failed_turns"]) == (2, 2, 0)
    assert result["replay_discussion_id"] != gt_discussion.id


def test_a_replay_never_writes_to_the_ground_truth_discussion(gt_discussion):
    before = len(gt_discussion.statements)
    diagram_before = gt_discussion.diagram.data

    run_agent_f1(
        discussion_id=gt_discussion.id,
        model=Model(
            called(ToolName.EditPerson, name="Wren"),
            said("Wren is in the record now."),
            called(ToolName.EditEvent, kind="moved", date="1994-06-01", person=1),
            said("I put that down."),
        ),
    )

    db.session.refresh(gt_discussion)
    assert len(gt_discussion.statements) == before
    assert gt_discussion.diagram.data == diagram_before
