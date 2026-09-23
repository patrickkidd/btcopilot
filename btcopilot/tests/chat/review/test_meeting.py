"""The meeting and the result screen: deciding what the vote left open,
ratifying, and what the meeting produced."""

import datetime

import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot.models import User
from btcopilot.review import divergence, export, ruledraft, snapshot
from btcopilot.review.models import Cut, Item, ReviewStatus, Rule, RuleSource
from btcopilot.tests.chat.review.conftest import coded, person, shift

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


def decide_all(patrick, cut, choice="keep"):
    for item in list(db.session.get(Cut, cut.id).items):
        if item.status is not ReviewStatus.Disputed:
            continue
        patrick.patch(
            f"/review/items/{item.id}",
            json={
                "choice": choice,
                "value": {"coding_id": item.opinions[0]["coding_id"]},
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
        if any(t["item"].get("description") == "father left" for t in item.opinions)
    )
    assert father.status is ReviewStatus.Agreed


def test_the_meeting_lists_people_as_well_as_events(
    patrick, test_user, test_user_2, cut
):
    """People and bonds are read before the events, on the ballot and in the
    meeting alike (R-0326)."""
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
    three_opinions = {"people": [person(1, "Ann")], "events": [shift(10, 1, "a shift")]}
    coded(test_user, cut, three_opinions)
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)

    blind = coder.get(f"/review/items?cut_id={cut.id}").get_json()
    assert all("user_id" not in opinion for item in blind for opinion in item["opinions"])
    named = patrick.get(f"/review/items?cut_id={cut.id}&named=true").get_json()
    assert any("user_id" in opinion for item in named for opinion in item["opinions"])


def test_the_kept_version_is_read_back_on_a_later_reading(
    patrick, test_user, test_user_2, cut
):
    """Which coder's version the room kept is on the item itself, so a decided
    item opens with that row lit long after the meeting (R-0339). Writing one
    out or leaving it unresolved keeps nothing lit."""
    three_readings_users(test_user, test_user_2, cut)
    open_vote(patrick, cut)
    item = next(
        one
        for one in db.session.get(Cut, cut.id).items
        if one.status is ReviewStatus.Disputed and one.item_kind.value == "event"
    )
    coding_id = item.opinions[0]["coding_id"]

    patrick.patch(
        f"/review/items/{item.id}",
        json={"choice": "keep", "value": {"coding_id": coding_id}},
    )
    rows = patrick.get(f"/review/items?cut_id={cut.id}&named=true").get_json()
    read = next(one for one in rows if one["id"] == item.id)
    assert read["kept_coding_id"] == coding_id

    patrick.patch(f"/review/items/{item.id}", json={"choice": "unresolved"})
    assert db.session.get(Item, item.id).kept_coding_id is None


def test_the_kept_version_is_not_on_the_blind_reading(
    patrick, coder, test_user, test_user_2, cut
):
    three_readings_users(test_user, test_user_2, cut)
    open_vote(patrick, cut)
    blind = coder.get(f"/review/items?cut_id={cut.id}").get_json()
    assert all("kept_coding_id" not in one for one in blind)


def three_readings_users(test_user, test_user_2, cut):
    """Two coders on the same moment, dated differently, so it is disputed."""
    coded(
        test_user,
        cut,
        {"people": [person(1, "Ann")], "events": [shift(10, 1, "a shift", "2021-06-01")]},
    )
    coded(
        test_user_2,
        cut,
        {"people": [person(1, "Ann")], "events": [shift(10, 1, "a shift", "2022-01-01")]},
    )


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

    decide_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})
    assert db.session.get(Cut, cut.id).ratified_at is not None


def test_an_item_marked_unresolved_is_kept_and_left_out_of_the_record(
    patrick, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    decide_all(patrick, cut, choice="unresolved")
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    assert result["unresolved"] >= 1
    assert Item.query.filter_by(
        cut_id=cut.id, status=ReviewStatus.Unresolved
    ).count() >= 1


def test_reopening_a_decided_item_puts_it_back_in_front_of_the_room(
    patrick, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    decide_all(patrick, cut)
    item = db.session.get(Cut, cut.id).items[0]
    patrick.patch(f"/review/items/{item.id}", json={"choice": "reopen"})

    assert db.session.get(Item, item.id).status is ReviewStatus.Disputed
    refused = patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})
    assert refused.status_code == 400


