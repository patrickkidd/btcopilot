import datetime

from btcopilot.extensions import db
from btcopilot.personal.models import Author, Change
from mock import patch

from btcopilot.review import export, ruledraft, snapshot
from btcopilot.review.freeze import frozen
from btcopilot.review.models import Coding, Cut, Item, ReviewStatus, Rule, RuleSource
from btcopilot.tests.review.conftest import coded, person, shift


def test_cut_starts_after_the_previous_one(patrick, session, turns, cut):
    made = patrick.post(
        "/review/cuts",
        json={"discussion_id": session.id, "end_statement_id": turns[3].id},
    )
    assert made.status_code == 201
    assert made.get_json()["start_statement_id"] == turns[2].id


def test_first_cut_starts_at_the_first_turn(patrick, session, turns):
    made = patrick.post(
        "/review/cuts",
        json={"discussion_id": session.id, "end_statement_id": turns[1].id},
    )
    assert made.get_json()["start_statement_id"] == turns[0].id


def test_an_overlapping_window_is_refused(patrick, session, turns, cut):
    made = patrick.post(
        "/review/cuts",
        json={
            "discussion_id": session.id,
            "start_statement_id": turns[1].id,
            "end_statement_id": turns[3].id,
        },
    )
    assert made.status_code == 400
    assert f"overlaps cut {cut.id}" in made.get_data(as_text=True)


def test_a_coder_cannot_open_the_vote(coder, cut):
    """A refused role lands on the login page, which is how this app says no."""
    refused = coder.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    assert refused.status_code == 302
    assert db.session.get(Cut, cut.id).vote_opened_at is None


def test_coding_reuses_the_coders_record_from_the_last_cut(
    coder, test_user_2, session, turns, cut
):
    first = coder.post("/review/codings", json={"cut_id": cut.id}).get_json()
    later = Cut(
        discussion_id=session.id,
        start_statement_id=turns[2].id,
        end_statement_id=turns[3].id,
        user_id=test_user_2.id,
    )
    db.session.add(later)
    db.session.commit()

    second = coder.post("/review/codings", json={"cut_id": later.id}).get_json()
    assert second["diagram_id"] == first["diagram_id"]


def test_done_freezes_the_coders_record(coder, cut):
    coding = coder.post("/review/codings", json={"cut_id": cut.id}).get_json()
    assert not frozen(coding["diagram_id"])

    coder.patch(f"/review/codings/{coding['id']}", json={"done_at": True})
    assert frozen(coding["diagram_id"])


def test_a_coder_sees_no_one_elses_coding_until_their_own_is_done(
    coder, test_user, test_user_2, cut
):
    coded(test_user, cut, {"people": [person(1, "Ann")]})
    mine = coder.post("/review/codings", json={"cut_id": cut.id}).get_json()
    assert len(coder.get(f"/review/codings?cut_id={cut.id}").get_json()) == 1

    coder.patch(f"/review/codings/{mine['id']}", json={"done_at": True})
    assert len(coder.get(f"/review/codings?cut_id={cut.id}").get_json()) == 2


def test_names_are_hidden_on_codings_until_ratification(coder, test_user, cut):
    coded(test_user, cut, {"people": [person(1, "Ann")]})
    mine = coder.post("/review/codings", json={"cut_id": cut.id}).get_json()
    coder.patch(f"/review/codings/{mine['id']}", json={"done_at": True})

    listed = coder.get(f"/review/codings?cut_id={cut.id}").get_json()
    assert all("user_id" not in row for row in listed)


def two_codings(test_user, test_user_2, cut):
    """Both coders wrote down the same shift; only one wrote the second."""
    shared = shift(10, 1, "mother got sick")
    a = coded(
        test_user,
        cut,
        {"people": [person(1, "Ann")], "events": [shared]},
    )
    b = coded(
        test_user_2,
        cut,
        {
            "people": [person(1, "Ann")],
            "events": [dict(shared, id=20), shift(21, 1, "father left", "2021-06-01")],
        },
    )
    return a, b


def disputed_event(cut) -> Item:
    """What a ballot screen is about: one disputed event of the cut."""
    return next(
        i
        for i in Item.query.filter_by(cut_id=cut.id, item_kind="event").all()
        if i.status is ReviewStatus.Disputed
    )


