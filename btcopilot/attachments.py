"""A file attached to a message, read into plain text once and never kept:
the statement keeps the file's name and that text, and the coach reads only
the text [Oracle: R-0828, R-0829, R-0830]. Text and Markdown are their own
text, stored with the words in the request. A PDF or a photo is read by the
model, a call per part, which takes longer than a request may sit open, so
the request checks it and leaves its bytes in Redis for an hour, and the
worker reads it there before the coach's turn, then lets the bytes go."""

import base64
import enum
import io
import time
from collections.abc import Callable
from pathlib import Path

import pillow_heif
import redis
from flask import current_app
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from werkzeug.exceptions import (
    InternalServerError,
    RequestEntityTooLarge,
    UnsupportedMediaType,
)

from btcopilot import prompts
# The models package before the meter, which the models package imports.
from btcopilot.models import TokenMeter
from btcopilot.models.modelcall import Purpose
from btcopilot.metered import Metered
from btcopilot.turnlog import TurnLogBackend

pillow_heif.register_heif_opener()

# The model's request limit is 32 MB, and a file grows by a third when encoded.
MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 100
# Pages read in one call, so a long PDF's text fits one call's output.
CHUNK_PAGES = 25
# The longest side a photo is sent at; the model reads no more detail than this.
MAX_SIDE = 1568
READ_TOKENS = 16000
CUT_OFF = "max_tokens"
DECLINED = "refusal"
# How long a file waits in Redis for the worker to read it. The worker takes
# it within seconds while it is up; a file nobody read is gone within the hour.
HELD_TTL = 3600

KINDS_SAID = "PDF, JPEG, PNG, HEIC, text and Markdown files"
UNKNOWN = f"The app reads {KINDS_SAID}; this file is none of those."
TOO_BIG = "That file is over 20 MB; the app reads files up to 20 MB."
TOO_LONG = f"That PDF has more than {MAX_PAGES} pages; the app reads up to {MAX_PAGES}."
UNREADABLE = "The app could not open that file."
CUT = "That file holds more than the app can read in one go; send it in parts."
REFUSED = "The app could not read that file."
GONE = "The app no longer has that file; send it again."


class Gone(Exception):
    """The worker came for a file the hour had already taken."""


class Kind(enum.StrEnum):
    Pdf = "pdf"
    Jpeg = "jpeg"
    Png = "png"
    Heic = "heic"
    Text = "text"
    Markdown = "markdown"


SUFFIXES = {
    ".pdf": Kind.Pdf,
    ".jpg": Kind.Jpeg,
    ".jpeg": Kind.Jpeg,
    ".png": Kind.Png,
    ".heic": Kind.Heic,
    ".heif": Kind.Heic,
    ".txt": Kind.Text,
    ".text": Kind.Text,
    ".md": Kind.Markdown,
    ".markdown": Kind.Markdown,
}
IMAGES = (Kind.Jpeg, Kind.Png, Kind.Heic)


