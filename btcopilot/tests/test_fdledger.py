import datetime

from btcopilot import extensions, fdfile, fdledger
from btcopilot.fdledger import Decision
from btcopilot.tests.fdfixtures import dumps, scene

TODAY = datetime.date(2026, 10, 10)
BECAME = {"person 1": "person 3, Ada Lund", "event 20": "event 6, birth"}


def ledger(decisions=(), **more) -> str:
    return fdledger.text(
        "Lund family.fd",
        fdfile.read(dumps(scene(**more))),
        BECAME,
        list(decisions),
        TODAY,
    )


def section(text: str, title: str) -> str:
    return text.split(f"-- {title} --\n", 1)[1].split("\n\n", 1)[0]


def test_header_names_the_file_version_date_and_counts():
    # R-0873
    head = ledger().split("\n\n", 1)[0]
    assert head.splitlines() == [
        "Family Diagram import record",
        "File: Lund family.fd",
        "Saved by Family Diagram 2.1.23b2",
        "Imported: 2026-10-10",
        "In the file: 3 people, 3 events, 1 pair-bonds, 0 relationship lines",
        "Choices made: 0",
    ]


def test_every_raw_field_kept_flat_with_what_it_became_and_its_choices():
    # R-0873
    choice = Decision(
        "person 1", "name", "", "Cy's mother", "Named by place in the family."
    )
    ada = section(ledger([choice]), "person 1")
    assert "  itemPos: 10.0, 20.0" in ada
    assert "  color: 255, 0, 0, 255" in ada
    assert "  primary: True" in ada
    assert "In the new diagram: person 3, Ada Lund" in ada
    assert (
        'Choice on name: the file said ""; the new diagram has "Cy\'s mother". Named by place in the family.'
        in ada
    )


def test_grouped_by_person_in_file_order_then_the_rest():
    # R-0873
    text = ledger(
        emotions=[
            {"kind": "cutoff", "id": 31, "person": 3, "target": 1, "event": None}
        ],
        layers=[
            {
                "kind": "Layer",
                "id": 30,
                "name": "Work",
                "itemProperties": {"1": {"itemPos": (1.0, 2.0)}},
            }
        ],
    )
    order = [
        text.index(mark)
        for mark in (
            "Ada Lund (person 1)",
            "Bo Lund (person 2)",
            "-- event 22 --",
            "Cy Lund (person 3)",
            "-- event 20 --",
            "-- relationship line 31 --",
            "-- pair-bond 10 --",
            "-- diagram --",
        )
    ]
    assert order == sorted(order)
    assert "  layers 1.itemProperties.1.itemPos: 1.0, 2.0" in text
    assert "In the new diagram: not an item of its own" in section(
        text, "relationship line 31"
    )


def test_secrets_of_the_desktop_file_never_written():
    # R-0873
    text = ledger(password="hunter2", masterKey="k3y")
    assert "hunter2" not in text and "k3y" not in text


def test_mail_says_what_it_is_and_attaches_the_record(flask_app):
    # R-0873
    flask_app.config["MAIL_SERVER"] = "localhost"
    with flask_app.app_context(), extensions.mail.record_messages() as outbox:
        fdledger.send("ada@example.com", "Lund family.fd", "Lund family", "the record")
    [mail] = outbox
    assert mail.recipients == ["ada@example.com"]
    assert mail.reply_to == flask_app.config["ADMIN_EMAIL"]
    assert "Search it for a person's name" in mail.body and "!" not in mail.body
    [attached] = mail.attachments
    assert (attached.filename, attached.data) == (
        "Lund family - import record.txt",
        "the record",
    )
