"""The chat route: the user's words in, one coach turn out."""


def test_no_chat_route_takes_a_mode(flask_app):
    # R-0015
    rules = [r.rule for r in flask_app.url_map.iter_rules() if r.rule.startswith("/app/chat")]
    assert rules == ["/app/chat"]
    assert [r for r in flask_app.url_map.iter_rules() if "mode" in r.rule] == []
