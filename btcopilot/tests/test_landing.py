"""The landing page at familydiagram.com and its two forms."""

import datetime
import json
import re

import pytest
from freezegun import freeze_time
from mock import patch

from btcopilot import extensions
from btcopilot.auth import landing, turnstile
from btcopilot.auth.invitation import Invitation
from btcopilot.extensions import db
from btcopilot.models import User
from btcopilot.tests.test_passwordless import INVITED, browser, token  # noqa: F401

ASKER = "test@example.com"
SENT = (
    "If that address has been invited, a sign-in link is on its way. It lasts one day."
)
THANKS = "Thanks. You are on the list and will hear from us when a spot opens."


@pytest.fixture
def keyed(flask_app):
    flask_app.config["TURNSTILE_SITE_KEY"] = "site-key-for-tests"
    flask_app.config["TURNSTILE_SECRET_KEY"] = "secret-key-for-tests"
    with patch("btcopilot.auth.turnstile.verify", return_value=True) as verify:
        yield verify


def ask_for_link(browser, email: str):
    with extensions.mail.record_messages() as outbox:
        response = browser.post(
            "/app/signin-link",
            data={
                "csrf_token": token(browser),
                "email": email,
                turnstile.FIELD: "a-token",
            },
        )
    return response, outbox


def ask_to_join(browser, **fields):
    with extensions.mail.record_messages() as outbox:
        response = browser.post(
            "/app/beta-request",
            data={"csrf_token": token(browser), turnstile.FIELD: "a-token", **fields},
        )
    return response, outbox


def seen(response) -> str:
    """The words a visitor reads, without the markup around them."""
    html = response.get_data(as_text=True)
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def test_a_visitor_sees_the_landing_page(flask_app, browser, keyed):
    # R-0601
    response = browser.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    text = seen(response)
    assert "Alaska Family Systems" in text
    assert "Family Diagram" in text
    assert "Family Diagram is by invitation only for now." in text
    assert 'action="/app/signin-link"' in html
    assert 'action="/app/beta-request"' in html
    assert html.count('data-sitekey="site-key-for-tests"') == 2
    assert html.count("turnstile/v0/api.js") == 1
    assert "!" not in text
    assert '<link rel="icon" type="image/png" href="/app/afs-logo.png"' in html
    assert "/app/theory" not in html
    assert '<meta name="theme-color" content="#f7f6f2"' in html
    assert '<meta name="theme-color" content="#171d1c"' in html


# Job 026 (2026-10-07): the page was rebuilt around the stepping family diagram, so
# the description is no longer one paragraph under the heading but the hero line and
# three one-line facts about what the app does today. R-0602's words ("the record
# builds", "it gets smarter") are off the page by the job's brief; Patrick rules.
HERO = "Your family, as dated facts you can check."
FACTS = [
    "A coach that asks about your family.",
    "Each fact you state becomes a dated event you can correct.",
    "Your family diagram, drawn from those facts, on any date.",
]


def described(browser) -> list[str]:
    """The three facts under the picture, as a visitor reads them."""
    html = browser.get("/").get_data(as_text=True)
    facts = re.search(r'<section class="facts">(.*?)</section>', html, re.S).group(1)
    return [" ".join(li.split()) for li in re.findall(r"<li>(.*?)</li>", facts, re.S)]


def test_the_page_says_what_the_app_is_in_the_briefs_words(browser, keyed):
    # R-0601, R-0602
    html = browser.get("/").get_data(as_text=True)
    assert f"<h1>{HERO}</h1>" in html
    assert described(browser) == FACTS
    assert "<abbr" not in html and "SARF" not in html and "chat-first" not in html


def test_the_description_claims_only_what_the_app_does_today(browser, keyed):
    # R-0602
    text = seen(browser.get("/")).lower()
    for word in (
        "record",
        "smarter",
        "better",
        "pattern",
        "moment",
        "stretch",
        "bowen",
    ):
        assert word not in text


def test_the_description_is_never_framed_as_therapy(browser, keyed):
    # R-0602
    text = seen(browser.get("/")).lower()
    for word in (
        "therapy",
        "therapist",
        "wounded",
        "hard stretch",
        "healing",
        "trauma",
    ):
        assert word not in text


