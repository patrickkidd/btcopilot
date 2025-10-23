import logging
import pytest
from mock import patch

import vedana
from btcopilot.extensions import db
from btcopilot.pro.models import User


@pytest.mark.parametrize(
    "endpoint,method",
    [
        ("/training/stream/", "GET"),
        ("/training/stream/test-sse", "GET"),
    ],
)
def test_requires_auditor_or_admin(subscriber, endpoint, method, caplog):
    """Test that stream endpoints require auditor or admin roles"""
    with patch("btcopilot.training.utils.get_auditor_id", return_value="test_auditor"):
        with caplog.at_level(logging.ERROR):
            if method == "GET":
                response = subscriber.get(endpoint)
                # GET requests are web requests, expect redirect to login
                assert response.status_code == 302
                assert "/auth/login" in response.headers.get("Location", "")
            elif method == "POST":
                response = subscriber.post(endpoint, json={})
                # POST with JSON is API request, expect 403
                assert response.status_code == 403
            elif method == "DELETE":
                response = subscriber.delete(endpoint)
                # DELETE is API request, expect 403
                assert response.status_code == 403


def test_sse_stream_connection(auditor):
    """Test SSE stream connection endpoint"""
    with patch("btcopilot.training.sse.sse_manager.subscribe"):
        response = auditor.get("/training/stream/")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["Content-Type"]


def test_sse_test_endpoint(auditor):
    """Test SSE test endpoint"""
    with patch("btcopilot.training.sse.sse_manager.publish"):
        response = auditor.get("/training/stream/test-sse")
        assert response.status_code == 200
        assert response.json["message"] == "Test SSE message sent"
        assert "subscribers" in response.json


def test_sse_stream_connection(auditor):
    with patch("btcopilot.training.sse.sse_manager.subscribe"):
        response = auditor.get("/training/stream/")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["Content-Type"]


def test_sse_test_endpoint(auditor):
    with patch("btcopilot.training.sse.sse_manager.publish"):
        response = auditor.get("/training/stream/test-sse")
        assert response.status_code == 200
        assert response.json["message"] == "Test SSE message sent"
        assert "subscribers" in response.json
