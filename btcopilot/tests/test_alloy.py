"""The box's telemetry agent, as deployed."""

import re

from btcopilot.tests.test_boxsecrets import DEPLOY

CONFIG = (DEPLOY / "alloy" / "config.alloy").read_text()


def test_alloy_ships_host_metrics_and_container_logs_to_grafana_cloud():
    # R-0370
    compose = (DEPLOY / "docker-compose.yml").read_text()
    assert "image: grafana/alloy" in compose
    assert "./alloy/config.alloy:/etc/alloy/config.alloy" in compose
    assert 'prometheus.exporter.unix "host"' in CONFIG
    assert 'loki.source.docker "containers"' in CONFIG
    pushes = re.findall(r'url\s*=\s*"https://([^/"]+)', CONFIG)
    assert pushes
    assert all(host.endswith(".grafana.net") for host in pushes)
