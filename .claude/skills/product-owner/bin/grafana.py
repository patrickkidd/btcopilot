"""Read-only numbers from the laptop's Grafana for the product owner run, as
counts only: every panel of the repository's dashboards over the last 30 days,
LogsQL counts from VictoriaLogs, and failed traces from VictoriaTraces
(doc/MONITORING.md). Grafana at http://127.0.0.1:3000 as admin, with
GF_SECURITY_ADMIN_PASSWORD from the main clone's deploy/laptop/.env;
FD_GRAFANA_URL and FD_GRAFANA_PASSWORD override them. The password is never
printed.

    python3 grafana.py panels
    python3 grafana.py logsql '<query>' ['<query>' ...]
    python3 grafana.py traces
"""

import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from statistics import mean

from files import REPO, clone

DASHBOARDS = REPO / "deploy" / "grafana"
DAY = 86400
# The dashboards' template variables, set to everyone their own queries allow.
VARIABLES = {
    "${people:sqlstring}": "select username from users",
    "${exclude}": "claude-test",
    "$user": "select id from users",
}


def password():
    lines = (clone() / "deploy" / "laptop" / ".env").read_text().splitlines()
    pairs = dict(x.split("=", 1) for x in lines if "=" in x and not x.startswith("#"))
    return pairs["GF_SECURITY_ADMIN_PASSWORD"]


def env():
    url = os.environ.get("FD_GRAFANA_URL", "http://127.0.0.1:3000")
    secret = os.environ.get("FD_GRAFANA_PASSWORD") or password()
    return url, base64.b64encode(f"admin:{secret}".encode()).decode()


URL, AUTH = env()


def call(path, body=None):
    request = urllib.request.Request(
        f"{URL}{path}",
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Basic {AUTH}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def sql(panel):
    target = panel["targets"][0]
    text = target.get("rawSql") or target["expr"]
    for name, value in VARIABLES.items():
        text = text.replace(name, value)
    return text


def summary(panel, frames):
    now = time.time() * 1000
    if panel["type"] == "table":
        rows, columns = 0, {}
        for frame in frames:
            fields, values = frame["schema"]["fields"], frame["data"]["values"]
            rows += len(values[0]) if values else 0
            for field, column in zip(fields, values):
                if field.get("type") == "number":
                    columns[field["name"]] = round(sum(v or 0 for v in column), 4)
        return {"rows": rows, "column_sums": columns}
    points, timed, series = [], False, 0
    for frame in frames:
        fields, values = frame["schema"]["fields"], frame["data"]["values"]
        times = next(
            (c for f, c in zip(fields, values) if f.get("type") == "time"), None
        )
        timed = timed or times is not None
        for field, column in zip(fields, values):
            if field.get("type") == "number":
                series += 1
                points += [
                    (t, v) for t, v in zip(times or [now] * len(column), column) if v is not None
                ]
    if not timed:
        return {"total_30d": round(sum(v for _, v in points), 4)}
    week = [v for t, v in points if t >= now - 7 * DAY * 1000]
    last = [v for t, v in points if t == max((t for t, _ in points), default=None)]
    # A panel whose query divides or averages draws a rate a day: its days are
    # averaged, never added.
    fold = mean if "/" in sql(panel) or "avg(" in sql(panel).lower() else sum
    name = "mean" if fold is mean else "total"
    return {
        "series": series,
        f"{name}_30d": round(fold(v for _, v in points), 4) if points else None,
        f"{name}_7d": round(fold(week), 4) if week else None,
        "latest": round(fold(last), 4) if last else None,
    }


def panels():
    out = {}
    for path in sorted(DASHBOARDS.glob("*.json")):
        dashboard = json.loads(path.read_text())
        held = call(f"/api/dashboards/uid/{dashboard['uid']}")["dashboard"]
        found = {
            "in_grafana_matches_repo": len(held["panels"]) == len(dashboard["panels"])
        }
        for panel in dashboard["panels"]:
            if not panel.get("targets"):
                continue
            target = panel["targets"][0]
            query = {**target, "refId": "A", "datasource": panel["datasource"]}
            query["rawSql" if "rawSql" in target else "expr"] = sql(panel)
            query["format"] = target.get("format", "time_series")
            answer = call(
                "/api/ds/query", {"from": "now-30d", "to": "now", "queries": [query]}
            )["results"]["A"]
            found[panel["title"]] = (
                {"error": answer["error"]}
                if "error" in answer
                else summary(panel, answer.get("frames", []))
            )
        out[dashboard["title"]] = found
    return out


def logsql(queries):
    out = {}
    for text in queries:
        query = urllib.parse.urlencode({"query": text})
        result = call(
            f"/api/datasources/proxy/uid/fd-vl/select/logsql/stats_query?{query}"
        )["data"]["result"]
        out[text] = sum(float(r["value"][1]) for r in result)
    return out


def traces():
    now = int(time.time())
    window = urllib.parse.urlencode(
        {
            "start": (now - 7 * DAY) * 1_000_000,
            "end": now * 1_000_000,
            "limit": 1000,
            "tags": json.dumps({"error": "true"}),
        }
    )
    jaeger = "/api/datasources/proxy/uid/fd-vt/api"
    found = 0
    for service in call(f"{jaeger}/services")["data"]:
        query = f"{window}&{urllib.parse.urlencode({'service': service})}"
        found += len(call(f"{jaeger}/traces?{query}")["data"])
    return {"failed_traces_7d": found}


if __name__ == "__main__":
    command, args = sys.argv[1], sys.argv[2:]
    print(
        json.dumps(
            {"panels": panels, "logsql": lambda: logsql(args), "traces": traces}[
                command
            ](),
            indent=1,
        )
    )
