"""The ballot by pairing: the pairing job, its fixed check, Patrick's joins and
splits before the vote opens, opening as a second step, and agreement by who
people are. The model is stood in for; the prompt's own eval is live."""

from mock import Mock, patch

from btcopilot import extensions, llmutil, turnlog
from btcopilot.extensions import db
from btcopilot.metered import Metered
from btcopilot.models import Observation, ObservationKind, Purpose
from btcopilot.models import Diagram
from btcopilot.review import adapter, pairing, snapshot
from btcopilot.review.models import Cut, Item, ReviewStatus, Vote, VoteChoice
from btcopilot.review.models.item import PairingConfidence
from btcopilot.review.pairing import Answer, Entry, Pairing
from btcopilot.schema import ItemKind
from btcopilot.tests.review.conftest import coded, person, shift

# The queue, stood in for: the job runs where it is sent.
QUEUE = Mock(send_task=lambda name, args, kwargs: pairing.built(*args, **kwargs))


def words(kind, item) -> tuple:
    if kind is ItemKind.Person:
        return (kind, item["name"])
    if kind is ItemKind.PairBond:
        return (kind, item["person_a"], item["person_b"])
    return (kind, item.get("description"))


def by_words(cut) -> Answer:
    """The model, stood in for: versions in the same words are one thing."""
    groups = {}
    for key, (kind, item, _) in pairing.listed(snapshot.done_codings(cut)).items():
        groups.setdefault(words(kind, item), []).append(Entry(*key))
    return Answer(
        [Pairing(e, "same words", PairingConfidence.Sure) for e in groups.values()]
    )


def build(patrick, cut, answer=None):
    """Patrick asks for the ballot; the job runs where the queue would."""

    def asked(meter, *args, **kwargs):
        return answer or by_words(db.session.get(Cut, cut.id))

    with (
        patch.object(Metered, "structured", asked),
        patch.object(extensions, "celery", QUEUE),
    ):
        return patrick.post("/review/items", json={"cut_id": cut.id})


def open_vote(patrick, cut):
    build(patrick, cut)
    return patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})


def two_codings(test_user, test_user_2, cut):
    """Ann's worry, written by both coders; Ann's move, by one."""
    a = coded(
        test_user,
        cut,
        {"people": [person(1, "Ann")], "events": [shift(10, 1, "worried")]},
    )
    b = coded(
        test_user_2,
        cut,
        {
            "people": [person(5, "Ann")],
            "events": [shift(20, 5, "worried"), shift(21, 5, "moved", "2021-06-01")],
        },
    )
    return a, b


def test_asking_for_the_ballot_builds_the_pairings_on_the_worker(
    patrick, test_user, test_user_2, cut
):
    # R-0961, R-0962, R-0964
    a, b = two_codings(test_user, test_user_2, cut)
    asked = build(patrick, cut)
    assert asked.status_code == 202

    read = patrick.get(f"/review/cuts/{cut.id}").get_json()
    assert read["ballot"] == "built"
    assert read["pairing_agent"]["model"] == pairing.MODEL
    worried = next(
        i
        for i in Item.query.filter_by(cut_id=cut.id)
        if i.item_kind is ItemKind.Event and len(i.opinions) == 2
    )
    assert sorted((o["coding_id"], o["item_id"]) for o in worried.opinions) == [
        (a.id, 10),
        (b.id, 20),
    ]
    assert worried.pairing_reason == "same words"


def test_the_pairing_call_is_fable_on_its_own_purpose(
    patrick, test_user, test_user_2, cut
):
    # R-0961, R-0962
    two_codings(test_user, test_user_2, cut)
    asked = {}

    def structured(meter, prompt, fmt, schema, limit, model=None):
        asked.update(model=model, purpose=meter.purpose, prompt=prompt)
        return by_words(db.session.get(Cut, cut.id))

    with (
        patch.object(Metered, "structured", structured),
        patch.object(extensions, "celery", QUEUE),
    ):
        patrick.post("/review/items", json={"cut_id": cut.id})
    assert asked["model"] == "claude-fable-5-2"
    assert asked["purpose"] is Purpose.Pairing
    assert "turn 0" in asked["prompt"] and '"description": "moved"' in asked["prompt"]


def test_a_coders_version_left_out_fails_the_ballot_and_is_observed(
    patrick, test_user, test_user_2, cut
):
    # R-0961
    a, b = two_codings(test_user, test_user_2, cut)
    short = Answer(
        [Pairing([Entry(a.id, 10), Entry(b.id, 20)], "same", PairingConfidence.Sure)]
    )
    build(patrick, cut, short)

    assert patrick.get(f"/review/cuts/{cut.id}").get_json()["ballot"] == "failed"
    seen = Observation.query.filter_by(kind=ObservationKind.PairingCheck).one()
    assert [b.id, 21] in seen.detail["missing"]
    assert seen.diagram_id == cut.diagram_id
    opened = patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    assert opened.status_code == 400


