"""Test journal import ID separation: person IDs and event IDs must not collide."""

import pytest

from btcopilot.pro.models import Diagram


SYNTHETIC_JOURNAL = """
Timeline Journal

- March 5 - stressed with neighborhood committee's constant email chain about parking rules
- March 6 - withdrew from committee chair role, argument with Derek at the community center. Should reduce stress. Willing to step back from group politics.
- March 6-20 - A(span): Alex lingering frustration from Committee / Derek situation
- March 15 - Committee meeting went OK, Derek led it, Alex stayed quiet in back
- Rachel functioning UP; clarity of supporting Alex through stress (reciprocity pattern?)
- March 16-17 - Work stress from project deadline. Relieved on March 17 after Marcus moved deployment responsibility to London team. Watching for underlying stress
- March 18, relieved that a water main break cancelled mandatory office day
- March 18, Alex back pain flared suddenly and didn't sleep much
- March 19, S: Up - Alex stays home instead of joining Rachel and parents at lake cabin. Requires pain medication plus sleep aid to rest
- March 20, Alex tries 45min yoga, commits again to less coffee, more exercise, more therapy work, reducing overall tension (slept poorly)
- March 21 - S: Up - Alex slept poorly, but mentally adjusted well to it
- March 22, Anxiety from Marcus mentioning potential future choice of relocating for company or finding new job (slept well)
- April 10
    - Conflict: Alex upset at Rachel for telling Karen "when will you two have kids?" story and Rachel finding it funny. Alex threat sensitivity up about everyone asking. Alex frustrated after explaining 4 times why that's not OK.
    - Triangle: Alex moved outside while Rachel / Karen stayed inside
    - Reciprocity: Rachel not understanding, Alex over-explaining repeatedly
- April 12: Disagreement about Alex wanting Rachel to handle house maintenance issues independently
- April 12-13: S: up, Rachel. Poor sleep
- April 14: S: Down, Rachel. Better sleep after visiting Susan's place
- April 28: A: Up, Alex. Marcus tells Alex he's responsible for all product outcomes.
- April 29: A: Max, Alex. Full workload lands on Alex
- April 30: S: Up, Alex & Rachel. insomnia, Alex woke at 3am, Rachel only 4 hours
- May 1: S: Up, Rachel. Insomnia
- May 2: A, S, R: up. Windy weather. Alex snapped hard at Rachel in front of neighbors about yard work. Later small tension made Rachel cry. Alex had to leave BBQ to console her. Left neighborhood early, talked through it well. Will plan to prevent that. Venting a lot against Derek.
- May 3: S up (Rachel), A: up (Alex) - Tony call with complicated dynamics about James, asking if Alex/James "are speaking" about their relationship, fear of spreading to Victor
- June 1: Symptom up, Relationship: Triangle. Alex reacts strongly to Rachel's comment that her family always does airport pickups for weddings, where Frank said shuttles make more sense. Interlocking triangles: Alex felt outside along with his family, Rachel and her family on inside. Alex always feels outside with Frank and Linda/Tom, connecting to feeling outside with his Parents after their divorce. Complex but clear. Rachel apologized early, Alex biked then apologized later, negative mood lasted into evening.
- June 10: Alex: A: up, S: up. Found out must relocate or accept severance. Only slept few hours with medication. Sat for 60 minutes, committing to 60min twice daily, no alcohol. Starting research and job applications
- June 25: S up, A up, Thomas Greene killed in accident. Alex shocked, compares to historical tragedy. Does not sleep much
- July 5: S: up (sleep), having flu
- July 6-7: S: same (sleep), visiting Portland
- July 8-10: S: same (sleep), at Beth's wedding in Denver
- July 11: S: down, at home. Still some flu, took sleep aid
- August 3: Start fertility treatment injections
- August 7: Conflict: A->R. Call from clinic about test results. Emotional content for Alex, thinking about parents divorce, feeling something missing, uncertainty about future
- August 15: Nice dinner with Tom, Linda, Victor, Rachel, Alex at Tom's in Bellevue. Calm and good. Maybe first time relaxed.
- August 18: Alex renewed intention to no alcohol + meditate. Thinking about no more trips planned
- August 22: got news that treatment cycle failed
- August 23: A: up, F: up. Alex told father about treatment failure, no plans to continue. Alex said it was "pretty emotional for both of us." Frank said either path can be great. Overall very good frank conversation. At local bar, had beers.
- August 26: Alex has lunch with mother and discusses treatment. Takes lot of energy but awareness and control maintained. Jason showed up with his family drama. Alex left in controlled way but couldn't sail through it easily.
- August 27: S: down (mood, insomnia), F: up - workout, work productivity
- October 15/25: A up - Rachel / Alex anticipating Keith/Alex tension from beach trip last year.
- October 16: S up - Alex
- October 16: S up, R: distance - Alex @ Keith and Emma's
- October 17: S same, R distance - Alex
- October 18: Alex: S down, A down, Rachel: F down. Alex and Rachel bail on plans with Keith and Emma, citing Alex's poor sleep. The 6 hour drive from mountains was full of heavy topic talks. Alex learns he doesn't remember anyone being in his corner after Frank and Emma both suggested Rachel should "stick together" rather than stay at resort, and Rachel agreeing - Alex pulls over and cries hard. This brings calming though emotional clarity. Rachel breaks down later after feeling pinched by Alex about friends and group trips. Alex asks if she was ever depressed when single and Rachel said often. Rachel sleeps without affection and Alex sleeps on couch to avoid fourth sleepless night. Alex feels better view of Rachel's baseline emotional state and resolves to reflect on this as priority - feels dark, some nervousness about their relationship. Probably the most emotional incident so far.
- October 19
"""


