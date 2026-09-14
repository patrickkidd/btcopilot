"""The one-shot read of the old Pro database into this one (platform build
step 7). The importer itself is not written yet; these are the two calls the
command line makes, so that the day it lands nothing above it changes."""

NOT_BUILT = (
    "the importer is not written yet (platform build step 7). "
    "When it lands, replace these two calls with it."
)


def dry_run(dump: str) -> list[dict]:
    """Counts in against counts out, and every record that would fail, without
    writing anything."""
    raise NotImplementedError(NOT_BUILT)


def run(dump: str) -> list[dict]:
    """The same read, writing the users and the converted records."""
    raise NotImplementedError(NOT_BUILT)
