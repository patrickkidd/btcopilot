"""A file attached to a message, read into plain text once and never kept:
the statement keeps the file's name and that text, and the coach reads only
the text [Oracle: R-0828, R-0829, R-0830]. Text and Markdown are their own
text; a PDF or a photo is read by one model call."""

import base64
import enum
import io
from pathlib import Path

import pillow_heif
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from werkzeug.exceptions import RequestEntityTooLarge, UnsupportedMediaType

from btcopilot import prompts
# The models package before the meter, which the models package imports.
from btcopilot.models import TokenMeter
from btcopilot.models.modelcall import Purpose
from btcopilot.metered import Metered

pillow_heif.register_heif_opener()

MAX_BYTES = 25 * 1024 * 1024
MAX_PAGES = 100
# The longest side a photo is sent at; the model reads no more detail than this.
MAX_SIDE = 1568
READ_TOKENS = 16000

KINDS_SAID = "PDF, JPEG, PNG, HEIC, text and Markdown files"
UNKNOWN = f"The app reads {KINDS_SAID}; this file is none of those."
TOO_BIG = "That file is over 25 MB; the app reads files up to 25 MB."
TOO_LONG = f"That PDF has more than {MAX_PAGES} pages; the app reads up to {MAX_PAGES}."
UNREADABLE = "The app could not open that file."


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
    refused before anything is spent."""

    def __init__(self, name: str, data: bytes):
        self.name = name
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
                pages = len(PdfReader(io.BytesIO(data)).pages)
            except PdfReadError:
                raise UnsupportedMediaType(UNREADABLE)
            if pages > MAX_PAGES:
                raise RequestEntityTooLarge(TOO_LONG)
            self.block = _block("document", "application/pdf", data)
        else:
            self.block = _block("image", "image/jpeg", _jpeg(data))

    def read(self, user_id: int, diagram_id: int, turn_id: str) -> str:
        """The text the coach reads: the file itself for text, else what one
        model call read from it, charged to the person like the coach's own."""
        if self.kind in (Kind.Text, Kind.Markdown):
            return self.text
        meter = Metered(user_id, diagram_id, turn_id, Purpose.Transcribe)
        words = meter.read(
            [self.block, {"type": "text", "text": f"The file is named {self.name}."}],
            prompts.files().fragment("attachment"),
            READ_TOKENS,
        )
        TokenMeter.charge(user_id, meter.spent)
        return words


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
