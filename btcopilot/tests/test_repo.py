"""What the repository holds and what has left it."""

import importlib.util
import re

from btcopilot.models import Discussion, DiscussionStatus, Statement
from btcopilot.tests.repo import PACKAGE, REPO

DOC = REPO / "doc"


def test_the_docs_live_at_the_top_and_the_retired_folders_are_gone():
    # R-0420
    assert (DOC / "STATE.md").is_file()
    assert (DOC / "HOW_THIS_PROJECT_WORKS.md").is_file()
    assert not (DOC / "chat-first").exists()
    assert not (DOC / "screens").exists()
    skills = REPO / ".claude" / "skills"
    assert not (skills / "scout").exists()
    assert not (skills / "loop-review").exists()


def test_every_archived_document_opens_with_its_dated_header():
    # R-0420
    archived = sorted((DOC / "archive").glob("*.md"))
    assert archived
    undated = [
        path.name
        for path in archived
        if not re.match(r"> \*\*Archived \d{4}-\d{2}", path.read_text())
    ]
    assert undated == []


def test_the_auto_arrange_code_is_gone():
    # R-0418
    assert importlib.util.find_spec("btcopilot.arrange") is None
    assert not (PACKAGE / "arrange").exists()


def test_the_auto_arrange_analysis_names_the_commit_that_held_the_code():
    # R-0418
    analysis = (DOC / "analyses" / "2026-02-20_auto_arrange.md").read_text()
    assert re.search(r"`btcopilot/arrange`.*commit [0-9a-f]{7,40} is the one to check out", analysis)


def test_nothing_in_the_app_asks_for_an_extraction_prompt():
    # R-0414
    callers = [
        str(path.relative_to(PACKAGE))
        for path in PACKAGE.rglob("*.py")
        if "tests" not in path.parts
        and path.name != "prompts.py"
        and re.search(r"DATA_EXTRACTION_|CURSOR_EXTRACTION_|CURSOR_MARKER_", path.read_text())
    ]
    assert callers == []


def test_the_chat_database_keeps_nothing_of_the_pending_extraction():
    # R-0414
    left = [
        name
        for model, name in (
            (Discussion, "extracting"),
            (Discussion, "extracted_through_order"),
            (Discussion, "pending_extracted_through_order"),
            (Statement, "pdp_deltas"),
        )
        if name in model.__table__.columns
    ]
    left += [s.value for s in DiscussionStatus if "extract" in s.value]
    assert left == []
    schema = (PACKAGE / "migrations" / "versions" / "1b00000000aa_the_app_from_empty.py").read_text()
    assert not re.search(r"extract|pdp_deltas", schema.replace("relative date extraction", ""))
    deploy = (REPO / ".github" / "workflows" / "release.yml").read_text()
    for column in ("extracting", "extracted_through_order", "pending_extracted_through_order", "pdp_deltas"):
        assert f"DROP COLUMN {column}" in deploy
