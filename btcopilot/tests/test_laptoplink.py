import os
import subprocess
from pathlib import Path

import pytest

LINK = Path(__file__).parents[2] / "deploy" / "laptop" / "link" / "link.sh"
NEXT = "s=1f;i=2a"

SSH = f"""#!/bin/sh
for a; do last=$a; done
printf '%s\\n' "$last" >> "$LINK_TMP/sent"
if [ "$BOX" = refuse ]; then
  echo "not a journal cursor" >&2
  exit 2
fi
printf 'MESSAGE=hello\\n__CURSOR={NEXT}\\n\\n'
"""


@pytest.fixture
def link(tmp_path):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "ssh").write_text(SSH)
    (bin_ / "curl").write_text("#!/bin/sh\nexit 0\n")
    for stub in bin_.iterdir():
        stub.chmod(0o755)
    dir_ = tmp_path / "link"
    dir_.mkdir()

    def run(box="ok"):
        env = dict(
            os.environ,
            PATH=f"{bin_}:{os.environ['PATH']}",
            LINK_DIR=str(dir_),
            LINK_TMP=str(tmp_path),
            FD_BOX="box",
            BOX=box,
        )
        out = subprocess.run(
            ["sh", str(LINK), "once"], env=env, capture_output=True, text=True
        )
        sent = tmp_path / "sent"
        return out.stdout, sent.read_text().splitlines() if sent.exists() else None

    run.dir = dir_
    return run


def test_valid_cursor_sent(link):
    # R-0370
    (link.dir / "cursor").write_text("s=0a;i=1")
    out, sent = link()
    assert sent == ["s=0a;i=1"]
    assert (link.dir / "cursor").read_text() == NEXT


def test_missing_cursor_sends_nothing(link):
    # R-0370
    out, sent = link()
    assert sent is None
    assert "cursor ~/fd-monitoring/link/cursor is missing" in out
    assert "touch ~/fd-monitoring/link/approve-repull" in out


def test_corrupt_cursor_sends_nothing(link):
    # R-0370
    (link.dir / "cursor").write_text("s=0a\nrm -rf /")
    out, sent = link()
    assert sent is None
    assert "cursor ~/fd-monitoring/link/cursor is corrupt" in out


def test_approval_sends_empty_once(link):
    # R-0370
    (link.dir / "approve-repull").touch()
    out, sent = link()
    assert sent == [""]
    assert not (link.dir / "approve-repull").exists()
    assert (link.dir / "cursor").read_text() == NEXT
    link()
    _, sent = link()
    assert sent == ["", NEXT, NEXT]


def test_box_refusal_stops(link):
    # R-0370
    (link.dir / "cursor").write_text("s=0a")
    out, sent = link(box="refuse")
    assert sent == ["s=0a"]
    assert "box refused the cursor (exit 2): not a journal cursor" in out
    assert (link.dir / "cursor.refused").read_text() == "s=0a"
    out, sent = link(box="refuse")
    assert sent == ["s=0a"]
    assert "is missing" in out
