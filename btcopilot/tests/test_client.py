def test_ask(client, llm_response):
    RESPONSE = "I'm sorry, I don't know the answer to that question."

    with llm_response(RESPONSE, sources=[]):
        response = client.post(
            "/v1/chat", json={"question": "What is differentiation of self"}
        )
    assert response.status_code == 200
    assert response.json["response"] == RESPONSE
    assert response.json["sources"] == []
