"""The one-time copy of Grafana Cloud into the laptop stores (bin/cloudbackfill.py)."""

import json

import bin.cloudbackfill as cloudbackfill


def test_a_series_is_written_at_its_own_timestamps_with_its_labels():
    # R-0370
    series = {
        "metric": {"__name__": "node_load1", "job": 'a"b', "instance": "box"},
        "values": [[1791238152.754, "1.02"], [1791238212.754, "NaN"]],
    }
    assert cloudbackfill.exposition(series) == (
        'node_load1{instance="box",job="a\\"b"} 1.02 1791238152754\n'
        'node_load1{instance="box",job="a\\"b"} NaN 1791238212754\n'
    )


def test_windows_cover_the_span_without_gap_or_overlap():
    # R-0370
    spans = cloudbackfill.windows(5000, 12000, 3600)
    assert spans == [(5000, 7200), (7200, 10800), (10800, 12000)]


def test_an_hour_copied_in_part_gets_only_the_lines_it_lacks(monkeypatch):
    # R-0370
    held = [
        {"_time": "2026-10-06T18:49:12.000000005Z", "_msg": "twice"},
        {"_time": "2026-10-06T18:49:13Z", "_msg": "later"},
    ]
    at = cloudbackfill.nanos(held[0]["_time"])
    assert at % cloudbackfill.NS == 5
    found = [
        {"_time": at - 1, "_msg": "earlier"},
        {"_time": at, "_msg": "twice"},
        {"_time": at, "_msg": "twice"},
        {"_time": at + cloudbackfill.NS - 5, "_msg": "later"},
    ]
    posted = []
    monkeypatch.setattr(cloudbackfill, "logsql", lambda base, query: held)
    monkeypatch.setattr(cloudbackfill, "entries", lambda cloud, start, end: found)
    monkeypatch.setattr(
        cloudbackfill, "call", lambda url, data=None, headers=None: posted.append(data)
    )
    assert cloudbackfill.hour(None, (0, 3600)) == 2
    sent = [json.loads(line)["_msg"] for line in posted[0].decode().splitlines()]
    assert sent == ["earlier", "twice"]


def test_a_cloud_log_carries_the_container_field_the_journal_uses():
    # R-0370
    fields = cloudbackfill.fields(
        {
            "container": "familydiagram-fd-app-60",
            "service_name": "fd-app",
            "__time_shard__": "x",
        }
    )
    assert fields == {
        "container": "familydiagram-fd-app-60",
        "service_name": "fd-app",
        "CONTAINER_NAME": "familydiagram-fd-app-60",
        "source": "grafana-cloud",
    }


def test_a_second_with_more_lines_than_a_page_is_read_by_the_nanosecond():
    # R-0370
    lines = [cloudbackfill.NS * 7 + i for i in range(cloudbackfill.LOKI_LIMIT + 3)]

    class Cloud:
        def json(self, uid, path, params):
            got = [t for t in lines if params["start"] <= t < params["end"]]
            values = [[str(t), f"line {t}"] for t in got[: cloudbackfill.LOKI_LIMIT]]
            return {"data": {"result": [{"stream": {"service_name": "fd-app"}, "values": values}]}}

    found = cloudbackfill.entries(Cloud(), 7 * cloudbackfill.NS, 8 * cloudbackfill.NS)
    assert sorted(e["_time"] for e in found) == lines
