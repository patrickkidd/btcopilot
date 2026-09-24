import dataclasses

import pytest

from btcopilot.schema import Cluster


@pytest.mark.xfail(
    strict=True,
    reason="a stored cluster also keeps a title, a summary and a start and end date",
)
def test_a_stored_cluster_keeps_its_name_reason_source_and_events_only():
    # R-0205
    kept = {field.name for field in dataclasses.fields(Cluster)}
    assert kept == {"id", "name", "reason", "source", "eventIds"}
