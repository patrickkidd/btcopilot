"""The box's collector, as deployed: nothing it takes is dropped while the
laptop is away (doc/MONITORING.md)."""

import yaml

from btcopilot.tests.test_boxsecrets import DEPLOY

CONFIG = yaml.safe_load((DEPLOY / "otel" / "config.yaml").read_text())
COMPOSE = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text())
LAPTOP = ("otlp_http/metrics", "otlp_http/traces")


def test_the_app_and_its_workers_send_traces_to_the_collector():
    # R-0370
    env = COMPOSE["x-app-env"]
    assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://fd-otel:4318"
    assert float(env["OTEL_EXPORTER_OTLP_TIMEOUT"]) >= 30
    assert "./otel/config.yaml:/etc/otel/config.yaml:ro" in COMPOSE["services"]["fd-otel"]["volumes"]


def test_what_goes_to_the_laptop_is_queued_on_disk_and_retried_forever():
    # R-0370
    pipelines = CONFIG["service"]["pipelines"]
    assert set(pipelines["metrics"]["receivers"]) == {"host_metrics", "docker_stats"}
    assert pipelines["traces"]["receivers"] == ["otlp"]
    assert {*pipelines["metrics"]["exporters"], *pipelines["traces"]["exporters"]} >= set(LAPTOP)
    for name in LAPTOP:
        exporter = CONFIG["exporters"][name]
        assert exporter["sending_queue"]["storage"] == "file_storage"
        assert exporter["retry_on_failure"]["max_elapsed_time"] == 0
    queue = CONFIG["extensions"]["file_storage"]["directory"]
    assert any(v.endswith(f":{queue}") for v in COMPOSE["services"]["fd-otel"]["volumes"])


def test_every_container_logs_to_the_hosts_journal():
    # R-0370
    for name, service in COMPOSE["services"].items():
        assert service["logging"]["driver"] == "journald", name


def test_the_queues_hold_30_days_at_one_batch_per_timeout_and_no_more():
    # R-0370
    batch = CONFIG["processors"]["batch"]
    assert batch == {"timeout": "10s", "send_batch_size": 8192}
    for pipeline in CONFIG["service"]["pipelines"].values():
        assert pipeline["processors"] == ["batch"]
    for name in LAPTOP:
        assert CONFIG["exporters"][name]["sending_queue"]["queue_size"] == 260_000
