"""The meeting and the result screen: settling what the vote left open,
ratifying, and what the meeting produced."""

import datetime

import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot.pro.models import User
from btcopilot.review import divergence, export, ruledraft, snapshot
from btcopilot.review.models import Cut, Item, ReviewStatus, Rule, RuleSource
from btcopilot.tests.review.conftest import coded, person, shift

COACH = {"model": "claude-test", "prompt_version": 3}


@pytest.fixture
def coach_user(flask_app):
    user = User(username="coach@fd362.invalid", roles="subscriber")
    db.session.add(user)
    db.session.commit()
    return user


def three_readings(test_user, test_user_2, coach_user, cut):
    """Two people and the coach, each reading the same two moments: everyone
    has the first, the coach alone dates the second differently."""
    shared = shift(10, 1, "mother got sick")
    apart = shift(11, 1, "father left", "2021-06-01")
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shared, apart]})
    coded(
        test_user_2,
        cut,
        {"people": [person(1, "Ann")], "events": [dict(shared, id=20), apart]},
    )
    coded(
        coach_user,
        cut,
        {
            "people": [person(1, "Ann")],
            "events": [dict(shared, id=30), dict(apart, id=31, dateTime="2022-01-01")],
        },
        agent=COACH,
    )


def open_vote(patrick, cut):
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})


def settle_all(patrick, cut, choice="keep"):
    for item in list(db.session.get(Cut, cut.id).items):
        if item.status is not ReviewStatus.Disputed:
            continue
        patrick.patch(
            f"/review/items/{item.id}",
            json={
                "choice": choice,
                "value": {"coding_id": item.takes[0]["coding_id"]},
            },
        )


def test_the_coach_is_not_counted_as_a_coder(
    patrick, test_user, test_user_2, coach_user, cut
):
    three_readings(test_user, test_user_2, coach_user, cut)
    open_vote(patrick, cut)

    figures = db.session.get(Cut, cut.id).agreement["first_pass"]
    assert figures["codings"] == 2


def test_what_only_the_coach_read_differently_is_not_disputed(
    patrick, test_user, test_user_2, coach_user, cut
):
    """The two people wrote the second moment the same way; only the coach
    dated it otherwise, and that does not put it in front of the room."""
    three_readings(test_user, test_user_2, coach_user, cut)
    open_vote(patrick, cut)

    father = next(
        item
        for item in db.session.get(Cut, cut.id).items
        if any(t["item"].get("description") == "father left" for t in item.takes)
    )
    assert father.status is ReviewStatus.Agreed


def test_the_meeting_lists_people_as_well_as_events(
    patrick, test_user, test_user_2, cut
):
    """People and pair bonds never reach the ballot; they wait for the room."""
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": []})
    coded(test_user_2, cut, {"people": [person(1, "Ann"), person(2, "Bo")]})
    open_vote(patrick, cut)

    kinds = {
        item.item_kind.value
        for item in db.session.get(Cut, cut.id).items
        if item.status is ReviewStatus.Disputed
    }
    assert "person" in kinds


def test_names_are_on_the_meetings_reading_and_not_the_ballots(
    patrick, coder, test_user, test_user_2, cut
):
    three_takes = {"people": [person(1, "Ann")], "events": [shift(10, 1, "a shift")]}
    coded(test_user, cut, three_takes)
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)

    blind = coder.get(f"/review/items?cut_id={cut.id}").get_json()
    assert all("user_id" not in take for item in blind for take in item["takes"])
    named = patrick.get(f"/review/items?cut_id={cut.id}&named=true").get_json()
    assert any("user_id" in take for item in named for take in item["takes"])


def test_a_coder_cannot_ask_for_the_names(coder, test_user, test_user_2, cut):
    coded(test_user, cut, {"people": [person(1, "Ann")]})
    refused = coder.get(f"/review/items?cut_id={cut.id}&named=true")
    assert refused.status_code == 302


def test_the_tally_names_who_voted_which_way(
    patrick, coder, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    item = next(
        i
        for i in db.session.get(Cut, cut.id).items
        if i.status is ReviewStatus.Disputed and i.item_kind.value == "event"
    )
    coder.put(f"/review/items/{item.id}/vote", json={"choice": "drop"})

    tally = patrick.get(f"/review/tallies?cut_id={cut.id}").get_json()
    row = next(t for t in tally if t["review_item_id"] == item.id)
    assert row["counts"]["drop"] == 1
    assert row["votes"][0]["name"]


def test_ratify_waits_until_every_open_item_has_a_choice(
    patrick, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)

    refused = patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})
    assert refused.status_code == 400
    assert "still need a choice" in refused.get_data(as_text=True)
    assert db.session.get(Cut, cut.id).ratified_at is None

    settle_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})
    assert db.session.get(Cut, cut.id).ratified_at is not None


