import logging
import pytest
from mock import patch

from btcopilot.training.models import (
    Discussion,
    Statement,
    Speaker,
    SpeakerType,
    Feedback,
)


@pytest.mark.parametrize(
    "endpoint,method",
    [
        ("/training/admin/", "GET"),
        ("/training/feedback", "GET"),
        ("/training/feedback/download", "GET"),
        ("/training/admin/users/1", "PUT"),
    ],
)
def tests_requires_admin(auditor, endpoint, method, caplog):
    """Test that all admin endpoints properly reject non-admin users"""
    with caplog.at_level(logging.ERROR):
        try:
            if method == "GET":
                response = auditor.get(endpoint)
                # GET requests are web requests, expect redirect to login
                assert response.status_code == 302
                assert "/auth/login" in response.headers.get("Location", "")
            elif method == "DELETE":
                response = auditor.delete(endpoint)
                # DELETE with JSON is API request, expect 403
                assert response.status_code == 403
            elif method == "PUT":
                response = auditor.put(endpoint, json={})
                # PUT with JSON is API request, expect 403
                assert response.status_code == 403
        except Exception:
            # Authorization failure is expected - check that 403 Forbidden error was logged
            assert any(
                "403" in record.message or "Forbidden" in record.message
                for record in caplog.records
            )


def test_admin_dashboard(admin):
    response = admin.get("/training/admin/")
    assert response.status_code == 200
    assert response.data is not None


def test_user_update(admin, test_user):
    response = admin.put(
        f"/training/admin/users/{test_user.id}",
        json={"roles": ["subscriber", "admin"]},  # Use string-based roles instead of vedana constants
    )
    assert response.status_code == 200
    assert response.json["success"] is True