def test_a_pairing_of_a_person_and_an_event_fails_the_check(
    patrick, test_user, test_user_2, cut
):
    # R-0961
    a, b = two_codings(test_user, test_user_2, cut)
    mixed = by_words(cut)
    mixed.pairings[0].entries.append(mixed.pairings[1].entries.pop())
    build(patrick, cut, mixed)

    seen = Observation.query.filter_by(kind=ObservationKind.PairingCheck).one()
    assert seen.detail["mixed"]


def test_the_vote_opens_only_on_built_pairings_and_never_rebuilds_them(
    patrick, test_user, test_user_2, cut
):
    # R-0963
    two_codings(test_user, test_user_2, cut)
    early = patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    assert early.status_code == 400

    build(patrick, cut)
    before = sorted(i.id for i in Item.query.filter_by(cut_id=cut.id))
    opened = patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    assert opened.get_json()["ballot"] == "open"
    assert sorted(i.id for i in Item.query.filter_by(cut_id=cut.id)) == before


def test_a_coding_finished_after_the_pairings_keeps_the_vote_shut(
    patrick, test_user, test_user_2, cut
):
    # R-0961
    coded(test_user, cut, {"people": [person(1, "Ann")]})
    build(patrick, cut)
    coded(test_user_2, cut, {"people": [person(5, "Ann")]})

    opened = patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    assert opened.status_code == 400
    assert db.session.get(Cut, cut.id).vote_opened_at is None


def test_the_ballot_is_never_rebuilt_over_votes(
    patrick, coder, test_user, test_user_2, cut
):
    # R-0963, R-0275
    two_codings(test_user, test_user_2, cut)
    open_vote(patrick, cut)
    item = next(
        i
        for i in Item.query.filter_by(cut_id=cut.id)
        if i.status is ReviewStatus.Disputed
    )
    db.session.add(
        Vote(review_item_id=item.id, user_id=coder.user.id, choice=VoteChoice.Drop)
    )
    db.session.commit()

    assert build(patrick, cut).status_code == 409
    cut_row = db.session.get(Cut, cut.id)
    cut_row.vote_opened_at = None
    db.session.commit()
    assert build(patrick, cut).status_code == 409
    assert Vote.query.count() == 1


def test_people_are_agreed_by_who_they_are_not_by_their_numbers(
    patrick, test_user, test_user_2, cut
):
    # R-0961
    two_codings(test_user, test_user_2, cut)
    open_vote(patrick, cut)

    rows = {
        (i.item_kind, len(i.opinions)): i.status
        for i in Item.query.filter_by(cut_id=cut.id)
    }
    assert rows[(ItemKind.Person, 2)] is ReviewStatus.Agreed
    assert rows[(ItemKind.Event, 2)] is ReviewStatus.Agreed
    assert rows[(ItemKind.Event, 1)] is ReviewStatus.Disputed


def test_parents_named_in_either_order_are_the_same_parents(
    patrick, test_user, test_user_2, cut
):
    # R-0961
    a = coded(
        test_user,
        cut,
        {
            "people": [
                person(1, "Wally"),
                person(2, "Louann"),
                dict(person(3, "Kid"), parents=7),
            ],
            "pair_bonds": [{"id": 7, "person_a": 1, "person_b": 2}],
        },
    )
    b = coded(
        test_user_2,
        cut,
        {
            "people": [
                person(4, "Louann"),
                person(5, "Wally"),
                dict(person(6, "Kid"), parents=8),
            ],
            "pair_bonds": [{"id": 8, "person_a": 4, "person_b": 5}],
        },
    )
    together = [
        [Entry(a.id, 1), Entry(b.id, 5)],
        [Entry(a.id, 2), Entry(b.id, 4)],
        [Entry(a.id, 3), Entry(b.id, 6)],
        [Entry(a.id, 7), Entry(b.id, 8)],
    ]
    build(
        patrick,
        cut,
        Answer([Pairing(e, "same", PairingConfidence.Sure) for e in together]),
    )

    assert {i.status for i in Item.query.filter_by(cut_id=cut.id)} == {
        ReviewStatus.Agreed
    }


