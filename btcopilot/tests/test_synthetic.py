from btcopilot.tests.conftest import wrote
from btcopilot.tests.synthetic import AttachmentStyle, Persona, Turn, simulate_user_response


def test_the_simulated_client_speaks_the_words_of_the_metered_reply(monkeypatch):
    # R-0409
    said = "My sister Nell moved out west when I was twelve years old."
    monkeypatch.setattr(
        "btcopilot.tests.synthetic.gemini_text_sync", lambda *a, **k: wrote(said)
    )
    persona = Persona("Ann", "A teacher.", AttachmentStyle.Secure)
    reply = simulate_user_response(persona, [Turn("ai", "Who is in your family?")], 1)
    assert reply == said
