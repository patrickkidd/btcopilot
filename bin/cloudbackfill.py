"""Copies what Grafana Cloud still holds into the laptop stores of
deploy/laptop/compose.yml: metrics at their native resolution into
VictoriaMetrics, logs (browser logs among them) into VictoriaLogs, traces into
VictoriaTraces. Prints, per signal, the count Grafana Cloud reports for the
window beside the count the laptop store then holds.

  GRAFANA_URL=... GRAFANA_SA_TOKEN=... uv run python bin/cloudbackfill.py [--since ISO] [--until ISO]

Re-runnable up to the cutover without duplicates: VictoriaMetrics drops a
sample it already holds at the same timestamp; a log line or a trace already
held is skipped.
"""

import argparse
import json
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROM = "grafanacloud-prom"
LOKI = "grafanacloud-logs"
TEMPO = "grafanacloud-traces"
VM = "http://127.0.0.1:8428"
VL = "http://127.0.0.1:9428"
VT = "http://127.0.0.1:10428"
SOURCE = "grafana-cloud"
LOGS = '{service_name=~".+"}'
BROWSER = '{kind=~".+"}'
DROPPED = {"__time_shard__"}
HOUR = 3600
DAY = 86400
LOKI_LIMIT = 5000
TEMPO_LIMIT = 1000
THREADS = 6
ATTEMPTS = 8
TIMEOUT = 120
NS = 10**9
NDJSON = {"Content-Type": "application/x-ndjson"}
SETTLE = 300


def call(url: str, params: dict | None = None, data: bytes | None = None, headers=None) -> bytes:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, data=data, headers=headers or {})
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                return response.read()
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == ATTEMPTS:
                raise RuntimeError(f"{error.code} {url}: {error.read()[:500]!r}") from error
        except (URLError, HTTPException, ConnectionError, TimeoutError):
            if attempt == ATTEMPTS:
                raise
        time.sleep(2**attempt)


class Cloud:
    def __init__(self, url: str, token: str):
        base = url if "://" in url else f"https://{url}"
        self.proxy = f"{base}/api/datasources/proxy/uid"
        self.auth = {"Authorization": f"Bearer {token}"}

    def get(self, uid: str, path: str, params: dict, accept: str | None = None) -> bytes:
        headers = self.auth | ({"Accept": accept} if accept else {})
        return call(f"{self.proxy}/{uid}{path}", params, headers=headers)

    def json(self, uid: str, path: str, params: dict) -> dict:
        return json.loads(self.get(uid, path, params))


def logsql(base: str, query: str) -> list[dict]:
    body = call(f"{base}/select/logsql/query", data=urlencode({"query": query}).encode())
    return [json.loads(line) for line in body.decode().splitlines() if line]


