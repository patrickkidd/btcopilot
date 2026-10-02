import json

from btcopilot.models import SyntheticPersona
from btcopilot.tests.conftest import wrote
from btcopilot.tests.synthetic import (
    AttachmentStyle,
    ClientRealismEvaluator,
    ConversationResult,
    DataCategory,
    Persona,
    PersonaTrait,
    Turn,
    generate_persona,
    simulate_user_response,
)


def test_the_simulated_client_speaks_the_words_of_the_metered_reply(monkeypatch):
    # R-0409
    said = "My sister Nell moved out west when I was twelve years old."
    monkeypatch.setattr(
        "btcopilot.tests.synthetic.gemini_text_sync", lambda *a, **k: wrote(said)
    )
    persona = Persona("Ann", "A teacher.", AttachmentStyle.Secure)
    reply = simulate_user_response(persona, [Turn("ai", "Who is in your family?")], 1)
    assert reply == said


def test_a_generated_persona_is_stored_whole_and_reads_back_as_a_client(
    flask_app, monkeypatch
):
    # R-0409
    answer = {
        "name": "Corwin",
        "background": "A carpenter, the younger of two brothers.",
        "presenting_problem": "I don't sleep.",
        "data_points": [{"category": "siblings", "keywords": ["brother", "Hale"]}],
    }
    prompts = []

    def model(prompt, **kwargs):
        prompts.append(prompt)
        return wrote(f"```json\n{json.dumps(answer)}\n```")

    monkeypatch.setattr("btcopilot.tests.synthetic.gemini_text_sync", model)
    stored = generate_persona(
        [PersonaTrait.Terse], AttachmentStyle.DismissiveAvoidant, "male", 41
    )
    assert "dismissive_avoidant" in prompts[0]
    assert SyntheticPersona.query.one() is stored
    assert (stored.name, stored.traits, stored.sex, stored.age) == (
        "Corwin",
        ["terse"],
        "male",
        41,
    )
    client = stored.to_persona()
    assert client.attachmentStyle is AttachmentStyle.DismissiveAvoidant
    assert [(p.category, p.keywords) for p in client.dataPoints] == [
        (DataCategory.Siblings, ["brother", "Hale"])
    ]


def test_the_realism_score_takes_the_models_reading_of_the_arc(monkeypatch):
    # R-0409
    prompts = []

    def model(prompt, **kwargs):
        prompts.append(prompt)
        return wrote('{"score": 0.9, "evidence": "Goes brief after the loss."}')

    monkeypatch.setattr("btcopilot.tests.synthetic.gemini_text_sync", model)
    turns = []
    for n in range(6):
        turns += [Turn("ai", "And then?"), Turn("user", f"We moved, year {n}.")]
    persona = Persona("Ann", "A teacher.", AttachmentStyle.Secure)
    scored = ClientRealismEvaluator().evaluate(ConversationResult(turns, persona))
    assert "Turn 6 (4 words): We moved, year 5." in prompts[0]
    assert (scored.emotionalArcScore, scored.emotionalArcEvidence) == (
        0.9,
        "Goes brief after the loss.",
    )
    assert scored.wordCountsPerTurn == [4] * 6
    assert 0.0 <= scored.score <= 1.0
