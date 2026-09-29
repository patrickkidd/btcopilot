"""The concept pages (FD-364): read from GitHub, revalidated by ETag after five
minutes, and for coders only: the public edition is made outside the app."""

import json
from http import HTTPStatus

import pytest
import requests
from mock import patch

import btcopilot
from btcopilot.extensions import db
from btcopilot.routes import theory as theory_routes
from btcopilot.theorypages import TheoryPages, Unavailable

PAGES = {
    "README.md": """# Concept pages for coders

## Public copy

| Key | Source | File | Visibility |
|---|---|---|---|
| FE*n* L*x* | Kerr and Bowen, *Family Evaluation* | [`BT:FE`](../../bowentheory/FE.md) | PUBLIC |
| SEM *m* | App Seminar | [`FR:transcripts/seminar/`](../transcripts/seminar/) | CONFIDENTIAL |
""",
    "INDEX.md": """# Concept pages: index

| Page | Covers | Entries | Status of the code |
|---|---|---|---|
| [`anxiety.md`](anxiety.md) (A) | What anxiety is | 3 | Own evidence ruled |
| [`conflict.md`](conflict.md) (C) | Conflict as a move | 1 | Two rules |

Total: 4 entries, 2 CONFIDENTIAL.
""",
    "anxiety.md": """# Anxiety (A)

- Sources are in [`README.md`](README.md); see [`conflict.md`](conflict.md#C1) and [`../REFERENCE.md`](../REFERENCE.md).

## 2. What the original authors wrote

- <a id="A1"></a>**A1** “anxiety is the response to a threat” Kerr, FE5 L9 · PUBLIC. The standard definition. <!-- v BT:FE Chapters/5 - Chronic Anxiety.md L9 -->
- <a id="A2"></a>**A2** “the lighthouse keeper worried all winter” Member, SEM 2024 @00:01:00 · CONFIDENTIAL. A seminar reading. <!-- v FR:transcripts/seminar/x.tsv @00:01:00 -->
<!-- CONFIDENTIAL -->
### App Seminar
- <a id="A3"></a>**A3** “the ferry captain stopped sleeping” Member, SEM 2025 @00:02:00. A second reading.
<!-- /CONFIDENTIAL -->
""",
    "conflict.md": """# Conflict (C)

- <a id="C1"></a>**C1** “two people fight over an issue” Bowen, FE7 L2 · PUBLIC. A move by two.
""",
}

LISTING = "https://api.github.com/repos/patrickkidd/btcopilot-sources/contents/theory/CONCEPTS"


def answer(status: HTTPStatus, body: str = "", etag: str | None = None):
    response = requests.Response()
    response.status_code = status
    response._content = body.encode()
    if etag:
        response.headers["ETag"] = etag
    return response


class GitHub:
    """The contents API over PAGES, answering 304 to a matching ETag."""

    def __init__(self):
        self.files = dict(PAGES)
        self.down = False
        self.calls = []
        self.answered = []

    def get(self, url, params, headers, timeout):
        self.calls.append((url, headers))
        if self.down:
            raise requests.ConnectionError("github is down")
        key = url.removeprefix(LISTING).lstrip("/")
        if key:
            body = self.files[key]
        else:
            body = json.dumps([{"name": n, "type": "file"} for n in self.files])
        etag = f'"{hash(body)}"'
        status = (
            HTTPStatus.NOT_MODIFIED
            if headers.get("If-None-Match") == etag
            else HTTPStatus.OK
        )
        self.answered.append(status)
        return answer(status, "" if status == HTTPStatus.NOT_MODIFIED else body, etag)


@pytest.fixture
def github():
    fake = GitHub()
    with patch("btcopilot.theorypages.requests.get", side_effect=fake.get):
        yield fake


def pages(clock=lambda: 0, token="t"):
    return TheoryPages(
        repo="patrickkidd/btcopilot-sources",
        ref="master",
        path="theory/CONCEPTS",
        token=token,
        clock=clock,
    )


@pytest.fixture
def theory(flask_app, github):
    flask_app.extensions["theory"] = pages()
    return github


@pytest.fixture
def coder(web):
    web.user.roles = btcopilot.ROLE_AUDITOR
    db.session.merge(web.user)
    db.session.commit()
    return web


