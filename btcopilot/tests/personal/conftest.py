import contextlib

import pytest
from mock import patch, AsyncMock

from btcopilot.personal import ResponseDirection
from btcopilot.personal.database import PDP, PDPDeltas


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "chat_flow: mock various parts of the intelligence flow",
    )


@pytest.fixture(autouse=True)
def chat_flow(request):

    chat_flow = request.node.get_closest_marker("chat_flow")

    with contextlib.ExitStack() as stack:
        if chat_flow is not None:

            response = chat_flow.kwargs.get("response", "some response")
            pdp = (chat_flow.kwargs.get("pdp", PDP()), PDPDeltas())
            response_direction = chat_flow.kwargs.get(
                "response_direction", ResponseDirection.Follow
            )

            stack.enter_context(
                patch(
                    "btcopilot.personal.pdp.update",
                    AsyncMock(return_value=pdp),
                )
            )
            stack.enter_context(
                patch(
                    "btcopilot.personal.chat.detect_response_direction",
                    AsyncMock(return_value=response_direction),
                )
            )
            stack.enter_context(
                patch(
                    "btcopilot.personal.chat._generate_response",
                    return_value=response,
                )
            )
            ret = {
                "response": response,
                "pdp": pdp,
                "response_direction": response_direction,
            }
        else:
            ret = None
        yield ret
