"""Puts every dashboard in deploy/grafana to Grafana Cloud, over whatever is
there, so the dashboards are what the repository says. Run by every release.

  GRAFANA_URL=https://<stack>.grafana.net GRAFANA_SA_TOKEN=... python bin/grafanapush.py

A refused dashboard raises and stops the release step.
"""

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

DASHBOARDS = Path(__file__).parents[1] / "deploy" / "grafana"


def push(url: str, token: str, path: Path) -> dict:
    request = Request(
        f"{url}/api/dashboards/db",
        data=json.dumps({"dashboard": json.loads(path.read_text()), "overwrite": True}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request) as response:
        return json.load(response)


def main() -> None:
    for path in sorted(DASHBOARDS.glob("*.json")):
        pushed = push(os.environ["GRAFANA_URL"], os.environ["GRAFANA_SA_TOKEN"], path)
        print(f"{path.name}: {pushed['uid']} at version {pushed['version']}")


if __name__ == "__main__":
    main()