class File:
    """An attached file, checked: a kind the app reads, within its size and
    pages. Its contents are made ready for reading here, so a file refused is
    refused before anything is stored or spent. A text file is its own text at
    once (`ready`); a PDF or a photo keeps its bytes for the worker to read."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self.data = data
        self.kind = SUFFIXES.get(Path(name).suffix.lower())
        if self.kind is None:
            raise UnsupportedMediaType(UNKNOWN)
        if len(data) > MAX_BYTES:
            raise RequestEntityTooLarge(TOO_BIG)
        if self.kind in (Kind.Text, Kind.Markdown):
            try:
                self.text = data.decode("utf-8")
            except UnicodeDecodeError:
                raise UnsupportedMediaType(UNREADABLE)
        elif self.kind is Kind.Pdf:
            try:
                pages = PdfReader(io.BytesIO(data)).pages
            except PdfReadError:
                raise UnsupportedMediaType(UNREADABLE)
            if len(pages) > MAX_PAGES:
                raise RequestEntityTooLarge(TOO_LONG)
            self.parts = _chunks(name, pages)
        else:
            self.parts = [
                [_block("image", "image/jpeg", _jpeg(data)), _said(f"The file is named {name}.")]
            ]

    @property
    def ready(self) -> bool:
        """Whether the text is in hand with no model call: text and Markdown."""
        return self.kind in (Kind.Text, Kind.Markdown)

    def read(
        self,
        user_id: int,
        diagram_id: int,
        turn_id: str,
        keep: Callable[[], None] | None = None,
    ) -> str:
        """The text the coach reads: the file itself for text, else what the
        model read from it, one call a part, charged to the person like the
        coach's own. A part cut off at the output limit fails the read, so no
        cut text is ever kept. `keep` is called before each part, so the turn
        reading a long file holds its session through every call."""
        if self.ready:
            return self.text
        meter = Metered(user_id, diagram_id, turn_id, Purpose.Transcribe)
        words = []
        try:
            for part in self.parts:
                if keep:
                    keep()
                said = meter.read(part, prompts.files().fragment("attachment"), READ_TOKENS)
                if said.stop == CUT_OFF:
                    raise InternalServerError(CUT)
                if said.stop == DECLINED or not said.words.strip():
                    raise InternalServerError(REFUSED)
                words.append(said.words)
        finally:
            TokenMeter.charge(user_id, meter.spent)
        return "\n\n".join(words)


def read_held(
    turn_id: str,
    name: str,
    user_id: int,
    diagram_id: int,
    keep: Callable[[], None] | None = None,
) -> str:
    """The worker's read of the file the request left for this turn: the same
    checks, parts, calls, ledger rows and charge as reading it in the request
    would be. A file the hour already took is Gone."""
    data = held(turn_id)
    if data is None:
        raise Gone(GONE)
    return File(name, data).read(user_id, diagram_id, turn_id, keep)


def why(error: Exception) -> str | None:
    """The read's own words for how it ended, when it ended its own way: cut
    off, declined or left empty, or gone from Redis. None for anything else,
    which is a fault, not a reading."""
    if isinstance(error, Gone):
        return str(error)
    if isinstance(error, InternalServerError) and error.description in (CUT, REFUSED):
        return error.description
    return None


def _key(turn_id: str) -> str:
    return f"attachment:{turn_id}"


class RedisFiles:
    """Where a file waits for the worker in the box: the queue's own Redis,
    under the turn's key, for HELD_TTL."""

    def __init__(self, client: redis.Redis):
        self.redis = client

    def hold(self, turn_id: str, data: bytes) -> None:
        self.redis.set(_key(turn_id), data, ex=HELD_TTL)

    def held(self, turn_id: str) -> bytes | None:
        return self.redis.get(_key(turn_id))

    def drop(self, turn_id: str) -> None:
        self.redis.delete(_key(turn_id))


class MemoryFiles:
    """The same in one process, which is what the tests and a stack with no
    separate worker use."""

    def __init__(self):
        self.files: dict[str, tuple[bytes, float]] = {}

    def hold(self, turn_id: str, data: bytes) -> None:
        self.files[turn_id] = (data, time.time() + HELD_TTL)

    def held(self, turn_id: str) -> bytes | None:
        found = self.files.get(turn_id)
        if found is None:
            return None
        data, until = found
        if until <= time.time():
            self.drop(turn_id)
            return None
        return data

    def drop(self, turn_id: str) -> None:
        self.files.pop(turn_id, None)


_files = None


def use(store) -> None:
    """The tests put their own store in; nothing else calls this."""
    global _files
    _files = store


def files():
    """The store the turn log's setting names: Redis where the worker is its
    own process, memory where everything runs in one."""
    global _files
    if _files is None:
        if current_app.config["TURN_LOG"] == TurnLogBackend.Memory:
            _files = MemoryFiles()
        else:
            _files = RedisFiles(
                redis.Redis.from_url(current_app.config["CELERY_BROKER_URL"])
            )
    return _files


def hold(turn_id: str, data: bytes) -> None:
    files().hold(turn_id, data)


def held(turn_id: str) -> bytes | None:
    return files().held(turn_id)


def drop(turn_id: str) -> None:
    files().drop(turn_id)


def _chunks(name: str, pages) -> list[list[dict]]:
    """A PDF as parts of CHUNK_PAGES pages, each its own document block."""
    parts = []
    for first in range(0, len(pages), CHUNK_PAGES):
        out = PdfWriter()
        for page in pages[first : first + CHUNK_PAGES]:
            out.add_page(page)
        data = io.BytesIO()
        out.write(data)
        said = f"The file is named {name}."
        if len(pages) > CHUNK_PAGES:
            last = min(first + CHUNK_PAGES, len(pages))
            said += f" These are its pages {first + 1} to {last} of {len(pages)}."
        parts.append([_block("document", "application/pdf", data.getvalue()), _said(said)])
    return parts


def _said(text: str) -> dict:
    return {"type": "text", "text": text}


def _block(kind: str, media_type: str, data: bytes) -> dict:
    return {
        "type": kind,
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.b64encode(data).decode(),
        },
    }


def _jpeg(data: bytes) -> bytes:
    """A photo of any of the kinds read, as a JPEG no larger than the model
    reads."""
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise UnsupportedMediaType(UNREADABLE)
    image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85)
    return out.getvalue()
