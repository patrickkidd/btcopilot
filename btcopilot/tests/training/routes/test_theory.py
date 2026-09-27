def test_auditor_sees_confidential_entries(auditor, theory):
    response = auditor.get("/training/theory/anxiety")
    assert response.status_code == 200
    assert "lighthouse" in response.text
    assert "ferry" in response.text
    assert "/training/theory/conflict#C1" in response.text


def test_subscriber_gets_public_edition(subscriber, theory):
    response = subscriber.get("/training/theory/anxiety")
    assert response.status_code == 200
    assert "anxiety is the response to a threat" in response.text
    assert "lighthouse" not in response.text
    assert "ferry" not in response.text
    assert "transcripts" not in response.text


def test_auditor_index_and_readme(auditor, theory):
    response = auditor.get("/training/theory/")
    assert response.status_code == 200
    assert "Total: 4 entries" in response.text
    assert auditor.get("/training/theory/README").status_code == 200


def test_subscriber_index_and_readme(subscriber, theory):
    response = subscriber.get("/training/theory/")
    assert response.status_code == 200
    assert "Total: 4 entries" not in response.text
    assert "(/training/theory/anxiety) (A)" in response.text
    assert subscriber.get("/training/theory/README").status_code == 404


def test_logged_out_redirects_to_login(flask_app, theory):
    response = flask_app.test_client().get("/training/theory/")
    assert response.status_code == 302
    assert "/login" in response.location
