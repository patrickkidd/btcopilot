"""A file attached to a message: checked in the request, read into text once,
kept as that text on the statement, and given to the coach after the person's
words. A PDF or a photo is read on the worker, where the coach's turns run, so
a long file never holds a request open (Patrick: "defintiely add the worker
job for long files. And you will re-use the existing worker container(s) in
the stack, right?"). The model that reads a file is stubbed here, and the
worker's task runs as the POST returns, the way every turn does in this suite.

Invented names only.
"""

import base64
import io

import pillow_heif
import pytest
from mock import patch
from PIL import Image
from pypdf import PdfReader, PdfWriter

from btcopilot import attachments, turnlog, turns
from btcopilot.extensions import db
from btcopilot.llmutil import Served, Spent, Text
from btcopilot.models import (
    ModelCall,
    Observation,
    ObservationKind,
    Statement,
    TokenMeter,
)
from btcopilot.models.modelcall import Purpose
from btcopilot.tests.conftest import Model, csrf_token, said
from btcopilot.tests.test_turnhistory import coach
from btcopilot.turnlog import TurnEventKind

READ = "Ada Hale, born 1950. Married Hugh Hale 1974."


@pytest.fixture
def token(web):
    return csrf_token(web)


@pytest.fixture(autouse=True)
def held():
    """Where a file waits for the worker, one store per test, in memory."""
    store = attachments.MemoryFiles()
    attachments.use(store)
    yield store
    attachments.use(None)


class FakeRedis:
    """Only what the file store asks of Redis, each call written down."""

    def __init__(self):
        self.kept = {}
        self.calls = []

    def set(self, key, value, ex=None):
        self.kept[key] = value
        self.calls.append(("set", key, ex))

    def get(self, key):
        return self.kept.get(key)

    def delete(self, key):
        self.kept.pop(key, None)
        self.calls.append(("delete", key))


def events(turn_id: str) -> list[dict]:
    return [event for _, event in turnlog.read_from(turn_id, 0)]


@pytest.fixture
def reader(monkeypatch):
    """The model that reads a file, answering with READ; each call's content
    blocks are kept."""
    calls = []

    def read(content, **kwargs):
        calls.append(content)
        return Text(READ, Spent(input=1200, output=40), Served("claude-opus-5-5"))

    monkeypatch.setattr("btcopilot.metered.claude_text_sync", read)
    return calls


def send(web, token, name: str, data: bytes, statement="Here is my mother's page."):
    return web.post(
        "/app/chat",
        data={"statement": statement, "file": (io.BytesIO(data), name)},
        content_type="multipart/form-data",
        headers={"X-CSRFToken": token},
    )


