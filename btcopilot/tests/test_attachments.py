"""A file attached to a message: checked, read into text once, kept as that
text on the statement, and given to the coach after the person's words. The
model that reads a PDF or a photo is stubbed here.

Invented names only.
"""

import base64
import io

import pillow_heif
import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from btcopilot import attachments
from btcopilot.extensions import db
from btcopilot.llmutil import Served, Spent, Text
from btcopilot.models import ModelCall, Statement, TokenMeter
from btcopilot.models.modelcall import Purpose
from btcopilot.tests.conftest import Model, csrf_token, said
from btcopilot.tests.test_turnhistory import coach

READ = "Ada Hale, born 1950. Married Hugh Hale 1974."


@pytest.fixture
def token(web):
    return csrf_token(web)


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


def test_a_read_that_fails_keeps_nothing_and_frees_the_session(
    web, token, monkeypatch
):
    # R-0829
    def broken(content, **kwargs):
        raise RuntimeError("the model went away")

    monkeypatch.setattr("btcopilot.metered.claude_text_sync", broken)
    coach(monkeypatch, Model(said("Thank you.")))
    assert send(web, token, "page.pdf", pdf()).status_code == 500
    assert Statement.query.count() == 0
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


def test_the_answer_to_a_send_carries_the_file_name_and_its_text(web, token, monkeypatch, reader):
    # R-0830
    coach(monkeypatch, Model(said("Thank you.")))
    body = send(web, token, "page.pdf", pdf()).get_json()
    assert (body["attachment_name"], body["attachment_text"]) == ("page.pdf", READ)


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
def test_a_read_the_model_declines_or_leaves_empty_fails_the_send_and_keeps_nothing(
    web, token, monkeypatch, stop, words
):
    # R-0829
    monkeypatch.setattr(
        "btcopilot.metered.claude_text_sync",
        lambda content, **kw: Text(words, Spent(), Served("claude-opus-5-5"), stop),
    )
    coach(monkeypatch, Model(said("Thank you.")))
    response = send(web, token, "grave.jpg", photo("JPEG"))
    assert response.status_code == 500
    assert attachments.REFUSED in response.get_data(as_text=True)
    assert Statement.query.count() == 0


def test_a_part_cut_off_at_the_output_limit_fails_the_read_and_keeps_nothing(
    web, token, monkeypatch
):
    # R-0828
    monkeypatch.setattr(
        "btcopilot.metered.claude_text_sync",
        lambda content, **kw: Text(READ, Spent(), Served("claude-opus-5-5"), "max_tokens"),
    )
    coach(monkeypatch, Model(said("Thank you.")))
    response = send(web, token, "diary.pdf", pdf())
    assert response.status_code == 500
    assert attachments.CUT in response.get_data(as_text=True)
    assert Statement.query.count() == 0
