from btcopilot.extensions import db
from btcopilot.models import Author, Change, Interaction, InteractionKind
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
