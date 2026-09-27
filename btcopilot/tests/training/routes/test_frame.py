def test_auditor_sees_confidential_entries(auditor, frame):
    response = auditor.get("/training/frame/anxiety")
    assert response.status_code == 200
    assert "lighthouse" in response.text
    assert "ferry" in response.text
    assert "/training/frame/conflict#C1" in response.text


def test_subscriber_gets_public_edition(subscriber, frame):
    response = subscriber.get("/training/frame/anxiety")
    assert response.status_code == 200
    assert "anxiety is the response to a threat" in response.text
    assert "lighthouse" not in response.text
    assert "ferry" not in response.text
    assert "transcripts" not in response.text


def test_auditor_index_and_readme(auditor, frame):
    response = auditor.get("/training/frame/")
    assert response.status_code == 200
    assert "Total: 4 entries" in response.text
    assert auditor.get("/training/frame/README").status_code == 200


def test_subscriber_index_and_readme(subscriber, frame):
    response = subscriber.get("/training/frame/")
    assert response.status_code == 200
    assert "Total: 4 entries" not in response.text
    assert "(/training/frame/anxiety) (A)" in response.text
    assert subscriber.get("/training/frame/README").status_code == 404


def test_logged_out_redirects_to_login(flask_app, frame):
    response = flask_app.test_client().get("/training/frame/")
    assert response.status_code == 302
    assert "/login" in response.location