def test_the_picture_steps_through_the_dated_events(browser, keyed):
    # R-0601
    html = browser.get("/").get_data(as_text=True)
    steps = json.loads(re.search(r'id="steps">(.*?)</script>', html, re.S).group(1))
    assert [s["d"] for s in steps] == [
        "19 Jun 2010",
        "2 Nov 2011",
        "2012",
        "Oct 2012",
        "21 Jan 2014",
    ]
    for step in ("back", "next"):
        assert (
            html.count(f'<button type="button" class="stepbtn" data-step="{step}">')
            == 1
        )
    assert 'id="join"' in html and 'href="#join"' in html


def test_an_invited_address_gets_a_link_that_signs_in(flask_app, browser, keyed):
    # R-0601
    Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"]).consume()

    response, outbox = ask_for_link(browser, f"  {INVITED.upper()} ")
    assert response.status_code == 200
    assert SENT in seen(response)
    assert [m.recipients for m in outbox] == [[INVITED]]
    assert outbox[0].subject == "Your Family Diagram sign-in link"
    path = re.search(r"https?://[^/\s]+(/app/invite/\S+)", outbox[0].body).group(1)

    opened = browser.get(path)
    assert opened.status_code == 302
    assert opened.headers["Location"] == flask_app.config["APP_HOME"]
    assert browser.get("/app/me").get_json()["user"]["email"] == INVITED


def test_an_account_holder_gets_a_link(flask_app, browser, keyed, test_user):
    # R-0601
    response, outbox = ask_for_link(browser, test_user.username)
    assert response.status_code == 200
    assert [m.recipients for m in outbox] == [[test_user.username]]
    fresh = Invitation.query.filter_by(email=test_user.username).one()
    lasts = fresh.expires_at - datetime.datetime.utcnow()
    assert datetime.timedelta(hours=23) < lasts <= datetime.timedelta(days=1)


def test_an_unknown_address_is_told_the_same_and_sent_nothing(browser, keyed):
    # R-0601
    response, outbox = ask_for_link(browser, ASKER)
    assert response.status_code == 200
    assert SENT in seen(response)
    assert outbox == []
    assert Invitation.query.count() == 0


def test_links_are_capped_each_hour_without_saying_so(flask_app, browser, keyed):
    # R-0601
    old = Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    old.created_at = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    db.session.commit()
    cap = flask_app.config["LOGIN_CODES_PER_HOUR"]

    sent = [ask_for_link(browser, INVITED)[1] for _ in range(cap)]
    assert [len(outbox) for outbox in sent] == [1] * cap

    response, outbox = ask_for_link(browser, INVITED)
    assert response.status_code == 200
    assert SENT in seen(response)
    assert outbox == []
    assert Invitation.query.count() == cap + 1


@pytest.mark.parametrize("form", ["link", "beta"])
def test_a_failed_person_check_sends_nothing(flask_app, browser, keyed, form):
    # R-0601
    Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    keyed.return_value = False
    if form == "link":
        response, outbox = ask_for_link(browser, INVITED)
    else:
        response, outbox = ask_to_join(browser, name="Sam Tester", email=ASKER)
    assert response.status_code == 400
    assert landing.NOT_A_PERSON in seen(response)
    assert outbox == []
    assert Invitation.query.count() == 1


def test_a_beta_request_is_emailed_to_patrick(flask_app, browser, keyed):
    # R-0601
    response, outbox = ask_to_join(
        browser,
        name="Sam Tester",
        email=ASKER,
        words="I run a family practice and want to try it.",
    )
    assert response.status_code == 200
    assert THANKS in seen(response)
    assert len(outbox) == 1
    mail = outbox[0]
    assert mail.recipients == [flask_app.config["ADMIN_EMAIL"]]
    assert mail.reply_to == ASKER
    assert mail.subject == "Family Diagram beta request from Sam Tester"
    for field in ("Sam Tester", ASKER, "I run a family practice and want to try it."):
        assert field in mail.body
    assert Invitation.query.count() == 0 and User.query.count() == 0


def test_a_long_beta_request_is_cut_to_its_limit(browser, keyed):
    # R-0601
    _, outbox = ask_to_join(browser, name="Sam Tester", email=ASKER, words="x" * 5000)
    assert "x" * landing.WORDS_LIMIT in outbox[0].body
    assert "x" * (landing.WORDS_LIMIT + 1) not in outbox[0].body


