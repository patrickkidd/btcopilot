import pytest
from mock import patch


def test_login_success(anonymous, test_user):
    """Test successful login with stand-in authentication"""
    with patch("btcopilot.training.routes.auth.authenticate_user") as mock_auth:
        mock_auth.return_value = {
            "success": True,
            "user": {
                "id": test_user.id,
                "username": test_user.username,
                "roles": ["auditor"]
            }
        }
        
        response = anonymous.post(
            "/training/auth/login",
            data={"username": test_user.username, "password": "test-password"},
        )
        assert response.status_code == 302  # Redirect on successful login


def test_login_fail(anonymous, test_user):
    """Test failed login"""
    with patch("btcopilot.training.routes.auth.authenticate_user") as mock_auth:
        mock_auth.return_value = {"success": False, "error": "Invalid credentials"}
        
        response = anonymous.post(
            "/training/auth/login",
            data={"username": test_user.username, "password": "bad-password"},
        )
        assert response.status_code == 200  # Stay on login page
        assert b"Invalid credentials" in response.data


def test_logout(auditor):
    """Test user logout"""
    response = auditor.get("/training/auth/logout")
    assert response.status_code == 302  # Redirect after logout


def test_login_page(anonymous):
    """Test login page renders"""
    response = anonymous.get("/training/auth/login")
    assert response.status_code == 200
    assert b"Login" in response.data