def test_links_point_to_routes_and_flatten_the_rest():
    # R-0541
    out = theory_routes.links(
        "[`conflict.md`](conflict.md#C1) [`../REFERENCE.md`](../REFERENCE.md) [A1](#A1)",
        {"conflict.md": "/app/theory/conflict"},
    )
    assert out == "[`conflict.md`](/app/theory/conflict#C1) `../REFERENCE.md` [A1](#A1)"


def test_held_five_minutes_then_revalidated_by_etag(github):
    # R-0541
    now = [0]
    theory = pages(clock=lambda: now[0])
    assert theory.names() == ["anxiety", "conflict"]
    assert theory.text("conflict") == PAGES["conflict.md"]
    github.files["conflict.md"] = "# Conflict (C), edited\n"
    now[0] = 299
    assert theory.text("conflict") == PAGES["conflict.md"]
    assert len(github.calls) == 2

    now[0] = 301
    assert theory.text("conflict") == "# Conflict (C), edited\n"
    url, headers = github.calls[-1]
    assert url == f"{LISTING}/conflict.md"
    assert headers["Authorization"] == "Bearer t"
    assert headers["If-None-Match"]


def test_unchanged_page_is_reused_on_304(github):
    # R-0541
    now = [0]
    theory = pages(clock=lambda: now[0])
    first = theory.text("anxiety")
    now[0] = 301
    assert theory.text("anxiety") == first
    assert github.answered == [HTTPStatus.OK, HTTPStatus.NOT_MODIFIED]


def test_github_down_past_the_window_is_not_served_stale(github):
    # R-0541
    now = [0]
    theory = pages(clock=lambda: now[0])
    theory.text("anxiety")
    github.down = True
    now[0] = 301
    with pytest.raises(Unavailable, match="github is down"):
        theory.text("anxiety")


def test_missing_token_fails_loudly(github):
    # R-0541
    with pytest.raises(Unavailable, match="FLASK_THEORY_GITHUB_TOKEN is not set"):
        pages(token=None).names()
    assert github.calls == []


def test_coder_reads_the_full_edition(theory, coder):
    # R-0311, R-0541, R-0567
    html = coder.get("/app/theory/anxiety").get_data(as_text=True)
    assert "lighthouse" in html
    assert "ferry" in html
    assert 'href="/app/theory/conflict#C1"' in html
    assert 'href="/app/theory/README"' in html
    assert "../REFERENCE.md" in html and 'href="../REFERENCE.md"' not in html
    assert coder.get("/app/theory/README").status_code == HTTPStatus.OK
    assert "Total: 4 entries" in coder.get("/app/theory").get_data(as_text=True)


def test_a_subscriber_is_refused(theory, web):
    # R-0311, R-0541, R-0567
    for path in ("/app/theory", "/app/theory/anxiety", "/app/theory/README"):
        assert web.get(path).status_code == HTTPStatus.FORBIDDEN
    assert theory.calls == []


def test_signed_out_is_sent_to_sign_in(theory, flask_app):
    # R-0541, R-0567
    response = flask_app.test_client().get("/app/theory/anxiety")
    assert response.status_code == HTTPStatus.FOUND
    assert "/app/login" in response.headers["Location"]


def test_unknown_page_is_404(theory, coder):
    # R-0541
    assert coder.get("/app/theory/nothing").status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("down, cause", [(False, "FLASK_THEORY_GITHUB_TOKEN"), (True, "github is down")])
def test_unreachable_pages_say_so_without_naming_the_source(flask_app, github, coder, down, cause):
    # R-0541
    flask_app.extensions["theory"] = pages(token=None if not down else "t")
    github.down = down
    with patch.object(theory_routes._log, "error") as logged:
        response = coder.get("/app/theory")
    html = response.get_data(as_text=True)
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert "The concept pages can&#39;t be loaded right now." in html
    assert "btcopilot-sources" not in html
    assert "theory/CONCEPTS" not in html
    assert "TOKEN" not in html
    said = logged.call_args.args[0]
    assert cause in said
    assert "patrickkidd/btcopilot-sources" in said
    assert "theory/CONCEPTS" in said