def test_one_coder_with_two_versions_of_one_thing_is_not_agreed(
    patrick, test_user, test_user_2, cut
):
    # R-0961
    coded(
        test_user,
        cut,
        {"people": [person(1, "Ann")], "events": [shift(10, 1, "moved")]},
    )
    coded(
        test_user_2,
        cut,
        {
            "people": [person(1, "Ann")],
            "events": [shift(20, 1, "moved"), shift(21, 1, "moved")],
        },
    )
    open_vote(patrick, cut)

    moved = next(i for i in Item.query.filter_by(cut_id=cut.id) if len(i.opinions) == 3)
    assert moved.status is ReviewStatus.Disputed
    row = patrick.get(f"/review/items?cut_id={cut.id}").get_json()
    assert next(r for r in row if r["id"] == moved.id)["not_coded"] == 0


def test_patrick_splits_a_version_off_into_its_own_pairing(
    patrick, test_user, test_user_2, cut
):
    # R-0963
    a, b = two_codings(test_user, test_user_2, cut)
    build(patrick, cut)
    worried = next(
        i
        for i in Item.query.filter_by(cut_id=cut.id)
        if len(i.opinions) == 2 and i.item_kind is ItemKind.Event
    )

    split = patrick.post(
        "/review/items",
        json={"cut_id": cut.id, "opinions": [{"coding_id": b.id, "item_id": 20}]},
    )
    assert split.status_code == 201
    body = split.get_json()
    assert body["deleted"] == []
    assert {r["pairing_reason"] for r in body["items"]} == {pairing.SET_BY_PATRICK}
    assert {r["pairing_confidence"] for r in body["items"]} == {"sure"}
    assert [
        (o["coding_id"], o["item_id"])
        for o in db.session.get(Item, worried.id).opinions
    ] == [(a.id, 10)]


def test_patrick_joins_two_pairings_and_the_emptied_one_goes(
    patrick, test_user, test_user_2, cut
):
    # R-0963
    a, b = two_codings(test_user, test_user_2, cut)
    build(patrick, cut)
    rows = Item.query.filter_by(cut_id=cut.id, item_kind=ItemKind.Event).all()
    worried = next(i for i in rows if len(i.opinions) == 2)
    moved = next(i for i in rows if len(i.opinions) == 1)

    joined = patrick.patch(
        f"/review/items/{worried.id}",
        json={
            "opinions": [
                {"coding_id": a.id, "item_id": 10},
                {"coding_id": b.id, "item_id": 20},
                {"coding_id": b.id, "item_id": 21},
            ]
        },
    ).get_json()
    assert joined["deleted"] == [moved.id]
    assert len(db.session.get(Item, worried.id).opinions) == 3


def test_a_join_or_split_of_a_person_with_an_event_is_refused(
    patrick, test_user, test_user_2, cut
):
    # R-0961
    a, b = two_codings(test_user, test_user_2, cut)
    build(patrick, cut)
    refused = patrick.post(
        "/review/items",
        json={
            "cut_id": cut.id,
            "opinions": [
                {"coding_id": a.id, "item_id": 1},
                {"coding_id": a.id, "item_id": 10},
            ],
        },
    )
    assert refused.status_code == 400


def test_a_coder_never_reads_the_pairings_before_the_vote(
    patrick, coder, test_user, test_user_2, cut
):
    # R-0961, R-0963
    two_codings(test_user, test_user_2, cut)
    build(patrick, cut)

    assert coder.get(f"/review/items?cut_id={cut.id}").get_json() == []
    mine = patrick.get(f"/review/items?cut_id={cut.id}").get_json()
    assert all(r["pairing_confidence"] == "sure" for r in mine)

    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    theirs = coder.get(f"/review/items?cut_id={cut.id}").get_json()
    assert theirs and all("pairing_reason" not in r for r in theirs)
    assert all("pairing_confidence" not in r for r in theirs)


def test_each_version_names_who_a_relationship_shift_is_toward(
    patrick, test_user, test_user_2, cut
):
    # R-0965
    toward = dict(
        shift(10, 1, "fought"), relationship="conflict", relationshipTargets=[2]
    )
    coded(
        test_user,
        cut,
        {"people": [person(1, "Ann"), person(2, "Bo")], "events": [toward]},
    )
    coded(
        test_user_2,
        cut,
        {"people": [person(1, "Ann"), person(2, "Bo")], "events": [toward]},
    )
    build(patrick, cut)

    rows = patrick.get(f"/review/items?cut_id={cut.id}").get_json()
    fought = next(r for r in rows if r["item_kind"] == "event")
    assert [o["toward_names"] for o in fought["opinions"]] == [["Bo"], ["Bo"]]