def stamp(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def span(start: int, end: int) -> str:
    return f"_time:[{stamp(start)}, {stamp(end)})"


def nanos(rfc3339: str) -> int:
    whole, _, rest = rfc3339.rstrip("Z").partition(".")
    seconds = datetime.fromisoformat(whole).replace(tzinfo=timezone.utc).timestamp()
    return int(seconds) * NS + int((rest or "0").ljust(9, "0")[:9])


def windows(start: int, end: int, size: int) -> list[tuple[int, int]]:
    edges = list(range(start - start % size, end, size))[1:]
    bounds = [start, *edges, end]
    return list(zip(bounds, bounds[1:]))


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def exposition(series: dict) -> str:
    labels = dict(series["metric"])
    name = labels.pop("__name__")
    inner = ",".join(f'{k}="{escape(v)}"' for k, v in sorted(labels.items()))
    return "".join(
        f"{name}{{{inner}}} {value} {round(ts * 1000)}\n" for ts, value in series["values"]
    )


def metrics(cloud: Cloud, since: int, until: int) -> tuple[int, int, int]:
    names = cloud.json(PROM, "/api/v1/label/__name__/values", {"start": since, "end": until})[
        "data"
    ]

    def copy(job: tuple[str, int, int]) -> tuple[int, int]:
        name, start, end = job
        selector = f'{{__name__="{name}"}}[{end - start}s]'
        count = {"query": f"sum(count_over_time({selector}))", "time": end}
        expected = total(cloud.json(PROM, "/api/v1/query", count)["data"])
        query = {"query": selector, "time": end}
        result = cloud.json(PROM, "/api/v1/query", query)["data"]["result"]
        if result:
            call(
                f"{VM}/api/v1/import/prometheus",
                data="".join(map(exposition, result)).encode(),
            )
        return sum(len(s["values"]) for s in result), expected

    jobs = [(n, s, e) for n in names for s, e in windows(since, until, DAY)]
    with ThreadPoolExecutor(THREADS) as pool:
        copied, expected = map(sum, zip(*pool.map(copy, jobs)))
    call(f"{VM}/internal/force_flush", data=b"")
    seen = 0
    for start, end in windows(since, until, DAY):
        count = f'sum(count_over_time({{__name__=~".+"}}[{end - start}s]))'
        seen += total(json.loads(call(f"{VM}/api/v1/query", {"query": count, "time": end}))["data"])
    return copied, expected, seen


def total(data: dict) -> int:
    return sum(int(float(r["value"][1])) for r in data["result"])


def entries(cloud: Cloud, start: int, end: int) -> list[dict]:
    params = {
        "query": LOGS,
        "start": start * NS,
        "end": end * NS,
        "limit": LOKI_LIMIT,
        "direction": "forward",
    }
    streams = cloud.json(LOKI, "/loki/api/v1/query_range", params)["data"]["result"]
    found = [
        {**fields(s["stream"]), "_time": int(ts), "_msg": line}
        for s in streams
        for ts, line in s["values"]
    ]
    if len(found) < LOKI_LIMIT:
        return found
    middle = (start + end) // 2
    return entries(cloud, start, middle) + entries(cloud, middle, end)


def fields(labels: dict) -> dict:
    kept = {k: v for k, v in labels.items() if k not in DROPPED}
    container = {"CONTAINER_NAME": kept["container"]} if "container" in kept else {}
    return kept | container | {"source": SOURCE}


def hour(cloud: Cloud, window: tuple[int, int]) -> int:
    start, end = window
    rows = logsql(VL, f"{span(start, end)} source:={SOURCE} | fields _time, _msg")
    held = Counter((nanos(r["_time"]), r.get("_msg", "")) for r in rows)
    fresh = []
    for entry in entries(cloud, start, end):
        key = (entry["_time"], entry["_msg"])
        if held[key]:
            held[key] -= 1
        else:
            fresh.append(entry)
    if not fresh:
        return 0
    body = "".join(json.dumps(e) + "\n" for e in fresh).encode()
    params = {
        "_stream_fields": "source,service_name,container,kind",
        "_time_field": "_time",
    }
    call(f"{VL}/insert/jsonline?{urlencode(params)}", data=body, headers=NDJSON)
    return len(fresh)


def logs(cloud: Cloud, since: int, until: int) -> tuple[int, int, int, int, int]:
    with ThreadPoolExecutor(THREADS) as pool:
        copied = sum(pool.map(lambda w: hour(cloud, w), windows(since, until, HOUR)))
    call(f"{VL}/internal/force_flush", data=b"")
    held = logsql(VL, f"{span(since, until)} source:={SOURCE} | stats count() n")
    browser = logsql(VL, f"{span(since, until)} source:={SOURCE} kind:* | stats count() n")
    return (
        copied,
        loki_count(cloud, LOGS, since, until),
        int(held[0]["n"]),
        loki_count(cloud, BROWSER, since, until),
        int(browser[0]["n"]),
    )


def loki_count(cloud: Cloud, selector: str, since: int, until: int) -> int:
    def one(window: tuple[int, int]) -> int:
        start, end = window
        query = f"sum(count_over_time({selector}[{end - start}s]))"
        data = cloud.json(LOKI, "/loki/api/v1/query", {"query": query, "time": end * NS})["data"]
        return total(data)

    with ThreadPoolExecutor(THREADS) as pool:
        return sum(pool.map(one, windows(since, until, HOUR)))


def search(cloud: Cloud, start: int, end: int) -> set[str]:
    params = {"q": "{}", "start": start, "end": end, "limit": TEMPO_LIMIT, "spss": 1}
    found = cloud.json(TEMPO, "/api/search", params).get("traces", [])
    if len(found) == TEMPO_LIMIT and end - start > 1:
        middle = (start + end) // 2
        return search(cloud, start, middle) | search(cloud, middle, end)
    return {t["traceID"].zfill(32) for t in found}


def span_count(cloud: Cloud, since: int, until: int) -> int:
    counted = 0
    for start, end in windows(since, until, DAY):
        params = {"q": "{} | count_over_time()", "start": start, "end": end, "step": "1h"}
        series = cloud.json(TEMPO, "/api/metrics/query_range", params)["series"]
        counted += sum(
            int(v.get("value", 0))
            for s in series
            for v in s["samples"]
            if start <= int(v["timestampMs"]) // 1000 < end
        )
    return counted


def traces(cloud: Cloud, since: int, until: int) -> tuple[int, int, int, int, int]:
    with ThreadPoolExecutor(THREADS) as pool:
        found = set().union(*pool.map(lambda w: search(cloud, *w), windows(since, until, HOUR)))
    reach = span(since - DAY, until + DAY)
    held = {r["trace_id"] for r in logsql(VT, f"{reach} trace_id:* | uniq by (trace_id)")}

    def copy(trace: str) -> int:
        body = cloud.get(TEMPO, f"/api/traces/{trace}", {}, accept="application/protobuf")
        call(
            f"{VT}/insert/opentelemetry/v1/traces",
            data=body,
            headers={"Content-Type": "application/x-protobuf"},
        )
        return 1

    with ThreadPoolExecutor(THREADS) as pool:
        copied = sum(pool.map(copy, [t for t in found if t not in held]))
    call(f"{VT}/internal/force_flush", data=b"")
    traced = logsql(VT, f"{reach} trace_id:* | stats count_uniq(trace_id) t")
    first, last = since - since % HOUR, until - until % HOUR
    spans = logsql(VT, f"{span(first, last)} trace_id:* | stats count() n")
    return (
        copied,
        len(found),
        int(traced[0]["t"]),
        span_count(cloud, first, last),
        int(spans[0]["n"]),
    )


def oldest() -> dict[str, str]:
    seen = {}
    first = json.loads(call(f"{VM}/api/v1/query", {"query": "tfirst_over_time(node_load1[100y])"}))
    values = [float(r["value"][1]) for r in first["data"]["result"]]
    seen["metrics"] = stamp(min(values)) if values else "none"
    for name, base in (("logs", VL), ("traces", VT)):
        rows = logsql(base, "_time:100y | stats min(_time) t")
        seen[name] = rows[0]["t"] if rows else "none"
    return seen


def moment(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp())


def main():
    now = int(time.time())
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--since", type=moment, default=now - 15 * DAY)
    parser.add_argument("--until", type=moment, default=now - SETTLE)
    args = parser.parse_args()
    cloud = Cloud(os.environ["GRAFANA_URL"], os.environ["GRAFANA_SA_TOKEN"])
    print(f"window {stamp(args.since)} to {stamp(args.until)}")
    copied, expected, seen = metrics(cloud, args.since, args.until)
    print(f"metrics samples: copied {copied}, cloud {expected}, laptop {seen}")
    copied, expected, seen, browser, held = logs(cloud, args.since, args.until)
    print(f"log lines: copied {copied}, cloud {expected}, laptop {seen}")
    print(f"browser log lines: cloud {browser}, laptop {held}")
    copied, expected, seen, spans, held = traces(cloud, args.since, args.until)
    print(f"traces: copied {copied}, cloud {expected}, laptop {seen}")
    print(f"spans: cloud {spans}, laptop {held}")
    for signal, at in oldest().items():
        print(f"oldest {signal} on the laptop: {at}")


if __name__ == "__main__":
    main()