def test_both_agreement_figures_are_kept(patrick, test_user, test_user_2, cut):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    decide_all(patrick, cut)
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

    decide_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    record = export.ratified_record(db.session.get(Cut, cut.id))
    assert record["people"]
    assert record["events"]


def test_the_result_scores_the_coachs_own_pass(
    patrick, test_user, test_user_2, coach_user, cut
):
    three_readings(test_user, test_user_2, coach_user, cut)
    open_vote(patrick, cut)
    decide_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    assert result["coach"]["agent"] == COACH
    assert result["coach"]["events"] is not None


def test_a_cut_the_coach_never_coded_says_so_rather_than_scoring_it(
    patrick, test_user, test_user_2, cut
):
    """No score and no differences, so the screen can say the coach did not
    code this conversation instead of showing an empty space."""
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    decide_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    assert result["coach"] is None
    assert result["differed"] == []


def test_where_the_coach_differed_is_written_once_at_ratification(
    patrick, test_user, test_user_2, coach_user, cut
):
    three_readings(test_user, test_user_2, coach_user, cut)
    open_vote(patrick, cut)
    decide_all(patrick, cut)
    with patch.object(divergence, "reasons", side_effect=lambda rows: rows):
        patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    assert any("father left" in row["label"] for row in result["differed"])


def test_a_rule_carries_the_decision_it_came_from(
    patrick, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    decide_all(patrick, cut)
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
    decide_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    result = patrick.get(f"/review/result?cut_id={cut.id}").get_json()
    left_out = {row["name"]: row["left_out"] for row in result["coders"]}
    assert max(left_out.values()) >= 1


def test_changing_an_opinion_rewords_the_same_moment(patrick, test_user, test_user_2, cut):
    """A change is a rewording, not a second event beside the first: it lands
    on the moment the opinions already name."""
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    item = next(
        i
        for i in db.session.get(Cut, cut.id).items
        if i.status is ReviewStatus.Disputed and i.item_kind.value == "event"
    )
    written = dict(item.opinions[0]["item"], description="what the room said")
    written.pop("id")
    patrick.patch(
        f"/review/items/{item.id}", json={"choice": "change", "value": written}
    )

    assert db.session.get(Item, item.id).item_id == "10"


def test_a_person_can_be_decided_before_what_they_stand_on_is_ratified(
    patrick, test_user, test_user_2, cut
):
    """Keeping a person born to a bond the coders all read the same way puts
    that bond on the case first, so the record has what the person needs and
    the room is not refused (R-0326)."""
    shared = {
        "people": [person(1, "Ann"), person(2, "Bo"), person(3, "Cass")],
        "pair_bonds": [{"id": 20, "person_a": 1, "person_b": 2}],
    }
    coded(test_user, cut, shared)
    coded(
        test_user_2,
        cut,
        dict(shared, people=[person(1, "Ann"), person(2, "Bo"), dict(person(3, "Cass"), parents=20)]),
    )
    open_vote(patrick, cut)
    disputed = next(
        i
        for i in db.session.get(Cut, cut.id).items
        if i.status is ReviewStatus.Disputed and i.item_kind.value == "person"
    )
    born = next(
        o for o in disputed.opinions if o["item"].get("parents") is not None
    )

    kept = patrick.patch(
        f"/review/items/{disputed.id}",
        json={"choice": "keep", "value": {"coding_id": born["coding_id"]}},
    )
    assert kept.status_code == 200, kept.get_data(as_text=True)
    bond = next(
        i for i in db.session.get(Cut, cut.id).items if i.item_kind.value == "pair_bond"
    )
    assert bond.item_id is not None


def test_a_decision_the_record_refuses_is_the_rooms_fault(
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
    bare = {k: v for k, v in item.opinions[0]["item"].items() if k != "symptom"}
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
    decide_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    assert coder.get(f"/review/result?cut_id={cut.id}").status_code == 200


def test_a_ratified_cut_cannot_be_decided_again(patrick, test_user, test_user_2, cut):
    coded(test_user, cut, {"people": [person(1, "Ann")], "events": [shift(10, 1, "a")]})
    coded(test_user_2, cut, {"people": [person(1, "Ann")], "events": []})
    open_vote(patrick, cut)
    decide_all(patrick, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    item = db.session.get(Cut, cut.id).items[0]
    refused = patrick.patch(f"/review/items/{item.id}", json={"choice": "unresolved"})
    assert refused.status_code == 400
