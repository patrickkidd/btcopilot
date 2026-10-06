"""Read-only numbers from Grafana for the product owner run, as counts only:
every panel of the repository's dashboards over the last 30 days, LogQL
counts, and failed traces. Grafana Cloud by default, with GRAFANA_URL and
GRAFANA_SA_TOKEN from the main clone's .env; FD_GRAFANA_URL and FD_GRAFANA_TOKEN
in the environment point it at another Grafana, such as the laptop's
http://localhost:3000 (doc/MONITORING.md). The token is never printed.

    python3 grafana.py panels
    python3 grafana.py logql '<expr>' ['<expr>' ...]
    python3 grafana.py traces
"""

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


def env():
    lines = (clone() / ".env").read_text().splitlines()
    pairs = dict(x.split("=", 1) for x in lines if "=" in x and not x.startswith("#"))
    cloud = f"https://{pairs['GRAFANA_URL'].removeprefix('https://')}"
    url = os.environ.get("FD_GRAFANA_URL", cloud)
    return url, os.environ.get("FD_GRAFANA_TOKEN", pairs["GRAFANA_SA_TOKEN"])


URL, TOKEN = env()


def call(path, body=None):
    request = urllib.request.Request(
        f"{URL}{path}",
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def sql(panel):
    text = panel["targets"][0]["rawSql"]
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
            query = {
                "refId": "A",
                "datasource": panel["datasource"],
                "rawSql": sql(panel),
                "format": panel["targets"][0].get("format", "time_series"),
            }
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


def logql(exprs):
    now = int(time.time())
    out = {}
    for expr in exprs:
        query = urllib.parse.urlencode({"query": expr, "time": f"{now}000000000"})
        result = call(
            f"/api/datasources/proxy/uid/grafanacloud-logs/loki/api/v1/query?{query}"
        )["data"]["result"]
        out[expr] = sum(float(r["value"][1]) for r in result)
    return out


def traces():
    now = int(time.time())
    query = urllib.parse.urlencode(
        {"q": "{ status = error }", "start": now - 7 * DAY, "end": now, "limit": 1000}
    )
    found = call(
        f"/api/datasources/proxy/uid/grafanacloud-traces/api/search?{query}"
    ).get("traces", [])
    return {"failed_traces_7d": len(found)}


if __name__ == "__main__":
    command, args = sys.argv[1], sys.argv[2:]
    print(
        json.dumps(
            {"panels": panels, "logql": lambda: logql(args), "traces": traces}[
                command
            ](),
            indent=1,
        )
    )
