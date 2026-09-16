"""No real names, emails, case identifiers or clinical transcripts in this repo.
The files that had them were moved to the corpus folder outside every repo; this
fails if one comes back, or if a new one arrives that looks like it."""

import re
import subprocess


from btcopilot.tests.repo import REPO

# A recording's transcript, or anything filed under a meetings folder that is
# not one of its templates.
MEETING = re.compile(
    r"\.(vtt|srt)$|(^|/)meetings/(?!TEMPLATE\.md|DELIBERATION_TEMPLATE\.md)",
    re.I,
)
DUMP = re.compile(r"\.(db|sqlite3?|dump|mdb)$", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.I)
# Every address the tree holds today, each one a test fixture, the stand-in
# family, a published research contact, or Patrick's own. A new one fails until
# it is added here on purpose.
ALLOWED_EMAIL = {
    "admin_auditor@example.com",
    "auditor1@example.com",
    "auditor2@example.com",
    "ballot1@fd362-fixture.invalid",
    "ballot3@fd362-fixture.invalid",
    "coach@example.com",
    "coach@fd362.invalid",
    "coach_chat@example.com",
    "corinne.whitlock@northmail.net",
    "dev-team@example.com",
    "diagram_auditor@example.com",
    "enterprise@assemblyai.com",
    "expert@example.com",
    "fd338-uitest@example.com",
    "icouzin@ab.mpg",
    "invited+unittest@gmail.com",
    "john.doe@example.com",
    "lli@ab.mpg",
    "marcus@fd362-fixture.invalid",
    "me@there.com",
    "n.okafor@twoharborscounseling.net",
    "new@fd362-fixture.invalid",
    "nobody+unittest@gmail.com",
    "nobody@x.com",
    "noone@none.com",
    "noreply@anthropic.com",
    "other_auditor@example.com",
    "patrick+fd321walk@example.com",
    "pro@fd362-fixture.invalid",
    "table@fd362-fixture.invalid",
    "patrick@alaskafamilysystems.com",
    "patrick@database.familydiagram",
    "patrick@example.com",
    "patrickkidd+beta@gmail.com",
    "patrickkidd+unittest+2@gmail.com",
    "patrickkidd+unittest@gmail.com",
    "patrickkidd@gmail.com",
    "s.a@example.com",
    "session_auditor@example.com",
    "test@example.com",
    "test_auditor@example.com",
    "third_user@test.com",
    "vivekhsridhar@gmail.com",
    "you@example.com",
}
TEXT_SUFFIX = {".py", ".md", ".txt", ".ts", ".js", ".html", ".json", ".yaml", ".yml"}


def tracked() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()


def test_no_meeting_record_of_real_people_is_in_the_repo():
    found = [name for name in tracked() if MEETING.search(name)]
    assert not found, (
        "these name real people and belong in fd-corpus/private, not here: "
        f"{found}"
    )


def test_no_database_dump_is_in_the_repo():
    found = [name for name in tracked() if DUMP.search(name)]
    assert not found, f"a database holds real people's records: {found}"


def test_no_outside_email_address_is_in_the_repo():
    offenders = {}
    for name in tracked():
        path = REPO / name
        if path.suffix.lower() not in TEXT_SUFFIX or not path.is_file():
            continue
        if path.stat().st_size > 2_000_000:
            continue
        found = {
            m.group(0)
            for m in EMAIL.finditer(path.read_text(errors="ignore"))
            if m.group(0).lower() not in ALLOWED_EMAIL
        }
        if found:
            offenders[name] = sorted(found)
    assert not offenders, f"an address that could be a real person's: {offenders}"
