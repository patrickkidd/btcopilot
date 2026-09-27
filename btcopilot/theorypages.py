import time
from http import HTTPStatus

import requests

GITHUB_API = "https://api.github.com"
EDITION_FILES = ("README.md", "INDEX.md")


class Unavailable(Exception):
    pass


class TheoryPages:
    """The theory's concept pages, read from the GitHub contents API. Each
    file is held for `ttl` seconds and then revalidated by its ETag, so a push
    to the theory repo shows without a deploy, and nothing older than `ttl` is
    served once GitHub stops answering (FD-364)."""

    def __init__(
        self,
        repo: str,
        ref: str,
        path: str,
        token: str | None,
        ttl: float = 300,
        clock=time.monotonic,
    ):
        self.repo = repo
        self.ref = ref
        self.path = path
        self.token = token
        self.ttl = ttl
        self.clock = clock
        self._cache = {}

    def names(self) -> list[str]:
        return self._get("", "application/vnd.github+json", self._names)

    def text(self, name: str) -> str:
        return self.file(f"{name}.md")

    def file(self, filename: str) -> str:
        return self._get(
            filename, "application/vnd.github.raw+json", lambda r: r.text
        )

    def _get(self, key, accept, parse):
        now = self.clock()
        hit = self._cache.get(key)
        if hit and now - hit[0] < self.ttl:
            return hit[2]
        response = self._fetch(key, accept, hit[1] if hit else None)
        if response.status_code == HTTPStatus.NOT_MODIFIED:
            self._cache[key] = (now, hit[1], hit[2])
        else:
            self._cache[key] = (now, response.headers.get("ETag"), parse(response))
        return self._cache[key][2]

    def _fetch(self, key, accept, etag):
        url = f"{GITHUB_API}/repos/{self.repo}/contents/{self.path}/{key}".rstrip("/")
        if not self.token:
            raise Unavailable(
                f"The concept pages cannot be read from {url}: "
                "FLASK_THEORY_GITHUB_TOKEN is not set."
            )
        headers = {"Accept": accept, "Authorization": f"Bearer {self.token}"}
        if etag:
            headers["If-None-Match"] = etag
        try:
            response = requests.get(
                url, params={"ref": self.ref}, headers=headers, timeout=10
            )
            if response.status_code != HTTPStatus.NOT_MODIFIED:
                response.raise_for_status()
        except requests.RequestException as e:
            raise Unavailable(
                f"The concept pages cannot be read from GitHub ({url}): {e}"
            ) from e
        return response

    @staticmethod
    def _names(response) -> list[str]:
        return sorted(
            e["name"][:-3]
            for e in response.json()
            if e["type"] == "file"
            and e["name"].endswith(".md")
            and e["name"] not in EDITION_FILES
        )