@pytest.mark.e2e
def test_journal_import_person_event_id_separation(subscriber):
    """
    Test that LLM correctly separates person IDs from event IDs.

    This catches a bug where the LLM:
    1. Assigned person IDs -1 through -N
    2. Started event IDs at -(N+1)
    3. Then incorrectly used -(N+1) as a person reference in later events

    The fix requires the prompt to clearly instruct the LLM to:
    - Use one ID sequence for people (e.g., -1, -2, -3...)
    - Use a separate ID sequence for events (e.g., -100, -101, -102... or continue from lowest person ID)
    - Never reference an event ID as a person ID
    """
    diagram = subscriber.user.free_diagram

    response = subscriber.post(
        f"/personal/diagrams/{diagram.id}/import-text",
        json={"text": SYNTHETIC_JOURNAL},
    )

    # The import should succeed without validation errors
    assert response.status_code == 200, f"Import failed: {response.get_json()}"

    data = response.get_json()
    assert data["success"] is True, f"Import not successful: {data}"

    summary = data["summary"]
    assert (
        summary["people"] >= 5
    ), f"Expected at least 5 people, got {summary['people']}"
    assert (
        summary["events"] >= 20
    ), f"Expected at least 20 events, got {summary['events']}"

    pdp = data.get("pdp", {})
    person_ids = {p["id"] for p in pdp.get("people", [])}
    event_ids = {e["id"] for e in pdp.get("events", [])}

    overlap = person_ids & event_ids
    assert (
        not overlap
    ), f"ID collision! These IDs are used for both people and events: {overlap}"

    invalid_refs = []
    for event in pdp.get("events", []):
        person_ref = event.get("person")
        if person_ref is not None and person_ref < 0:
            if person_ref not in person_ids:
                invalid_refs.append(
                    {
                        "event_id": event["id"],
                        "event_desc": event.get("description", "")[:40],
                        "invalid_person_ref": person_ref,
                    }
                )

    assert not invalid_refs, (
        f"Events reference non-existent PDP people. "
        f"This indicates the LLM confused event IDs with person IDs. "
        f"First few: {invalid_refs[:5]}"
    )

    diagram_reload = Diagram.query.get(diagram.id)
    assert diagram_reload is not None
    diagram_data = diagram_reload.get_diagram_data()
    assert len(diagram_data.pdp.people) > 0
    assert len(diagram_data.pdp.events) > 0


@pytest.mark.e2e
def test_journal_import_user_reference_preserved(subscriber):
    """
    Test that events about the primary user correctly reference person ID 1.

    The journal describes many events about "Alex" who is the primary user.
    These should reference the committed User (ID 1), not create a new person.
    """
    diagram = subscriber.user.free_diagram

    # Shorter journal focusing on user events
    short_journal = """
    Timeline Journal

    - March 5 - I was stressed with committee emails
    - March 6 - I withdrew from chair role, had argument with Derek
    - March 18 - My back pain flared and I didn't sleep much
    - March 19 - I stayed home instead of going to cabin with family. Required sleep aid.
    - March 20 - I tried yoga and committed to less coffee
    - April 10 - I was upset at my spouse about a comment at dinner
    - April 12-13 - Poor sleep for me
    """

    response = subscriber.post(
        f"/personal/diagrams/{diagram.id}/import-text",
        json={"text": short_journal},
    )

    assert response.status_code == 200, f"Import failed: {response.get_json()}"

    data = response.get_json()
    pdp = data.get("pdp", {})

    user_events = [e for e in pdp.get("events", []) if e.get("person") == 1]
    assert len(user_events) >= 4, (
        f"Expected most events to reference User (ID 1), but only {len(user_events)} do. "
        f"The LLM may be creating a new person instead of using the existing User."
    )
