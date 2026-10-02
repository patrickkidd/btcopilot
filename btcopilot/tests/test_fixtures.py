from btcopilot.extensions import db
from btcopilot.models import Author, Change, Interaction, InteractionKind, SpeakerType
from btcopilot.review.models import Coding, Cut, Item, Note, ReviewStatus, Vote, VoteChoice
from btcopilot.routes.fixtures import install
from btcopilot.schema import ItemKind


def test_a_fixture_reinstalls_over_a_record_that_was_used(flask_app, foreign_keys):
    # R-0322
    diagram = install("editable").free_diagram
    db.session.add_all(
        [
            Change(diagram_id=diagram.id, turn_id="t1", author=Author.Coach, deltas=[]),
            Interaction(
                diagram_id=diagram.id,
                kind=InteractionKind.Look,
                item_kind=ItemKind.Person,
            ),
        ]
    )
    db.session.commit()
    install("editable")
    assert Change.query.count() == Interaction.query.count() == 0


def test_a_fixture_reinstalls_while_its_session_is_on_the_agenda(flask_app, foreign_keys):
    # R-0322, R-0296
    user = install("play")
    session = user.free_diagram.discussions[0]
    turns = sorted(session.statements, key=lambda s: s.order)
    cut = Cut(
        diagram_id=session.diagram_id,
        start_statement_id=turns[0].id,
        end_statement_id=turns[-1].id,
        user_id=user.id,
    )
    db.session.add(cut)
    db.session.flush()
    coding = Coding(cut_id=cut.id, user_id=user.id, diagram_id=user.free_diagram_id)
    item = Item(cut_id=cut.id, item_kind=ItemKind.Event, opinions=[], status=ReviewStatus.Disputed)
    db.session.add_all([coding, item])
    db.session.flush()
    db.session.add_all(
        [
            Note(coding_id=coding.id, statement_id=turns[0].id, text="Wren", turn_id="t1"),
            Vote(review_item_id=item.id, user_id=user.id, choice=VoteChoice.Drop),
        ]
    )
    db.session.commit()
    install("play")

    assert [Cut.query.count(), Coding.query.count(), Note.query.count()] == [0, 0, 0]
    assert [Item.query.count(), Vote.query.count()] == [0, 0]


def test_a_fixture_familys_coach_speaks_as_the_coach(flask_app):
    # R-0322
    session = install("whitlock").free_diagram.discussions[0]

    assert session.chat_ai_speaker.type == SpeakerType.Expert