def test_snapshot_marks_the_shared_event_agreed_and_the_lone_one_disputed(
    patrick, test_user, test_user_2, cut
):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})

    events = Item.query.filter_by(cut_id=cut.id, item_kind="event").all()
    statuses = sorted(i.status for i in events)
    assert statuses == [ReviewStatus.Agreed, ReviewStatus.Disputed]
    assert len(next(i for i in events if i.status is ReviewStatus.Agreed).takes) == 2


def test_agreement_lands_on_the_cut(patrick, test_user, test_user_2, cut):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})

    agreement = db.session.get(Cut, cut.id).agreement
    assert agreement["codings"] == 2
    assert agreement["by_status"]["disputed"] >= 1


def test_one_vote_per_coder_per_item(patrick, coder, test_user, test_user_2, cut):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    item = disputed_event(cut)

    coder.put(f"/review/items/{item.id}/vote", json={"choice": "take"})
    coder.put(f"/review/items/{item.id}/vote", json={"choice": "drop"})
    votes = coder.get(f"/review/votes?cut_id={cut.id}").get_json()
    assert len(votes) == 1
    assert votes[0]["choice"] == "drop"


def test_a_coder_reads_only_their_own_votes(patrick, coder, test_user, test_user_2, cut):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    item = disputed_event(cut)
    patrick.put(f"/review/items/{item.id}/vote", json={"choice": "take"})

    assert coder.get(f"/review/votes?cut_id={cut.id}").get_json() == []
    tallies = patrick.get(f"/review/tallies?cut_id={cut.id}").get_json()
    counted = next(t for t in tallies if t["review_item_id"] == item.id)
    assert counted["counts"]["take"] == 1


def test_settle_writes_a_change_on_the_case_record(
    patrick, test_user, test_user_2, case, cut
):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    item = next(
        i
        for i in Item.query.filter_by(cut_id=cut.id, item_kind="event").all()
        if i.status is ReviewStatus.Agreed
    )

    settled = patrick.patch(
        f"/review/items/{item.id}",
        json={"choice": "keep", "value": {"coding_id": item.takes[0]["coding_id"]}},
    )
    assert settled.status_code == 200

    row = db.session.get(Item, item.id)
    assert row.status is ReviewStatus.Settled
    assert row.item_id is not None
    change = db.session.get(Change, row.settle_change_id)
    assert change.author is Author.Review
    assert change.diagram_id == case.id


def test_ratifying_writes_the_ground_truth_export(
    patrick, flask_app, test_user, test_user_2, cut
):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    item = next(
        i
        for i in Item.query.filter_by(cut_id=cut.id, item_kind="event").all()
        if i.status is ReviewStatus.Agreed
    )
    patrick.patch(
        f"/review/items/{item.id}",
        json={"choice": "keep", "value": {"coding_id": item.takes[0]["coding_id"]}},
    )
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})

    written = export.path_for(db.session.get(Cut, cut.id))
    assert written.exists()
    cases = export.cases(db.session.get(Cut, cut.id))
    assert cases[0]["gt_extraction"]["events"]


def test_ratifying_asks_the_coach_for_a_first_draft_of_the_rules(
    patrick, no_coach, test_user, test_user_2, cut
):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    patrick.patch(f"/review/cuts/{cut.id}", json={"ratified_at": True})
    assert no_coach.called


def test_the_coachs_draft_lands_as_ai_rules(patrick, test_user, test_user_2, cut):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    item = Item.query.filter_by(cut_id=cut.id, item_kind="event").first()
    item.status = ReviewStatus.Settled
    db.session.commit()

    with patch.object(ruledraft, "draft", return_value=["Date a shift by its start"]):
        ruledraft.draft_for(db.session.get(Cut, cut.id))
    db.session.commit()
    drafted = Rule.query.filter_by(drafted_by=RuleSource.Ai).all()
    assert [r.text for r in drafted] == ["Date a shift by its start"]


def test_a_post_without_a_csrf_token_is_refused(flask_app, patrick, session, turns):
    flask_app.config["WTF_CSRF_METHODS"] = ["POST"]
    refused = patrick.post(
        "/review/cuts",
        json={"discussion_id": session.id, "end_statement_id": turns[1].id},
    )
    assert refused.status_code == 400
    assert "CSRF" in refused.get_data(as_text=True)


