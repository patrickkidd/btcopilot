"""The integration suite: tests that need a real Postgres, the database
production runs. A run asks for it with --integration and Docker stands up one
Postgres container for the run; without the option every test here is skipped,
so the default suite never starts a database server."""

import subprocess
import time
import uuid

import pytest
import sqlalchemy as sa

IMAGE = "postgres:16"
PASSWORD = "integration"
READY_TRIES = 120


def docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def ready(engine) -> None:
    for _ in range(READY_TRIES):
        try:
            with engine.connect():
                return
        except sa.exc.OperationalError:
            time.sleep(0.5)
    raise RuntimeError("the Postgres container did not come up")


@pytest.fixture(scope="session")
def server(request):
    """One Postgres container for the run, on a port Docker picks."""
    if not request.config.getoption("--integration"):
        pytest.skip("need --integration: starts a Postgres container with Docker")
    name = f"fd-integration-{uuid.uuid4().hex[:8]}"
    docker(
        "run", "--rm", "-d", "--name", name,
        "-e", f"POSTGRES_PASSWORD={PASSWORD}",
        "-p", "127.0.0.1::5432",
        IMAGE,
    )  # fmt: skip
    try:
        port = docker("port", name, "5432/tcp").splitlines()[0].rsplit(":", 1)[1]
        uri = f"postgresql://postgres:{PASSWORD}@127.0.0.1:{port}"
        engine = sa.create_engine(f"{uri}/postgres", isolation_level="AUTOCOMMIT")
        ready(engine)
        yield uri, engine
        engine.dispose()
    finally:
        docker("rm", "-f", name)


@pytest.fixture
def postgres(server):
    """An empty database of the test's own."""
    uri, engine = server
    name = f"t{uuid.uuid4().hex}"
    with engine.connect() as connection:
        connection.execute(sa.text(f'CREATE DATABASE "{name}"'))
    yield f"{uri}/{name}"
    with engine.connect() as connection:
        connection.execute(sa.text(f'DROP DATABASE "{name}" WITH (FORCE)'))