def test_an_item_marked_unresolved_is_kept_and_left_out_of_the_record(
    patrick, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    settle_all(patrick, cut, choice="unresolved")
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    assert result["unresolved"] >= 1
    assert Item.query.filter_by(
        cut_id=cut.id, status=ReviewStatus.Unresolved
    ).count() >= 1


def test_reopening_a_settled_item_puts_it_back_in_front_of_the_room(
    patrick, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    settle_all(patrick, cut)
    item = db.session.get(Cut, cut.id).items[0]
    patrick.patch(f"/review/items/{item.id}", json={"choice": "reopen"})

    assert db.session.get(Item, item.id).status is ReviewStatus.Disputed
    refused = patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})
    assert refused.status_code == 400


def test_both_agreement_figures_are_kept(patrick, test_user, test_user_2, cut):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    settle_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    assert result["first_pass"]["percent"] < result["after"]["percent"]


def test_what_every_coder_read_the_same_way_is_ratified_too(
    patrick, flask_app, test_user, test_user_2, cut
):
    """An agreed item is never argued over, so ratifying is what confirms it
    onto the record."""
    same = {"people": [person(1, "Ann")], "events": [shift(10, 1, "a shift")]}
    coded(test_user, cut, same)
    coded(test_user_2, cut, dict(same, events=[dict(same["events"][0], id=20)]))
    open_vote(patrick, cut)
    agreed = [
        item
        for item in db.session.get(Cut, cut.id).items
        if item.status is ReviewStatus.Agreed
    ]
    assert agreed
    assert all(item.item_id is None for item in agreed)

    settle_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    record = export.ratified_record(db.session.get(Cut, cut.id))
    assert record["people"]
    assert record["events"]


def test_the_result_scores_the_coachs_own_pass(
    patrick, test_user, test_user_2, coach_user, cut
):
    three_readings(test_user, test_user_2, coach_user, cut)
    open_vote(patrick, cut)
    settle_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    assert result["coach"]["agent"] == COACH
    assert result["coach"]["events"] is not None


def test_where_the_coach_differed_is_written_once_at_ratification(
    patrick, test_user, test_user_2, coach_user, cut
):
    three_readings(test_user, test_user_2, coach_user, cut)
    open_vote(patrick, cut)
    settle_all(patrick, cut)
    with patch.object(divergence, "reasons", side_effect=lambda rows: rows):
        patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    assert any("father left" in row["label"] for row in result["differed"])


def test_a_rule_carries_the_settle_it_came_from(
    patrick, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    settle_all(patrick, cut)
    with patch.object(ruledraft, "draft", return_value={1: "Date a shift by its start"}):
        patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    rule = Rule.query.filter_by(drafted_by=RuleSource.Ai).one()
    assert rule.source["cut_id"] == cut.id
    assert rule.source["review_item_id"]
    assert rule.ratified_at is not None


def test_the_result_says_what_each_coder_tends_to_do(
    patrick, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    settle_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    left_out = {row["name"]: row["left_out"] for row in result["coders"]}
    assert max(left_out.values()) >= 1


def test_changing_a_take_rewords_the_same_moment(patrick, test_user, test_user_2, cut):
    """A change is a rewording, not a second event beside the first: it lands
    on the moment the takes already name."""
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    item = next(
        i
        for i in db.session.get(Cut, cut.id).items
        if i.status is ReviewStatus.Disputed and i.item_kind.value == "event"
    )
    written = dict(item.takes[0]["item"], description="what the room said")
    written.pop("id")
    patrick.patch(
        f"/review/items/{item.id}", json={"choice": "change", "value": written}
    )

    assert db.session.get(Item, item.id).item_id == "10"


def test_a_settle_the_record_refuses_is_the_rooms_fault(
    patrick, test_user, test_user_2, cut
):
    """A shift with no variable is refused in the record's own words, not as a
    server error."""
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    item = next(
        i
        for i in db.session.get(Cut, cut.id).items
        if i.status is ReviewStatus.Disputed and i.item_kind.value == "event"
    )
    bare = {k: v for k, v in item.takes[0]["item"].items() if k != "symptom"}
    refused = patrick.patch(
        f"/review/items/{item.id}", json={"choice": "change", "value": bare}
    )
    assert refused.status_code == 400
    assert "variable" in refused.get_data(as_text=True)


def test_a_cut_that_is_not_ratified_has_no_result(patrick, cut):
    refused = patrick.get(f"/review/result?cut_id={cut.id}")
    assert refused.status_code == 400


def test_every_contributor_can_read_the_result(
    patrick, coder, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    settle_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    assert coder.get(f"/review/result?cut_id={cut.id}").status_code == 200


def test_a_ratified_cut_cannot_be_settled_again(patrick, test_user, test_user_2, cut):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    settle_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    item = db.session.get(Cut, cut.id).items[0]
    refused = patrick.patch(f"/review/items/{item.id}", json={"choice": "unresolved"})
    assert refused.status_code == 400
