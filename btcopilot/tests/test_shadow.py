import datetime

import pytest
from mock import Mock, patch

from decimal import Decimal

from btcopilot import diagramjson, extensions, record, shadow, turns
from btcopilot.admin import setting
from btcopilot.admin.setting import SettingKey
from btcopilot.coachmodel import Spent
from btcopilot.coachturn import CoachTurn, EmptyReply, prompt_version
from btcopilot.discussions import open_session
from btcopilot.extensions import db
from btcopilot.models import (
    Change,
    Diagram,
    Discussion,
    Interaction,
    InteractionKind,
    ModelCall,
    Purpose,
    ShadowTurn,
    Statement,
    TokenMeter,
)
from btcopilot.models.change import Author
from btcopilot.models.preferences import PrefKey
from btcopilot.models.diagram import diagram_data
from btcopilot.routes.diagrams import readable
from btcopilot.schema import ItemKind
from btcopilot.toolbox import ToolName
from btcopilot.tests.conftest import Model, called, csrf_token, said, version
from btcopilot.tests.fixtures import ORIGINALS
from btcopilot.tests.test_profile import own_person, titles  # noqa: F401


def test_a_scratch_turn_charges_no_one_and_leaves_the_profile(discussion, test_user):
    # R-0596
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
        purpose=Purpose.Coach,
        model=Model(named, said("Thank you, Wren.")),
        scratch=True,
    ).run()
    assert test_user.first_name == first
    assert TokenMeter.query.count() == 0
    assert ModelCall.query.filter_by(purpose=Purpose.Coach).count() == 2


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


def shadows(user, *models):
    shadow.switch(user, list(models), datetime.datetime.utcnow())
    db.session.commit()


