import re
from pathlib import Path

import pytest

from btcopilot.personal.models import ProductEvent
from btcopilot.personal.productevents import Feature, Screen
from btcopilot.tests.chat.personal.conftest import csrf_token

TRACK = Path(__file__).parents[4] / "web" / "src" / "track.ts"


@pytest.fixture(autouse=True)
def no_auto_auth(monkeypatch):
    monkeypatch.delenv("FLASK_AUTO_AUTH_USER", raising=False)


def post(web, *events):
    return web.post(
        "/app/product-events",
        json={"session_id": "page1", "events": list(events)},
        headers={"X-CSRFToken": csrf_token(web)},
    )


def event(**over):
    return {
        "screen": Screen.Chat.value,
        "name": Feature.SendMessage.value,
        "at": "2026-09-22T10:00:00.000Z",
    } | over


def test_events_are_stored_with_user_and_session(web, test_user):
    # R-0077
    response = post(
        web,
        event(),
        event(
            screen=Screen.Menu.value,
            name=Feature.ChipTap.value,
            item_kind="person",
            item_id="7",
            diagram_id=test_user.free_diagram_id,
        ),
    )
    assert response.status_code == 201
    assert response.json == {"stored": 2}
    rows = ProductEvent.query.order_by(ProductEvent.id).all()
    assert [
        (r.user_id, r.session_id, r.screen, r.name, r.item_kind, r.item_id, r.diagram_id)
        for r in rows
    ] == [
        (test_user.id, "page1", "chat", "send_message", None, None, None),
        (test_user.id, "page1", "menu", "chip_tap", "person", "7", test_user.free_diagram_id),
    ]
    assert rows[0].client_at.isoformat() == "2026-09-22T10:00:00"


@pytest.mark.parametrize("bad", [{"screen": "nowhere"}, {"name": "nothing"}])
def test_an_unknown_screen_or_name_is_refused(web, bad):
    # R-0453
    response = post(web, event(), event(**bad))
    assert response.status_code == 400
    assert ProductEvent.query.count() == 0


def enum_values(source: str, name: str) -> set[str]:
    body = re.search(rf"export enum {name} \{{(.*?)\}}", source, re.S).group(1)
    return set(re.findall(r'= "(\w+)"', body))


def test_web_and_server_name_the_same_screens_and_features():
    # R-0077
    source = TRACK.read_text()
    assert enum_values(source, "Screen") == {s.value for s in Screen}
    assert enum_values(source, "Feature") == {f.value for f in Feature}