def test_a_rule_is_flagged_and_the_flag_closed(coder):
    made = coder.post("/review/rules", json={"text": "Date a shift by when it began"})
    rule_id = made.get_json()["id"]

    coder.patch(f"/review/rules/{rule_id}", json={"flag": True, "reason": "unclear"})
    assert db.session.get(Rule, rule_id).open_flags()

    coder.patch(f"/review/rules/{rule_id}", json={"close_flag": True})
    assert not db.session.get(Rule, rule_id).open_flags()


def test_the_agenda_gathers_what_the_meeting_must_take_up(
    patrick, coder, test_user, test_user_2, cut
):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    item = Item.query.filter_by(cut_id=cut.id).first()
    patrick.patch(f"/review/items/{item.id}", json={"choice": "unresolved"})
    rule = coder.post("/review/rules", json={"text": "A rule to look at"}).get_json()
    coder.patch(f"/review/rules/{rule['id']}", json={"flag": True})
    later = Cut(
        discussion_id=cut.discussion_id,
        start_statement_id=cut.start_statement_id,
        end_statement_id=cut.end_statement_id,
        user_id=test_user.id,
    )
    db.session.add(later)
    db.session.commit()
    unfinished = coded(test_user_2, later, {}, done=False)

    agenda = patrick.get("/review/agenda").get_json()
    assert [i["id"] for i in agenda["unresolved_items"]] == [item.id]
    assert [r["id"] for r in agenda["flagged_rules"]] == [rule["id"]]
    assert unfinished.id in [c["id"] for c in agenda["unfinished_codings"]]


def test_the_coachs_replay_is_a_coding_with_its_model(patrick, test_user, cut):
    coding = Coding(
        cut_id=cut.id,
        user_id=test_user.id,
        diagram_id=test_user.free_diagram_id,
        agent={"model": "claude-sonnet-5", "prompt_version": "7"},
        done_at=datetime.datetime.utcnow(),
    )
    db.session.add(coding)
    db.session.commit()

    assert snapshot.done_codings(db.session.get(Cut, cut.id)) == [coding]
    assert coding.agent["model"] == "claude-sonnet-5"


def test_the_table_says_what_each_coder_is_doing(patrick, coder, cut, test_user_2):
    """Patrick has not started; the other coder has a coding under way."""
    coder.post("/review/codings", json={"cut_id": cut.id})
    rows = patrick.get("/review/coders").get_json()
    by_id = {row["user_id"]: row for row in rows}
    assert by_id[patrick.user.id]["state"] == "not started"
    assert by_id[test_user_2.id]["state"] == "coding"
    assert by_id[patrick.user.id]["name"] == "you"


def test_a_coder_who_pressed_done_reads_as_done(patrick, test_user_2, cut):
    coded(test_user_2, cut, {})
    rows = patrick.get("/review/coders").get_json()
    assert {r["user_id"]: r["state"] for r in rows}[test_user_2.id] == "done"
    assert not any(row["closed_out"] for row in rows)


def test_taking_a_conversation_off_the_table(patrick, cut):
    gone = patrick.delete(f"/review/cuts/{cut.id}")
    assert gone.status_code == 200
    assert db.session.get(Cut, cut.id) is None


def test_a_cut_someone_started_cannot_be_taken_off_the_table(patrick, coder, cut):
    coder.post("/review/codings", json={"cut_id": cut.id})
    refused = patrick.delete(f"/review/cuts/{cut.id}")
    assert refused.status_code == 400
    assert "already started" in refused.get_data(as_text=True)
    assert db.session.get(Cut, cut.id) is not None


def test_a_cut_cannot_be_placed_before_the_last_ratified_one(
    patrick, session, turns, cut
):
    cut.ratified_at = datetime.datetime.utcnow()
    db.session.commit()
    refused = patrick.post(
        "/review/cuts",
        json={"discussion_id": session.id, "end_statement_id": turns[0].id},
    )
    assert refused.status_code == 400
    assert "already ratified" in refused.get_data(as_text=True)


def test_a_nudge_reaches_everyone_not_done(patrick, coder, test_user_2, cut):
    coder.post("/review/codings", json={"cut_id": cut.id})
    with patch("btcopilot.review.routes.nudges.send_nudge") as sent:
        made = patrick.post("/review/nudges", json={})
    assert made.status_code == 201
    assert made.get_json()["nudged"] == [patrick.user.id, test_user_2.id]
    assert sent.call_count == 2
    assert db.session.get(Cut, cut.id).nudged_at is not None


