import time
from http import HTTPStatus
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"
EDITION_FILES = ("README.md", "INDEX.md")


class FramePages:
    """The frame expert's concept pages, read from a local directory (dev,
    tests) or the GitHub contents API, cached for `ttl` seconds."""

    def __init__(
        self,
        dir: str | None = None,
        repo: str = "patrickkidd/btcopilot-sources",
        ref: str = "master",
        path: str = "frame/CONCEPTS",
        token: str | None = None,
        ttl: float = 300,
        clock=time.monotonic,
    ):
        self.dir = Path(dir) if dir else None
        self.repo = repo
        self.ref = ref
        self.path = path
        self.token = token
        self.ttl = ttl
        self.clock = clock
        self._cache = {}

    def names(self) -> list[str]:
        return self._get("", self._local_names if self.dir else self._github_names)

    def text(self, name: str) -> str:
        return self._get(f"{name}.md", self._local_text if self.dir else self._github_text)

    def _get(self, key, fetch):
        now = self.clock()
        hit = self._cache.get(key)
        if hit and now - hit[0] < self.ttl:
            return hit[2]
        etag, value = fetch(key, hit[1] if hit else None)
        if value is None:
            value = hit[2]
        self._cache[key] = (now, etag, value)
        return value

    def _local_names(self, key, etag):
        return None, sorted(
            p.stem for p in self.dir.glob("*.md") if p.name not in EDITION_FILES
        )

    def _local_text(self, key, etag):
        p = self.dir / key
        mtime = str(p.stat().st_mtime_ns)
        return mtime, None if mtime == etag else p.read_text()

    def _github(self, key, etag, accept):
        headers = {"Accept": accept, "Authorization": f"Bearer {self.token}"}
        if etag:
            headers["If-None-Match"] = etag
        response = requests.get(
            f"{GITHUB_API}/repos/{self.repo}/contents/{self.path}/{key}".rstrip("/"),
            params={"ref": self.ref},
            headers=headers,
            timeout=10,
        )
        if response.status_code == HTTPStatus.NOT_MODIFIED:
            return etag, None
        response.raise_for_status()
        return response.headers.get("ETag"), response

    def _github_names(self, key, etag):
        etag, response = self._github(key, etag, "application/vnd.github+json")
        if response is None:
            return etag, None
        return etag, sorted(
            e["name"][:-3]
            for e in response.json()
            if e["type"] == "file"
            and e["name"].endswith(".md")
            and e["name"] not in EDITION_FILES
        )

    def _github_text(self, key, etag):
        etag, response = self._github(key, etag, "application/vnd.github.raw+json")
        return etag, None if response is None else response.text
