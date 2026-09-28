import pytest
from mock import Mock, patch

from btcopilot import extensions, shadow, turns
from btcopilot.admin import setting
from btcopilot.admin.setting import SettingKey
from btcopilot.coachmodel import Spent
from btcopilot.coachturn import CoachTurn, EmptyReply
from btcopilot.extensions import db
from btcopilot.models import (
    Change,
    Diagram,
    Discussion,
    Interaction,
    InteractionKind,
    ModelCall,
    ShadowTurn,
    TokenMeter,
)
from btcopilot.schema import ItemKind
from btcopilot.toolbox import ToolName
from btcopilot.tests.conftest import Model, called, csrf_token, said, version
from btcopilot.tests.fixtures import ORIGINALS
from btcopilot.tests.test_profile import own_person, titles  # noqa: F401


def test_a_scratch_turn_charges_no_one_and_leaves_the_profile(discussion, test_user):
    # R-0589
    named = called(
        ToolName.EditPerson,
        id=1,
        name="Wren",
        last_name="Hale",
        version=version(discussion.diagram),
    )
    named.spent = Spent(input=1000, output=50)
    first = test_user.first_name
    CoachTurn(
        discussion,
        "I am Wren Hale",
        model=Model(named, said("Thank you, Wren.")),
        scratch=True,
    ).run()
    assert test_user.first_name == first
    assert TokenMeter.query.count() == 0
    assert ModelCall.query.count() == 2


@pytest.fixture
def token(web):
    return csrf_token(web)


def post(web, token, statement):
    return web.post(
        "/app/chat", json={"statement": statement}, headers={"X-CSRFToken": token}
    ).get_json()


def coach(monkeypatch, where, model):
    monkeypatch.setattr(where, lambda *a, **k: model)
    return model


def test_each_person_gets_their_own_coach_model_or_the_default(web, token, test_user):
    # R-0589
    asked = []

    def model_for(name=None):
        asked.append(name)
        return Model(said("Tell me more."))

    with patch("btcopilot.turns.model_for", model_for):
        post(web, token, "My sister is Nell.")
        setting.write(SettingKey.CoachModel, "haiku-4.5", test_user.id)
        post(web, token, "She is older.")
    assert asked == [None, "haiku-4.5"]


def test_a_shadow_turn_is_kept_apart_from_the_real_one(
    web, token, test_user, monkeypatch
):
    # R-0589
    real = coach(
        monkeypatch,
        "btcopilot.turns.model_for",
        Model(said("Tell me about Nell."), said("How much older?")),
    )
    real.turns[1].spent = Spent(input=10, output=5)
    first = post(web, token, "My sister is Nell.")
    diagram = db.session.get(Discussion, first["discussion_id"]).diagram
    db.session.add(
        Interaction(
            diagram_id=diagram.id,
            kind=InteractionKind.Look,
            item_kind=ItemKind.Person,
            item_id="1",
        )
    )
    db.session.commit()
    record = diagram.data
    changes = Change.query.filter_by(diagram_id=diagram.id).count()
    diagrams = Diagram.query.count()
    named = called(ToolName.EditPerson, id=1, name="Wren", last_name="Hale", version=1)
    named.spent = Spent(input=1000, output=50)
    candidate = coach(
        monkeypatch,
        "btcopilot.shadow.model_for",
        Model(named, said("Thank you, Wren.")),
    )
    setting.write(SettingKey.ShadowModel, "haiku-4.5", test_user.id)
    with patch("btcopilot.shadow.enqueue", shadow.run):
        second = post(web, token, "She is older.")

    row = ShadowTurn.query.one()
    assert (row.turn_id, row.statement_id, row.model) == (
        second["turn_id"],
        second["statement_id"],
        "haiku-4.5",
    )
    assert row.text == "Thank you, Wren."
    assert [(c["name"], c["refusal"]) for c in row.tool_calls] == [
        (ToolName.EditPerson.value, None)
    ]
    assert (row.input_tokens, row.output_tokens) == (1000, 50)
    assert row.cost_usd > 0
    assert row.snapshot is None and row.error is None
    # the candidate's own list grows with its tool calls after it was sent
    sent = len(real.histories[1])
    assert candidate.histories[0][: sent - 1] == real.histories[1][:-1]
    assert (
        candidate.histories[0][sent - 1]["content"][-1]
        == real.histories[1][-1]["content"][-1]
    )
    assert "look person 1" in candidate.systems[0]

    discussion = db.session.get(Discussion, first["discussion_id"])
    assert [s.text for s in discussion.statements] == [
        "My sister is Nell.",
        "Tell me about Nell.",
        "She is older.",
        "How much older?",
    ]
    db.session.refresh(diagram)
    assert diagram.data == record
    assert Change.query.filter_by(diagram_id=diagram.id).count() == changes
    assert Diagram.query.count() == diagrams
    assert Discussion.query.count() == 1
    assert {
        c.diagram_id for c in ModelCall.query.filter_by(turn_id=f"shadow-{row.turn_id}")
    } == {diagram.id}
    assert TokenMeter.query.one().input_tokens == 10
    assert test_user.first_name == "Unit"


def test_a_broken_shadow_keeps_its_error_and_leaves_no_scratch(
    web, token, test_user, monkeypatch
):
    # R-0589
    coach(monkeypatch, "btcopilot.turns.model_for", Model(said("Tell me about Nell.")))
    coach(monkeypatch, "btcopilot.shadow.model_for", Model())
    setting.write(SettingKey.ShadowModel, "haiku-4.5", test_user.id)
    diagrams = Diagram.query.count()
    with patch("btcopilot.shadow.enqueue"):
        body = post(web, token, "My sister is Nell.")
    with pytest.raises(IndexError):
        shadow.run(body["turn_id"])
    row = ShadowTurn.query.one()
    assert row.error.startswith("IndexError")
    assert row.snapshot is None
    assert Diagram.query.count() == diagrams
    assert Discussion.query.count() == 1


def test_a_failed_real_turn_starts_no_shadow(web, token, test_user, monkeypatch):
    # R-0589
    coach(monkeypatch, "btcopilot.turns.model_for", Model(said("")))
    setting.write(SettingKey.ShadowModel, "haiku-4.5", test_user.id)
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token, "My sister is Nell.")
    enqueue = Mock()
    with patch("btcopilot.shadow.enqueue", enqueue), pytest.raises(EmptyReply):
        turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    enqueue.assert_not_called()
    assert ShadowTurn.query.count() == 0


def test_a_shadow_waits_on_its_own_queue(flask_app, monkeypatch):
    # R-0589
    monkeypatch.setattr(extensions, "celery", None)
    ORIGINALS["init_celery"](flask_app)
    router = extensions.celery.amqp.router
    assert router.route({}, shadow.TASK)["queue"].name == shadow.QUEUE
    assert (
        router.route({}, turns.TASK)["queue"].name
        == extensions.celery.conf.task_default_queue
    )