def test_a_coder_cannot_nudge(coder, cut):
    refused = coder.post("/review/nudges", json={})
    assert refused.status_code == 302


def test_the_turns_of_a_session_carry_the_ratified_line(patrick, session, turns, cut):
    cut.ratified_at = datetime.datetime.utcnow()
    db.session.commit()
    read = patrick.get(f"/review/turns?discussion_id={session.id}").get_json()
    assert len(read["turns"]) == len(turns)
    assert read["agreed"]["statement_id"] == turns[1].id
    assert read["on_table"] is None


def test_a_coder_cannot_read_a_session_whole(coder, session):
    refused = coder.get(f"/review/turns?discussion_id={session.id}")
    assert refused.status_code == 302


def wrote_from(coding, event_id: int, statement_id: int, user_id: int):
    """The coder's record stamped with the turn one event was written from."""
    db.session.add(
        Change(
            diagram_id=coding.diagram_id,
            statement_id=statement_id,
            turn_id=f"turn-{statement_id}",
            user_id=user_id,
            author=Author.Review,
            deltas=[
                {
                    "item_kind": "event",
                    "item_id": str(event_id),
                    "field": "description",
                    "after": "said so",
                }
            ],
        )
    )
    db.session.commit()


def test_the_ballot_carries_the_turn_and_the_person_of_each_take(
    patrick, test_user, test_user_2, cut, turns
):
    first, _ = two_codings(test_user, test_user_2, cut)
    wrote_from(first, 10, turns[1].id, test_user.id)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})

    rows = patrick.get(f"/review/items?cut_id={cut.id}").get_json()
    agreed = next(
        r for r in rows if r["item_kind"] == "event" and r["status"] == "agreed"
    )
    assert agreed["coders"] == 2
    assert agreed["not_coded"] == 0
    assert agreed["takes"][0]["person_name"] == "Ann"
    assert agreed["takes"][0]["statement_id"] == turns[1].id
    assert agreed["line"]["text"] == "turn 1"
    assert [one["name"] for one in agreed["people"]] == ["Ann"]


def test_an_item_one_coder_left_out_says_how_many_left_it_out(
    patrick, test_user, test_user_2, cut
):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})

    rows = patrick.get(f"/review/items?cut_id={cut.id}").get_json()
    lone = next(
        r for r in rows if r["item_kind"] == "event" and r["status"] == "disputed"
    )
    assert lone["not_coded"] == 1


def test_no_name_reaches_the_ballot(patrick, test_user, test_user_2, cut):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})

    rows = patrick.get(f"/review/items?cut_id={cut.id}").get_json()
    assert all("user_id" not in row for row in rows)
    assert all("user_id" not in take for row in rows for take in row["takes"])


def test_an_agreed_item_cannot_be_voted_on(patrick, test_user, test_user_2, cut):
    two_codings(test_user, test_user_2, cut)
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})
    agreed = next(
        i
        for i in Item.query.filter_by(cut_id=cut.id, item_kind="event").all()
        if i.status is ReviewStatus.Agreed
    )

    refused = patrick.put(f"/review/items/{agreed.id}/vote", json={"choice": "take"})
    assert refused.status_code == 400
    assert "not on the ballot" in refused.get_data(as_text=True)


def test_the_vote_task_goes_when_every_disputed_event_has_a_vote(
    patrick, coder, test_user, test_user_2, cut
):
    two_codings(test_user, test_user_2, cut)
    coder.post("/review/codings", json={"cut_id": cut.id})
    mine = Coding.query.filter_by(cut_id=cut.id, user_id=coder.user.id).first()
    mine.done_at = datetime.datetime.utcnow()
    db.session.commit()
    patrick.patch(f"/review/cuts/{cut.id}", json={"vote_opened_at": True})

    card = coder.get("/review/tasks").get_json()["task"]
    assert card["kind"] == "vote"
    assert card["ready"]

    for item in Item.query.filter_by(cut_id=cut.id, item_kind="event").all():
        if item.status is ReviewStatus.Disputed:
            coder.put(f"/review/items/{item.id}/vote", json={"choice": "drop"})
    assert coder.get("/review/tasks").get_json()["task"] is None
