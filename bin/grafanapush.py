"""Puts every dashboard in deploy/grafana to Grafana Cloud, over whatever is
there, so the dashboards are what the repository says. Run by every release.

  GRAFANA_URL=https://<stack>.grafana.net GRAFANA_SA_TOKEN=... python bin/grafanapush.py

A refused dashboard raises and stops the release step. A stack asleep from idle
answers 503 until it wakes, so that one answer is waited out.
"""

import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

DASHBOARDS = Path(__file__).parents[1] / "deploy" / "grafana"
ATTEMPTS = 6
TIMEOUT = 30
LONGEST_WAIT = 30


def wait(error: HTTPError) -> int:
    after = error.headers.get("Retry-After", "")
    return min(int(after), LONGEST_WAIT) if after.isdigit() else 10


def push(url: str, token: str, path: Path) -> dict:
    request = Request(
        f"{url}/api/dashboards/db",
        data=json.dumps({"dashboard": json.loads(path.read_text()), "overwrite": True}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code != 503 or attempt == ATTEMPTS:
                raise
            time.sleep(wait(error))


def main() -> None:
    for path in sorted(DASHBOARDS.glob("*.json")):
        pushed = push(os.environ["GRAFANA_URL"], os.environ["GRAFANA_SA_TOKEN"], path)
        print(f"{path.name}: {pushed['uid']} at version {pushed['version']}")


if __name__ == "__main__":
    main()
