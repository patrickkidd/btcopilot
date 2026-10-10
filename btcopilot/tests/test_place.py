import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import flask.testing
import pytest

from btcopilot import diagramjson, place
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.place import Place
from btcopilot.tests.test_api import theirs  # noqa: F401
from btcopilot.tests.test_questions import box
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import ToolError, ToolName

TABLE = Path(__file__).parents[2] / "web" / "src" / "place.ts"
OPENED = {"Sec-Fetch-Dest": "document"}
KEY = "k7m2x9pq4w"
NO_ACCESS = "You do not have access to this diagram."


def bootstrap(response) -> dict:
    """What the served page tells the app on load."""
    page = response.get_data(as_text=True)
    return json.loads(re.search(r"window\.BOOTSTRAP=(\{.*?\})</script>", page).group(1))


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


def test_the_case_report_has_an_address_the_coach_may_open(family):
    # R-0714
    assert place.parse("/app/case-report") == (Place.CaseReport, [])
    assert box(family).call(ToolName.Navigate, {"address": "/app/case-report"}) == (
        "The app is at /app/case-report.",
        {"address": "/app/case-report"},
    )


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


def test_an_address_names_the_diagram_it_is_on_by_public_id_and_the_place_under_it():
    # R-0857, R-0858
    assert place.split(f"/app/diagram/{KEY}/account/coach") == (KEY, "/app/account/coach")
    assert place.split(f"/app/diagram/{KEY}") == (KEY, "/app")
    assert place.split(f"/app/diagram/{KEY}/?notification=4") == (KEY, "/app/")
    assert place.split("/app/account/coach") == (None, "/app/account/coach")
    assert place.parse(f"/app/diagram/{KEY}/account/coach") == (Place.Coach, [])
    assert place.parse(f"/app/diagram/{KEY}") == (Place.Chat, [])
    assert place.parse(f"/app/diagram/{KEY}/") == (Place.Chat, [])
    assert place.parse(f"/app/diagram/{KEY}/cluster/c1") == (Place.Cluster, ["c1"])
    # the word alone, a key of a shape the server never makes, and the list
    # route are no address
    for path in ("/app/diagram", "/app/diagram/", "/app/diagram/K7/account", "/app/diagrams/3"):
        assert place.parse(path) is None, path


def test_the_page_at_a_diagrams_address_opens_that_diagram(web, test_user):
    # R-0857
    made = Diagram(user_id=test_user.id, name="Wren's family", data=diagramjson.dumps({}))
    db.session.add(made)
    db.session.commit()
    opened = web.get(f"/app/diagram/{made.public_id}/account/coach", headers=OPENED)
    assert opened.status_code == 200
    assert bootstrap(opened)["diagram"]["public_id"] == made.public_id
    db.session.refresh(test_user)
    assert test_user.current_diagram_id == made.id
    # the row number is no address
    assert web.get(f"/app/diagram/{made.id}/account/coach", headers=OPENED).status_code == 404


def test_an_address_without_a_diagram_opens_the_persons_own(web, test_user):
    # R-0859
    own = test_user.free_diagram.public_id
    for path in ("/app/", "/app/account/coach", "/app/?notification=4"):
        opened = web.get(path, headers=OPENED)
        assert opened.status_code == 200, path
        assert bootstrap(opened)["diagram"]["public_id"] == own, path


def test_the_page_at_a_diagram_the_person_cannot_see_says_so(web, theirs):
    # R-0860
    for path in (
        f"/app/diagram/{theirs.public_id}/",
        f"/app/diagram/{theirs.public_id}/account",
        "/app/diagram/nope2nope2/",
    ):
        shown = web.get(path, headers=OPENED)
        assert shown.status_code == 404, path
        body = shown.get_data(as_text=True)
        assert NO_ACCESS in body, path
        assert "window.BOOTSTRAP" not in body, path
        assert "!" not in re.sub(r"<[^>]+>|<style>.*?</style>", "", body, flags=re.S), path


def test_an_admin_at_another_persons_address_is_put_on_their_diagram_and_app_brings_them_home(
    admin, test_user, theirs
):
    # R-0861, R-0859
    opened = admin.get(f"/app/diagram/{theirs.public_id}/", headers=OPENED)
    assert opened.status_code == 200
    told = bootstrap(opened)["diagram"]
    assert (told["public_id"], told["access"]) == (theirs.public_id, "admin-view")
    db.session.refresh(test_user)
    assert test_user.current_diagram_id == theirs.id
    # the home-screen icon opens the admin's own diagram, never the one viewed
    home = bootstrap(admin.get("/app/", headers=OPENED))["diagram"]
    assert home["public_id"] == test_user.free_diagram.public_id
    assert home["access"] == "own"


def test_the_coach_never_names_another_diagram(family):
    # R-0857
    with pytest.raises(ToolError) as refused:
        box(family).call(ToolName.Navigate, {"address": f"/app/diagram/{KEY}/account"})
    assert "names a diagram" in str(refused.value)


def test_an_address_opened_signed_out_signs_in_and_comes_back_to_it(flask_app):
    # R-0055
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        response = client.get("/app/account/coach", headers=OPENED)
    assert response.status_code == 302
    back = parse_qs(urlsplit(response.headers["Location"]).query)["next"][0]
    assert urlsplit(back).path == "/app/account/coach"
