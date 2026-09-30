import json

from btcopilot.coacheval import evaluate_coach
from btcopilot.tests.conftest import wrote


def test_the_judge_reads_its_verdict_from_the_words_of_the_metered_reply(monkeypatch):
    # R-0409
    verdict = dict.fromkeys(
        (
            "current_events_engagement",
            "name_usage",
            "no_premature_pivot",
            "no_theory_pitch",
            "returns_to_collection",
        ),
        True,
    )
    verdict["notes"] = "fine"
    monkeypatch.setattr(
        "btcopilot.coacheval.gemini_text_sync",
        lambda *a, **k: wrote(json.dumps(verdict)),
    )
    scores = evaluate_coach([("user", "My sister is Nell."), ("coach", "Tell me more.")], ["Nell"])
    assert scores.name_usage is True
    assert scores.notes == "fine"