def pdf(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(612, 792)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def photo(fmt: str, size=(40, 30)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, fmt)
    return out.getvalue()


def heic() -> bytes:
    out = io.BytesIO()
    pillow_heif.from_pillow(Image.new("RGB", (40, 30), "white")).save(out)
    return out.getvalue()


def words(model: Model) -> str:
    """What the coach was given as the person's newest message."""
    return "".join(b["text"] for b in model.histories[0][-1]["content"] if b["type"] == "text")


def stored() -> Statement:
    return Statement.query.filter(Statement.attachment_name.isnot(None)).one()


def test_a_markdown_file_is_its_own_text_and_the_coach_reads_it_after_the_words(
    web, token, monkeypatch, reader
):
    # R-0828, R-0829
    model = coach(monkeypatch, Model(said("Thank you.")))
    response = send(web, token, "notes.md", b"# Mum\nAda Hale, born 1950.")
    assert response.status_code == 202
    assert (stored().attachment_name, stored().attachment_text) == (
        "notes.md",
        "# Mum\nAda Hale, born 1950.",
    )
    assert reader == []
    assert words(model).endswith(
        "Here is my mother's page.\n\nFrom the file notes.md (enter every person and "
        "every dated event in it, births too, before you reply):\n# Mum\nAda Hale, born 1950."
    )


def test_a_pdf_is_read_once_by_the_model_charged_to_the_person(
    web, token, test_user, monkeypatch, reader
):
    # R-0828, R-0829
    coach(monkeypatch, Model(said("Thank you.")))
    assert send(web, token, "Family Bible.pdf", pdf()).status_code == 202
    [content] = reader
    assert content[0]["type"] == "document"
    assert content[0]["source"]["media_type"] == "application/pdf"
    assert stored().attachment_text == READ
    call = ModelCall.query.filter_by(purpose=Purpose.Transcribe).one()
    assert (call.user_id, call.turn_id, call.input_tokens) == (
        test_user.id,
        stored().turn_id,
        1200,
    )
    assert TokenMeter.query.filter_by(user_id=test_user.id).one().input_tokens >= 1200


@pytest.mark.parametrize(
    "name, data",
    [("grave.jpg", photo("JPEG")), ("letter.png", photo("PNG")), ("IMG_0042.HEIC", heic())],
)
def test_a_photo_of_each_kind_is_sent_to_the_model_as_a_jpeg(
    web, token, monkeypatch, reader, name, data
):
    # R-0828, R-0830
    coach(monkeypatch, Model(said("Thank you.")))
    assert send(web, token, name, data).status_code == 202
    [content] = reader
    assert (content[0]["type"], content[0]["source"]["media_type"]) == ("image", "image/jpeg")
    assert stored().attachment_text == READ


def test_a_large_photo_is_sent_no_larger_than_the_model_reads(
    web, token, monkeypatch, reader
):
    # R-0830
    coach(monkeypatch, Model(said("Thank you.")))
    assert send(web, token, "scan.png", photo("PNG", (4000, 3000))).status_code == 202
    sent = Image.open(io.BytesIO(base64.b64decode(reader[0][0]["source"]["data"])))
    assert max(sent.size) == attachments.MAX_SIDE


@pytest.mark.parametrize(
    "name, data, status, message",
    [
        ("notes.docx", b"PK", 415, attachments.UNKNOWN),
        ("broken.pdf", b"not a pdf", 415, attachments.UNREADABLE),
        ("broken.jpg", b"not a photo", 415, attachments.UNREADABLE),
        ("latin1.txt", "Zoë".encode("latin-1"), 415, attachments.UNREADABLE),
        ("long.pdf", pdf(attachments.MAX_PAGES + 1), 413, attachments.TOO_LONG),
        ("big.txt", b"a" * (attachments.MAX_BYTES + 1), 413, attachments.TOO_BIG),
    ],
)
def test_a_file_the_app_does_not_read_is_refused_in_plain_words_and_nothing_is_kept(
    web, token, monkeypatch, reader, name, data, status, message
):
    # R-0830
    coach(monkeypatch, Model(said("Thank you.")))
    response = send(web, token, name, data)
    assert response.status_code == status
    assert message in response.get_data(as_text=True)
    assert (Statement.query.count(), reader) == (0, [])


def test_a_read_that_breaks_on_the_worker_keeps_no_text_and_the_coach_never_starts(
    web, token, monkeypatch
):
    # R-0829
    """Patrick: "defintiely add the worker job for long files." A fault in the
    read is logged like a turn that broke; the message stays in the thread
    with no text, marked unfinished, and the session takes the next one."""

    def broken(content, **kwargs):
        raise RuntimeError("the model went away")

    monkeypatch.setattr("btcopilot.metered.claude_text_sync", broken)
    model = coach(monkeypatch, Model(said("Thank you.")))
    with patch("btcopilot.turns.enqueue"):
        body = send(web, token, "page.pdf", pdf()).get_json()
    with pytest.raises(RuntimeError):
        turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    assert (stored().attachment_name, stored().attachment_text) == ("page.pdf", None)
    assert model.histories == []
    assert events(body["turn_id"])[-1] == {
        "type": TurnEventKind.Failed.value,
        "message": attachments.REFUSED,
    }
    assert turnlog.running(body["discussion_id"]) is None
    response = web.post(
        "/app/chat", json={"statement": "Hello."}, headers={"X-CSRFToken": token}
    )
    assert response.status_code == 202


def test_the_thread_carries_the_file_name_and_its_text(web, token, monkeypatch, reader):
    # R-0830
    coach(monkeypatch, Model(said("Thank you.")))
    send(web, token, "notes.txt", b"Hugh Hale died 2001.")
    mine = [s for s in web.get("/app/statements").get_json() if s["role"] == "user"]
    assert [(s["attachment_name"], s["attachment_text"]) for s in mine] == [
        ("notes.txt", "Hugh Hale died 2001.")
    ]


def test_words_with_no_file_have_no_attachment(web, token, monkeypatch):
    # R-0829
    model = coach(monkeypatch, Model(said("Thank you.")))
    send_plain = web.post(
        "/app/chat",
        data={"statement": "Just words."},
        content_type="multipart/form-data",
        headers={"X-CSRFToken": token},
    )
    assert send_plain.status_code == 202
    assert {name for (name,) in db.session.query(Statement.attachment_name)} == {None}
    assert "From the file" not in words(model)


def test_the_answer_to_a_send_carries_the_file_name_and_the_text_once_it_is_read(
    web, token, monkeypatch, reader
):
    # R-0830
    """A text file's words come back with the 202; a PDF's are read on the
    worker, so the 202 carries its name and no text yet, and the thread
    carries the text once it is in."""
    coach(monkeypatch, Model(said("Thank you."), said("Thank you.")))
    body = send(web, token, "notes.txt", b"Hugh Hale died 2001.").get_json()
    assert (body["attachment_name"], body["attachment_text"]) == (
        "notes.txt",
        "Hugh Hale died 2001.",
    )
    with patch("btcopilot.turns.enqueue"):
        body = send(web, token, "page.pdf", pdf()).get_json()
    assert (body["attachment_name"], body["attachment_text"]) == ("page.pdf", None)
    turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    mine = [s for s in web.get("/app/statements").get_json() if s["role"] == "user"]
    assert [(s["attachment_name"], s["attachment_text"]) for s in mine] == [
        ("notes.txt", "Hugh Hale died 2001."),
        ("page.pdf", READ),
    ]


def test_a_file_sent_with_no_words_is_taken_and_the_coach_reads_the_file(
    web, token, monkeypatch, reader
):
    # R-0828
    model = coach(monkeypatch, Model(said("Thank you.")))
    assert send(web, token, "notes.txt", b"Hugh Hale died 2001.", statement="").status_code == 202
    assert stored().text == ""
    assert words(model).endswith(
        "From the file notes.txt (enter every person and every dated event in it, "
        "births too, before you reply):\nHugh Hale died 2001."
    )


def test_a_long_pdf_is_read_in_parts_of_25_pages_and_the_texts_joined(
    web, token, monkeypatch, reader
):
    # R-0828, R-0830
    coach(monkeypatch, Model(said("Thank you.")))
    assert send(web, token, "diary.pdf", pdf(60)).status_code == 202
    assert [len(PdfReader(io.BytesIO(base64.b64decode(c[0]["source"]["data"]))).pages) for c in reader] == [25, 25, 10]
    assert reader[1][1]["text"] == "The file is named diary.pdf. These are its pages 26 to 50 of 60."
    assert stored().attachment_text == "\n\n".join([READ] * 3)


@pytest.mark.parametrize("stop, words", [("refusal", "I can't help with that."), ("end_turn", " ")])
def test_a_read_the_model_declines_or_leaves_empty_ends_the_turn_in_the_thread_and_keeps_no_text(
    web, token, monkeypatch, stop, words
):
    # R-0829
    """Patrick: "defintiely add the worker job for long files." The read now
    fails on the worker, after the 202, so the thread says so where the page
    reads a turn that did not finish, in the words the refused read always had;
    the coach never starts and the session takes the next message."""
    monkeypatch.setattr(
        "btcopilot.metered.claude_text_sync",
        lambda content, **kw: Text(words, Spent(), Served("claude-opus-5-5"), stop),
    )
    model = coach(monkeypatch, Model(said("Thank you.")))
    response = send(web, token, "grave.jpg", photo("JPEG"))
    assert response.status_code == 202
    turn_id = response.get_json()["turn_id"]
    assert (stored().attachment_name, stored().attachment_text) == ("grave.jpg", None)
    assert model.histories == []
    assert events(turn_id)[-1] == {
        "type": TurnEventKind.Failed.value,
        "message": attachments.REFUSED,
    }
    [mine] = [s for s in web.get("/app/statements").get_json() if s["role"] == "user"]
    assert (mine["unfinished"], mine["failure"]) == (True, attachments.REFUSED)
    assert Statement.query.count() == 1
    assert [o.kind for o in Observation.query.all()] == [ObservationKind.TurnFailed]
    assert turnlog.running(response.get_json()["discussion_id"]) is None
    assert send(web, token, "notes.txt", b"Hugh Hale died 2001.").status_code == 202


def test_a_part_cut_off_at_the_output_limit_fails_the_read_and_keeps_no_text(
    web, token, monkeypatch
):
    # R-0828
    monkeypatch.setattr(
        "btcopilot.metered.claude_text_sync",
        lambda content, **kw: Text(READ, Spent(), Served("claude-opus-5-5"), "max_tokens"),
    )
    model = coach(monkeypatch, Model(said("Thank you.")))
    response = send(web, token, "diary.pdf", pdf())
    assert response.status_code == 202
    assert stored().attachment_text is None
    assert model.histories == []
    assert events(response.get_json()["turn_id"])[-1] == {
        "type": TurnEventKind.Failed.value,
        "message": attachments.CUT,
    }


def test_a_long_pdf_is_read_on_the_worker_and_the_coach_starts_once_the_text_is_in(
    web, token, test_user, monkeypatch, reader, held
):
    # R-0828, R-0829
    """Patrick: "defintiely add the worker job for long files. And you will
    re-use the existing worker container(s) in the stack, right?" The request
    stores the message with the file's name and no text, leaves the bytes for
    the worker, and the one task reads every part, writes the text, lets the
    bytes go and runs the coach's turn with the text after the words."""
    model = coach(monkeypatch, Model(said("Thank you.")))
    with patch("btcopilot.turns.enqueue") as queued:
        response = send(web, token, "diary.pdf", pdf(60))
    assert response.status_code == 202
    body = response.get_json()
    assert (body["attachment_name"], body["attachment_text"]) == ("diary.pdf", None)
    assert (stored().attachment_text, reader, model.histories) == (None, [], [])
    assert held.held(body["turn_id"]) == pdf(60)
    queued.assert_called_once_with(
        body["turn_id"], body["discussion_id"], body["statement_id"], zone=None
    )
    turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    assert len(reader) == 3
    assert stored().attachment_text == "\n\n".join([READ] * 3)
    assert held.held(body["turn_id"]) is None
    assert words(model).endswith(
        "Here is my mother's page.\n\nFrom the file diary.pdf (enter every person and "
        f"every dated event in it, births too, before you reply):\n{READ}\n\n{READ}\n\n{READ}"
    )
    assert events(body["turn_id"])[-1]["type"] == TurnEventKind.Done.value
    assert ModelCall.query.filter_by(purpose=Purpose.Transcribe).count() == 3
    assert TokenMeter.query.filter_by(user_id=test_user.id).one().input_tokens >= 3600


def test_a_turn_stopped_while_its_file_is_read_reads_no_further_part_and_ends_stopped(
    web, token, monkeypatch, held
):
    # R-0829, R-0636
    calls = []

    def read(content, **kwargs):
        calls.append(content)
        turnlog.halt(turn_id)
        return Text(READ, Spent(input=1200, output=40), Served("claude-opus-5-5"))

    monkeypatch.setattr("btcopilot.metered.claude_text_sync", read)
    model = coach(monkeypatch, Model(said("Thank you.")))
    with patch("btcopilot.turns.enqueue"):
        body = send(web, token, "diary.pdf", pdf(60)).get_json()
    turn_id = body["turn_id"]
    turns.run(turn_id, body["discussion_id"], body["statement_id"])
    assert (len(calls), model.histories) == (1, [])
    assert stored().attachment_text is None
    done = events(turn_id)[-1]
    assert (done["type"], done["stopped"]) == (TurnEventKind.Done.value, True)
    assert turnlog.running(body["discussion_id"]) is None
    assert ModelCall.query.filter_by(purpose=Purpose.Transcribe).count() == 1


def test_a_text_file_is_stored_in_the_request_and_never_waits_for_the_worker(
    web, token, monkeypatch, reader, held
):
    # R-0828, R-0830
    model = coach(monkeypatch, Model(said("Thank you.")))
    with patch("btcopilot.turns.enqueue"):
        body = send(web, token, "notes.txt", b"Hugh Hale died 2001.").get_json()
    assert (body["attachment_name"], body["attachment_text"]) == (
        "notes.txt",
        "Hugh Hale died 2001.",
    )
    assert stored().attachment_text == "Hugh Hale died 2001."
    assert (held.files, reader, model.histories) == ({}, [], [])


def test_the_file_waits_in_redis_an_hour_and_goes_once_it_is_read(
    web, token, monkeypatch, reader
):
    # R-0830
    """The original file is not kept: it sits in the queue's Redis under the
    turn's key for one hour at most, and the read deletes it."""
    fake = FakeRedis()
    attachments.use(attachments.RedisFiles(fake))
    coach(monkeypatch, Model(said("Thank you.")))
    with patch("btcopilot.turns.enqueue"):
        body = send(web, token, "page.pdf", pdf()).get_json()
    key = f"attachment:{body['turn_id']}"
    assert fake.calls == [("set", key, 3600)]
    assert fake.kept[key] == pdf()
    turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    assert fake.calls == [("set", key, 3600), ("delete", key)]
    assert stored().attachment_text == READ


def test_a_failed_read_leaves_the_file_for_the_hour_and_trying_again_reads_it(
    web, token, monkeypatch, held
):
    # R-0829
    """The thread's "try again" on a message whose file could not be read
    reads the file again rather than running the coach without it."""
    calls = []

    def flaky(content, **kwargs):
        calls.append(content)
        if len(calls) == 1:
            return Text(" ", Spent(), Served("claude-opus-5-5"), "end_turn")
        return Text(READ, Spent(), Served("claude-opus-5-5"))

    monkeypatch.setattr("btcopilot.metered.claude_text_sync", flaky)
    model = coach(monkeypatch, Model(said("Thank you.")))
    body = send(web, token, "page.pdf", pdf()).get_json()
    assert (stored().attachment_text, model.histories) == (None, [])
    assert held.held(body["turn_id"]) == pdf()
    response = web.post(
        f"/app/turns/{body['turn_id']}/resume", headers={"X-CSRFToken": token}
    )
    assert response.status_code == 202
    assert stored().attachment_text == READ
    assert held.held(body["turn_id"]) is None
    assert len(model.histories) == 1
    assert events(body["turn_id"])[-1]["type"] == TurnEventKind.Done.value


def test_a_file_the_hour_took_ends_the_turn_saying_to_send_it_again(
    web, token, monkeypatch, reader, held
):
    # R-0829, R-0830
    model = coach(monkeypatch, Model(said("Thank you.")))
    with patch("btcopilot.turns.enqueue"):
        body = send(web, token, "page.pdf", pdf()).get_json()
    held.drop(body["turn_id"])
    turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    assert (stored().attachment_text, reader, model.histories) == (None, [], [])
    assert events(body["turn_id"])[-1] == {
        "type": TurnEventKind.Failed.value,
        "message": attachments.GONE,
    }
