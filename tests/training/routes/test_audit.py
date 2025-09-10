def test_audit_403(subscriber):
    response = subscriber.get("/training/audit/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers.get("Location", "")


def test_audit_index(auditor, discussion):
    response = auditor.get("/training/audit/")
    assert response.status_code == 200
    assert response.data is not None


def test_audit_index_no_threads(auditor):
    response = auditor.get("/training/audit/")
    assert response.status_code == 200