from http import HTTPStatus
from unittest.mock import Mock, patch

from btcopilot.training.framepages import FramePages


def test_text_refreshes_after_ttl(frame_dir):
    now = [0]
    pages = FramePages(dir=frame_dir, clock=lambda: now[0])
    assert pages.names() == ["anxiety", "conflict"]
    assert "Conflict (C)" in pages.text("conflict")

    (frame_dir / "conflict.md").write_text("# Conflict (C), edited\n")
    now[0] = 299
    assert "edited" not in pages.text("conflict")

    now[0] = 301
    assert "edited" in pages.text("conflict")


def test_github_sends_etag_and_keeps_text_on_304():
    now = [0]
    pages = FramePages(token="t", clock=lambda: now[0])
    first = Mock(status_code=HTTPStatus.OK, headers={"ETag": '"v1"'}, text="# Anxiety")
    unchanged = Mock(status_code=HTTPStatus.NOT_MODIFIED)
    with patch("btcopilot.training.framepages.requests.get", side_effect=[first, unchanged]) as get:
        assert pages.text("anxiety") == "# Anxiety"
        now[0] = 301
        assert pages.text("anxiety") == "# Anxiety"
    url = get.call_args.args[0]
    headers = get.call_args.kwargs["headers"]
    assert url == "https://api.github.com/repos/patrickkidd/btcopilot-sources/contents/frame/CONCEPTS/anxiety.md"
    assert headers["If-None-Match"] == '"v1"'
    assert headers["Authorization"] == "Bearer t"
