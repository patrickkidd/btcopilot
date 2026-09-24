"""A finished coding freezes the record it was coded on.

The chat app's own writing routes ask this before they let an edit through, so
a coder cannot keep editing a coding they have already called done. It reads
only the review's own tables, which is what lets the chat app depend on it.
"""

from btcopilot.review.models import Coding


def frozen(diagram_id: int) -> bool:
    """Frozen while every coding on this record is finished. The next cut's
    coding reuses the same record and thaws it by simply not being done."""
    codings = Coding.query.filter(Coding.diagram_id == diagram_id).all()
    return bool(codings) and all(c.done_at is not None for c in codings)
