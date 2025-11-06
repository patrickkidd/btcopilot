import os.path
import json
import pickle
import logging

import pytest
import mock

from btcopilot import extensions


@pytest.fixture(autouse=True)
def _loggers(request):
    # Clear any handlers from previous tests
    logging.getLogger("btcopilot").handlers.clear()

    # Clean up any existing log files to ensure deterministic state
    # Note: This runs after flask_app is created but before test body
    if "flask_app" in request.fixturenames:
        flask_app = request.getfixturevalue("flask_app")
        log_path = os.path.join(flask_app.instance_path, "logs", "flask.json")
        try:
            os.remove(log_path)
        except FileNotFoundError:
            pass  # File doesn't exist yet, which is fine

    yield

    logging.getLogger("btcopilot").handlers.clear()


@pytest.mark.init_datadog
def test_datadog_logs(flask_app, test_user, test_activation, _loggers):
    extensions.init_datadog(flask_app)
    with mock.patch.object(logging.getLogger("btcopilot"), "level", logging.DEBUG):
        with flask_app.test_client(user=test_user) as client:
            response = client.post(
                "/v1/diagrams",
                data=pickle.dumps(
                    {
                        "name": "Test Diagram",
                        "data": b"",
                    }
                ),
            )
            assert response.status_code == 200
            diagram_id = pickle.loads(response.data)["id"]
            assert client.get(f"/v1/diagrams/{diagram_id}").status_code == 200
    with open(os.path.join(flask_app.instance_path, "logs", "flask.json"), "r") as f:
        sdata = f.read()
        logs = [json.loads(line) for line in sdata.split("\n") if line]

    expected_logs = [
        {
            "status": "INFO",
            "message": "POST /v1/diagrams",
            "http": {
                "method": "POST",
                "path": "/v1/diagrams",
            }
        },
        {
            "status": "INFO",
            "message": "Created new diagram",
            "user": {
                "username": test_user.username,
                "name": f"{test_user.first_name} {test_user.last_name}",
            }
        },
        {
            "status": "INFO",
            "message": "GET /v1/diagrams/2",
            "http": {
                "method": "GET",
                "path": "/v1/diagrams/2",
            }
        },
        {
            "status": "INFO",
            "message": "Fetched diagram 2",
            "user": {
                "username": test_user.username,
                "name": f"{test_user.first_name} {test_user.last_name}",
            }
        },
    ]

    assert len(logs) == len(expected_logs)
    for actual, expected in zip(logs, expected_logs):
        for key, value in expected.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    assert actual[key][subkey] == subvalue
            else:
                assert actual[key] == value
