import pickle

from btcopilot.tests.pro.copilot.conftest import llm_response


def test_chat(flask_app, test_session, llm_response):
    QUESTION = "What is the point?"
    RESPONSE = "There is no point"
    args = {"session": test_session.token, "question": QUESTION}
    with llm_response(RESPONSE):
        with flask_app.test_client() as client:
            response = client.post("/v1/copilot/chat", data=pickle.dumps(args))
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert data["response"] == RESPONSE