def test_each_person_gets_their_own_coach_model_or_the_default(web, token, test_user):
    # R-0596
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
    # R-0596
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
    shadows(test_user, "sonnet")
    with patch("btcopilot.shadow.enqueue", shadow.run):
        second = post(web, token, "She is older.")

    row = ShadowTurn.query.one()
    assert (row.turn_id, row.statement_id, row.model) == (
        second["turn_id"],
        second["statement_id"],
        "sonnet",
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
    assert discussion.statements[-1].prompt_version == row.prompt_version
    assert row.prompt_version == prompt_version()
    db.session.refresh(diagram)
    assert diagram.data == record
    assert Change.query.filter_by(diagram_id=diagram.id).count() == changes
    assert Diagram.query.count() == diagrams
    assert Discussion.query.count() == 1
    assert {
        (c.diagram_id, c.purpose)
        for c in ModelCall.query.filter_by(turn_id=f"shadow-{row.id}")
    } == {(diagram.id, Purpose.Shadow)}
    assert {c.purpose for c in ModelCall.query.filter_by(turn_id=row.turn_id)} == {
        Purpose.Coach
    }
    assert TokenMeter.query.one().input_tokens == 10
    assert test_user.first_name == "Unit"


@pytest.mark.parametrize(
    "replied, asked, ran",
    [(6, 6, False), (4, 4, True), (4, 7, True)],
    ids=["quiet", "soon", "slow-to-vote"],
)
def test_a_turn_five_minutes_after_the_coach_last_replied_runs_no_shadow_and_turns_them_off(
    web, token, test_user, monkeypatch, replied, asked, ran
):
    # R-0637
    coach(
        monkeypatch,
        "btcopilot.turns.model_for",
        Model(said("Tell me about Nell."), said("How much older?")),
    )
    coach(monkeypatch, "btcopilot.shadow.model_for", Model(said("Older by how much?")))
    first = post(web, token, "My sister is Nell.")
    now = datetime.datetime.utcnow()
    question, reply = db.session.get(Discussion, first["discussion_id"]).statements
    question.created_at = now - datetime.timedelta(minutes=asked)
    reply.created_at = now - datetime.timedelta(minutes=replied)
    shadow.switch(test_user, ["sonnet"], now - datetime.timedelta(minutes=12))
    db.session.commit()
    with patch("btcopilot.shadow.enqueue", shadow.run):
        post(web, token, "She is older.")
    assert ShadowTurn.query.count() == ran
    assert bool(test_user.pref(PrefKey.ShadowModels)) == ran


def test_a_shadow_turn_reads_the_words_of_every_session_as_the_real_one_did(
    web, token, test_user, monkeypatch
):
    # R-0596
    real = coach(
        monkeypatch,
        "btcopilot.turns.model_for",
        Model(said("Tell me about Nell."), said("How much older?")),
    )
    first = post(web, token, "My sister is Nell.")
    later = open_session(
        test_user, db.session.get(Discussion, first["discussion_id"]).diagram
    )
    db.session.commit()
    candidate = coach(
        monkeypatch, "btcopilot.shadow.model_for", Model(said("Older by how much?"))
    )
    shadows(test_user, "sonnet")
    with patch("btcopilot.shadow.enqueue", shadow.run):
        web.post(
            f"/app/sessions/{later.id}/statements",
            json={"statement": "She is older."},
            headers={"X-CSRFToken": token},
        )

    assert ShadowTurn.query.one().text == "Older by how much?"
    shown, sent = candidate.histories[0], real.histories[1]
    assert shown[:-1] == sent[:-1]
    assert [m["role"] for m in shown] == ["user", "assistant", "user"]
    assert shown[-1]["content"][-1] == sent[-1]["content"][-1]


def test_each_shadow_model_runs_the_turn_again_on_its_own(
    web, token, test_user, monkeypatch
):
    # R-0596
    coach(monkeypatch, "btcopilot.turns.model_for", Model(said("Tell me about Nell.")))
    replies = {"haiku-4.5": "How much older is she?", "sonnet": "Older by how much?"}
    monkeypatch.setattr(
        "btcopilot.shadow.model_for", lambda name: Model(said(replies[name]))
    )
    setting.write(SettingKey.ShadowCandidates, list(replies))
    shadows(test_user, *replies)
    with patch("btcopilot.shadow.enqueue", shadow.run):
        body = post(web, token, "My sister is Nell.")
    rows = ShadowTurn.query.order_by(ShadowTurn.id).all()
    assert [(row.turn_id, row.model, row.text) for row in rows] == [
        (body["turn_id"], model, text) for model, text in replies.items()
    ]
    assert {c.turn_id for c in ModelCall.query} == {
        body["turn_id"],
        *(f"shadow-{row.id}" for row in rows),
    }


def test_a_stored_shadow_the_app_no_longer_offers_is_skipped(
    web, token, test_user, monkeypatch
):
    # R-0000 ruling pending: Patrick 2026-10-01, Bedrock on Bedrock machines
    coach(monkeypatch, "btcopilot.turns.model_for", Model(said("Tell me about Nell.")))
    coach(monkeypatch, "btcopilot.shadow.model_for", Model(said("Older by how much?")))
    setting.write(SettingKey.ShadowCandidates, ["gemini-1.0-gone", "sonnet"])
    shadows(test_user, "sonnet")
    # stored before the app dropped the model, so it never met the setting's check
    test_user.preferences = dict(
        test_user.preferences, shadow_models=["gemini-1.0-gone", "sonnet"]
    )
    db.session.commit()
    with patch("btcopilot.shadow.enqueue", shadow.run):
        post(web, token, "My sister is Nell.")
    assert [row.model for row in ShadowTurn.query] == ["sonnet"]
    assert test_user.pref(PrefKey.ShadowModels) == ("sonnet",)


def test_a_broken_shadow_keeps_its_error_and_leaves_no_scratch(
    web, token, test_user, monkeypatch
):
    # R-0596
    coach(monkeypatch, "btcopilot.turns.model_for", Model(said("Tell me about Nell.")))
    coach(monkeypatch, "btcopilot.shadow.model_for", Model())
    shadows(test_user, "sonnet")
    diagrams = Diagram.query.count()
    with patch("btcopilot.shadow.enqueue"):
        body = post(web, token, "My sister is Nell.")
    row = ShadowTurn.query.one()
    assert row.turn_id == body["turn_id"]
    with pytest.raises(IndexError):
        shadow.run(row.id)
    assert row.error.startswith("IndexError")
    assert row.snapshot is None
    assert Diagram.query.count() == diagrams
    assert Discussion.query.count() == 1


def test_a_failed_real_turn_starts_no_shadow(web, token, test_user, monkeypatch):
    # R-0596
    coach(monkeypatch, "btcopilot.turns.model_for", Model(said("")))
    shadows(test_user, "sonnet")
    with patch("btcopilot.turns.enqueue"):
        body = post(web, token, "My sister is Nell.")
    enqueue = Mock()
    with patch("btcopilot.shadow.enqueue", enqueue), pytest.raises(EmptyReply):
        turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    enqueue.assert_not_called()
    assert ShadowTurn.query.count() == 0


def test_a_shadow_waits_on_its_own_queue(flask_app, monkeypatch):
    # R-0596
    monkeypatch.setattr(extensions, "celery", None)
    ORIGINALS["init_celery"](flask_app)
    router = extensions.celery.amqp.router
    assert router.route({}, shadow.TASK)["queue"].name == shadow.QUEUE
    assert (
        router.route({}, turns.TASK)["queue"].name
        == extensions.celery.conf.task_default_queue
    )


class Looks(Model):
    """A shadow model that reads the user's diagram list while it runs."""

    def __init__(self, user, *turns):
        super().__init__(*turns)
        self.user = user
        self.listed = []
        self.scratch = []

    def turn(self, system, messages, tools, turn_id=""):
        self.listed.append({d.id for d in readable(self.user)})
        self.scratch.append({d.id for d in Diagram.query.filter_by(scratch=True)})
        return (yield from super().turn(system, messages, tools, turn_id))


def test_the_user_never_sees_the_scratch_record(web, token, test_user, monkeypatch):
    # R-0596
    coach(monkeypatch, "btcopilot.turns.model_for", Model(said("Tell me about Nell.")))
    looks = coach(
        monkeypatch, "btcopilot.shadow.model_for", Looks(test_user, said("Go on."))
    )
    shadows(test_user, "sonnet")
    with patch("btcopilot.shadow.enqueue", shadow.run):
        post(web, token, "My sister is Nell.")
    assert looks.scratch[0]
    assert not looks.listed[0] & looks.scratch[0]


def renamed(diagram, name):
    return Model(
        called(
            ToolName.EditPerson,
            id=1,
            name=name,
            last_name="Hale",
            version=version(diagram),
        ),
        said("Go on."),
    )


def test_a_backfill_rebuilds_the_record_the_real_turn_found(
    web, token, test_user, monkeypatch
):
    # R-0596
    coach(monkeypatch, "btcopilot.turns.model_for", Model(said("Tell me about Nell.")))
    first = post(web, token, "My sister is Nell.")
    diagram = db.session.get(Discussion, first["discussion_id"]).diagram
    shadows(test_user, "sonnet")
    coach(monkeypatch, "btcopilot.turns.model_for", renamed(diagram, "Wren"))
    with patch("btcopilot.shadow.enqueue"):
        second = post(web, token, "I am Wren.")
    shadows(test_user)
    coach(monkeypatch, "btcopilot.turns.model_for", renamed(diagram, "Wrenn"))
    post(web, token, "Two n's.")
    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "Ren"}],
        author=Author.User,
        turn_id="by-hand",
        user_id=test_user.id,
    )

    live = ShadowTurn.query.one()
    said_second = db.session.get(Statement, second["statement_id"])
    assert diagram_data(diagramjson.loads(shadow.rebuilt(said_second))) == (
        diagram_data(diagramjson.loads(live.snapshot.encode("utf-8")))
    )
    db.session.refresh(diagram)
    assert diagram.get_diagram_data().people[0]["name"] == "Ren"


