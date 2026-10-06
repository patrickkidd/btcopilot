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


def test_an_hour_partly_copied_continues_after_its_newest_entry(monkeypatch):
    # R-0370
    held = [{"n": "2", "t": "2026-10-06T18:49:12.000000005Z"}]
    newest = cloudbackfill.nanos(held[0]["t"])
    assert newest % cloudbackfill.NS == 5
    found = [
        {"_time": newest - 1, "_msg": "old"},
        {"_time": newest, "_msg": "held"},
        {"_time": newest + 1, "_msg": "new"},
    ]
    posted = []
    monkeypatch.setattr(cloudbackfill, "logsql", lambda base, query: held)
    monkeypatch.setattr(cloudbackfill, "entries", lambda cloud, start, end: found)
    monkeypatch.setattr(
        cloudbackfill, "call", lambda url, data=None, headers=None: posted.append(data)
    )
    assert cloudbackfill.hour(None, (0, 3600)) == 1
    assert [json.loads(line)["_msg"] for line in posted[0].decode().splitlines()] == ["new"]


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
