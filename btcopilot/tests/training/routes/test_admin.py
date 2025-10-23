import logging
import pytest
from mock import patch

import vedana
from btcopilot.extensions import db
from btcopilot.pro.models import User
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.training.models import Feedback


# @pytest.mark.parametrize(
#     "endpoint,method",
#     [
#         ("/training/admin/", "GET"),
#         ("/training/feedback", "GET"),
#         ("/training/feedback/download", "GET"),
#         ("/training/admin/users/1", "PUT"),
#     ],
# )
# def tests_requires_admin(logged_in, endpoint, method, caplog):
#     """Test that all admin endpoints properly reject non-admin users"""
#     with patch("btcopilot.training.utils.check_admin_access", return_value=False):
#         with caplog.at_level(logging.ERROR):
#             try:
#                 response = logged_in.get(endpoint)
#                 # GET requests are web requests, expect redirect to login
#                 # assert response.status_code == 302
#                 # assert "/auth/login" in response.headers.get("Location", "")
#             except Exception:
#                 # Authorization failure is expected - check that 403 Forbidden error was logged
#                 assert any(
#                     "403" in record.message or "Forbidden" in record.message
#                     for record in caplog.records
#                 ), f"{[x for x in caplog.records]} did not contain '403' or 'Forbidden'"


def test_admin_dashboard(admin):
    response = admin.get("/training/admin/")
    assert response.status_code == 200
    assert response.data is not None


def test_user_update(admin, test_user):
    response = admin.put(
        f"/training/admin/users/{test_user.id}",
        json={"roles": [vedana.ROLE_SUBSCRIBER, vedana.ROLE_ADMIN]},
    )
    assert response.status_code == 200
    assert response.json["success"] is True
