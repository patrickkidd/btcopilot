import pytest


def test_subscriber_redirect_to_subscriber_landing(subscriber):
    """Subscribers should be redirected to subscriber landing from training root"""
    response = subscriber.get("/training/", follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith("/training/subscriber")


def test_subscriber_landing_allows_subscribers(subscriber):
    """Subscriber landing page should render for subscribers"""
    response = subscriber.get("/training/subscriber", follow_redirects=False)
    assert response.status_code == 200


def test_auditor_redirect_to_audit(auditor):
    """Auditors should be redirected to audit index from training root"""
    response = auditor.get("/training/", follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith("/training/audit/")


def test_auditor_redirect_from_subscriber_landing(auditor):
    """Auditors accessing subscriber landing should be redirected to training root"""
    response = auditor.get("/training/subscriber", follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith("/training/")


def test_admin_redirect_to_admin(admin):
    """Admins should be redirected to admin index from training root"""
    response = admin.get("/training/", follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith("/training/admin/")


def test_admin_redirect_from_subscriber_landing(admin):
    """Admins accessing subscriber landing should be redirected to training root"""
    response = admin.get("/training/subscriber", follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith("/training/")


def test_subscriber_no_infinite_redirect(subscriber):
    """
    Regression test: Ensure subscribers don't get caught in infinite redirect loop.

    Before the fix, subscribers would be redirected:
    /training/ -> /training/subscriber -> /training/ -> /training/subscriber -> ...

    After the fix, they should be able to access subscriber landing.
    """
    response = subscriber.get("/training/subscriber", follow_redirects=True)
    assert response.status_code == 200
    assert response.request.path == "/training/subscriber"


def test_subscriber_sees_403_for_admin_page(subscriber):
    """Subscribers accessing admin pages should see 403 page, not redirect"""
    response = subscriber.get("/training/admin/", follow_redirects=False)
    assert response.status_code == 403
    assert b"403" in response.data
    assert b"Access Denied" in response.data


def test_subscriber_sees_403_for_audit_page(subscriber):
    """Subscribers accessing audit pages should see 403 page, not redirect"""
    response = subscriber.get("/training/audit/", follow_redirects=False)
    assert response.status_code == 403
    assert b"403" in response.data
    assert b"Access Denied" in response.data