def test_a_coder_takes_their_own_vote_back(patrick, coder, test_user, test_user_2, cut):
    # R-0965
    two_codings(test_user, test_user_2, cut)
    open_vote(patrick, cut)
    item = next(
        i
        for i in Item.query.filter_by(cut_id=cut.id)
        if i.status is ReviewStatus.Disputed
    )
    patrick.put(f"/review/items/{item.id}/vote", json={"choice": "drop"})
    coder.put(f"/review/items/{item.id}/vote", json={"choice": "drop"})

    taken = coder.delete(f"/review/items/{item.id}/vote")
    assert taken.status_code == 204
    assert [v.user_id for v in Vote.query.all()] == [patrick.user.id]


def test_no_vote_is_taken_back_while_the_vote_is_shut(
    patrick, coder, test_user, test_user_2, cut
):
    # R-0965
    two_codings(test_user, test_user_2, cut)
    build(patrick, cut)
    item = Item.query.filter_by(cut_id=cut.id).first()
    assert coder.delete(f"/review/items/{item.id}/vote").status_code == 400


def test_a_failed_call_leaves_the_ballot_failed_and_is_never_retried(
    patrick, test_user, test_user_2, cut
):
    # R-0961
    two_codings(test_user, test_user_2, cut)
    calls = []

    def refused(meter, *args, **kwargs):
        calls.append(1)
        raise llmutil.Billed(
            "refused", llmutil.Served("m"), llmutil.Spent()
        )

    with (
        patch.object(Metered, "structured", refused),
        patch.object(extensions, "celery", QUEUE),
    ):
        try:
            patrick.post("/review/items", json={"cut_id": cut.id})
        except llmutil.Billed:
            pass
    assert calls == [1]
    assert patrick.get(f"/review/cuts/{cut.id}").get_json()["ballot"] == "failed"


def test_keeping_a_coder_with_two_versions_writes_both(
    patrick, test_user, test_user_2, case, cut
):
    # R-0961, R-0257
    coded(
        test_user,
        cut,
        {"people": [person(1, "Ann")], "events": [shift(10, 1, "moved")]},
    )
    b = coded(
        test_user_2,
        cut,
        {
            "people": [person(1, "Ann")],
            "events": [
                dict(shift(20, 1, "moved"), kind="noted", symptom=None),
                shift(21, 1, "moved"),
            ],
        },
    )
    open_vote(patrick, cut)
    both = next(i for i in Item.query.filter_by(cut_id=cut.id) if len(i.opinions) == 3)

    kept = patrick.patch(
        f"/review/items/{both.id}",
        json={"choice": "keep", "value": {"coding_id": b.id}},
    )
    assert kept.status_code == 200
    events = adapter.record_of(db.session.get(Diagram, case.id))["events"]
    assert sorted(e["kind"] for e in events) == ["noted", "shift"]


def test_a_job_that_breaks_after_its_call_fails_the_ballot_and_can_build_again(
    patrick, test_user, test_user_2, cut
):
    # R-0961, R-0517
    two_codings(test_user, test_user_2, cut)

    def broke(meter, *args, **kwargs):
        raise KeyError("No price for model claude-fable-5-2")

    with (
        patch.object(Metered, "structured", broke),
        patch.object(extensions, "celery", QUEUE),
    ):
        assert patrick.post("/review/items", json={"cut_id": cut.id}).status_code == 500
    assert patrick.get(f"/review/cuts/{cut.id}").get_json()["ballot"] == "failed"
    seen = Observation.query.filter_by(kind=ObservationKind.PairingCheck).one()
    assert "No price" in seen.detail["error"]
    assert build(patrick, cut).status_code == 202
    assert patrick.get(f"/review/cuts/{cut.id}").get_json()["ballot"] == "built"


def test_a_job_whose_worker_died_fails_the_ballot_on_the_next_read(
    patrick, test_user, test_user_2, cut
):
    # R-0961, R-0517
    two_codings(test_user, test_user_2, cut)
    with patch.object(extensions, "celery", Mock()):
        assert patrick.post("/review/items", json={"cut_id": cut.id}).status_code == 202
    assert patrick.get(f"/review/cuts/{cut.id}").get_json()["ballot"] == "building"

    turnlog.store().holds.clear()
    assert patrick.get(f"/review/cuts/{cut.id}").get_json()["ballot"] == "failed"
    seen = Observation.query.filter_by(kind=ObservationKind.PairingCheck).one()
    assert seen.detail["error"] == pairing.LOST
    assert build(patrick, cut).status_code == 202
    assert patrick.get(f"/review/cuts/{cut.id}").get_json()["ballot"] == "built"
