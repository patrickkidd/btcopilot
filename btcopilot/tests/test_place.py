import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import flask.testing

from btcopilot import place
from btcopilot.place import Place

TABLE = Path(__file__).parents[2] / "web" / "src" / "place.ts"
OPENED = {"Sec-Fetch-Dest": "document"}


def test_web_and_server_share_one_table_of_addresses():
    # R-0055
    body = re.search(r"export enum Place \{(.*?)\}", TABLE.read_text(), re.S).group(1)
    assert dict(re.findall(r'(\w+) = "([^"]*)"', body)) == {p.name: p.value for p in Place}


def test_an_address_reads_back_as_its_place_and_values():
    # R-0055
    assert place.parse("/app/") == (Place.Chat, [])
    assert place.parse("/app/account/coach/") == (Place.Coach, [])
    assert place.parse("/app/account/meeting/2026-10-06/12") == (
        Place.MeetingCut,
        ["2026-10-06", "12"],
    )
    assert place.parse("/app/event/new") == (Place.NewEvent, [])
    assert place.parse("/app/event/5/edit") == (Place.EventEditor, ["5"])
    assert place.parse("/app/nowhere") is None
    assert place.parse("/elsewhere/account") is None


def test_a_browser_opening_an_address_in_the_app_gets_the_page_there(web):
    # R-0055
    for path in ("/app/account/coach", "/app/cluster/c1", "/app/sessions/3", "/app/account"):
        opened = web.get(path, headers=OPENED)
        assert opened.status_code == 200, path
        assert "window.BOOTSTRAP" in opened.get_data(as_text=True)
    assert web.get("/app/nowhere", headers=OPENED).status_code == 404
    # the page's own reads at the same paths still answer the page
    read = web.get("/app/account")
    assert read.is_json
    # and a browser keeps the two apart when it goes back or forward
    assert "Sec-Fetch-Dest" in read.vary
    assert "Sec-Fetch-Dest" in web.get("/app/account", headers=OPENED).vary


def test_an_address_opened_signed_out_signs_in_and_comes_back_to_it(flask_app):
    # R-0055
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        response = client.get("/app/account/coach", headers=OPENED)
    assert response.status_code == 302
    back = parse_qs(urlsplit(response.headers["Location"]).query)["next"][0]
    assert urlsplit(back).path == "/app/account/coach"