def test_a_backfill_runs_only_the_turns_not_yet_run(web, token, test_user, monkeypatch):
    # R-0596
    real = coach(
        monkeypatch,
        "btcopilot.turns.model_for",
        Model(said("Tell me about Nell."), said("How much older?"), said("Go on.")),
    )
    real.turns[0].spent = Spent(input=1_000_000, output=0)
    first = post(web, token, "My sister is Nell.")
    setting.write(SettingKey.ShadowCandidates, ["sonnet", "haiku-4.5"])
    shadows(test_user, "haiku-4.5")
    with patch("btcopilot.shadow.enqueue"):
        second = post(web, token, "She is older.")
    shadows(test_user)
    post(web, token, "By two years.")
    discussion = db.session.get(Discussion, first["discussion_id"])
    discussion.statements[-1].turn_id = None
    db.session.commit()

    assert shadow.untraced(test_user) == 1
    assert [s.turn_id for s in shadow.pending(test_user, "sonnet")] == [
        first["turn_id"],
        second["turn_id"],
    ]
    usd, unpriced = shadow.estimate(shadow.pending(test_user, "sonnet")[:1], "sonnet")
    assert (usd, unpriced) == (Decimal("2.00"), 0)
    enqueue = Mock()
    with patch("btcopilot.shadow.enqueue", enqueue):
        assert shadow.backfill(test_user, "haiku-4.5") == 1
    rows = ShadowTurn.query.filter_by(model="haiku-4.5").order_by(ShadowTurn.id).all()
    assert [(r.turn_id, r.statement_id) for r in rows] == [
        (second["turn_id"], second["statement_id"]),
        (first["turn_id"], first["statement_id"]),
    ]
    enqueue.assert_called_once_with(rows[-1].id)


def test_a_backfilled_turn_runs_like_a_live_one(web, token, test_user, monkeypatch):
    # R-0596
    coach(monkeypatch, "btcopilot.turns.model_for", Model(said("Tell me about Nell.")))
    post(web, token, "My sister is Nell.")
    coach(monkeypatch, "btcopilot.shadow.model_for", Model(said("Older or younger?")))
    with patch("btcopilot.shadow.enqueue", shadow.run):
        shadow.backfill(test_user, "sonnet")
    row = ShadowTurn.query.one()
    assert row.text == "Older or younger?"
    assert row.snapshot is None and row.error is None