@pytest.mark.parametrize(
    "name, email",
    [
        ("Sam Tester", "test@example.com\nBcc: test@example.com"),
        ("Sam Tester", "test@example.com\r"),
        ("Sam\r\nTester", ASKER),
        ("Sam Tester", "test @example.com"),
        ("Sam Tester", "test@@example.com"),
        ("Sam Tester", "@example.com"),
    ],
)
def test_a_beta_request_with_a_broken_name_or_email_is_refused(
    browser, keyed, name, email
):
    # R-0601
    response, outbox = ask_to_join(browser, name=name, email=email)
    assert response.status_code == 400
    text = seen(response)
    assert (
        "Put your name and your email on one line each." in text
        or "That email address does not look right." in text
    )
    assert outbox == []


@pytest.mark.parametrize("missing", ["name", "email"])
def test_a_beta_request_needs_a_name_and_an_email(browser, keyed, missing):
    # R-0601
    fields = {"name": "Sam Tester", "email": ASKER, missing: "  "}
    response, outbox = ask_to_join(browser, **fields)
    assert response.status_code == 400
    assert "Enter your name and your email." in seen(response)
    assert outbox == []


def test_without_keys_in_production_the_forms_are_shut(flask_app, browser):
    # R-0601
    flask_app.config["CONFIG"] = "production"
    Invitation.issue(INVITED, flask_app.config["INVITATION_DAYS"])
    with patch("btcopilot.auth.turnstile.verify", return_value=True):
        link, link_mail = ask_for_link(browser, INVITED)
        beta, beta_mail = ask_to_join(browser, name="Sam Tester", email=ASKER)
    for response in (link, beta):
        assert response.status_code == 503
        assert landing.UNAVAILABLE in seen(response)
    assert link_mail == [] and beta_mail == []

    page = browser.get("/")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert landing.UNAVAILABLE in seen(page)
    assert html.count("disabled>") == 2
    assert "data-sitekey" not in html and "api.js" not in html


def test_development_without_keys_uses_the_always_passing_keys(flask_app, browser):
    # R-0601
    flask_app.config["CONFIG"] = "development"
    html = browser.get("/").get_data(as_text=True)
    assert html.count(f'data-sitekey="{turnstile.TEST_SITE_KEY}"') == 2

    with (
        flask_app.test_request_context(),
        patch.object(turnstile.requests, "post") as post,
    ):
        post.return_value.json.return_value = {"success": True}
        assert turnstile.verify("a-token", "203.0.113.9") is True
    assert post.call_args.kwargs["data"]["secret"] == turnstile.TEST_SECRET_KEY
    assert post.call_args.kwargs["timeout"] == 5


def test_the_person_check_fails_closed(flask_app):
    # R-0601
    flask_app.config["TURNSTILE_SITE_KEY"] = "site-key-for-tests"
    flask_app.config["TURNSTILE_SECRET_KEY"] = "secret-key-for-tests"
    with (
        flask_app.test_request_context(),
        patch.object(turnstile.requests, "post") as post,
    ):
        post.return_value.json.return_value = {"success": False}
        assert turnstile.verify("a-token", None) is False
        post.side_effect = turnstile.requests.Timeout()
        assert turnstile.verify("a-token", None) is False
        assert turnstile.verify("", None) is False


def test_the_copyright_year_is_the_year_of_the_visit(browser, keyed):
    # R-0601
    with freeze_time("2031-05-01"):
        text = seen(browser.get("/"))
    assert "© 2031 Alaska Family Systems" in text


def test_the_copyright_links_to_alaska_family_systems_and_the_logo_is_the_icon(
    browser, keyed
):
    # R-0601
    # Job 026 (2026-10-07): the logo image left the page (the picture is the page);
    # the logo stays as the page's icon. Patrick rules on R-0601's logo and colours.
    html = browser.get("/").get_data(as_text=True)
    year = datetime.date.today().year
    assert re.search(
        rf'<a href="https://alaskafamilysystems.com">© {year} Alaska Family Systems</a>',
        html,
    )
    assert "<img" not in html
    logo = browser.get("/app/afs-logo.png")
    assert logo.status_code == 200
    assert logo.mimetype == "image/png"
    assert logo.data[:8] == b"\x89PNG\r\n\x1a\n"
