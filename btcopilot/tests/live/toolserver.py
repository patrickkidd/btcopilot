"""The coach's tools as an MCP server on stdio, for a coach turn answered on the
Claude Code subscription (subscription.py). It serves the tool definitions the
app sends the API, name, description and input schema unchanged, read from the
JSON file given as its one argument. A call is answered with nothing: the turn
stops at its first message, and the suite's own replay runs the tools.

python -m btcopilot.tests.live.toolserver <tools file>
"""

import json
import sys

VERSION = "2025-06-18"


def listed(tools: list[dict]) -> list[dict]:
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["input_schema"],
        }
        for t in tools
    ]


def result(method: str, params: dict, tools: list[dict]) -> dict:
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "coach", "version": "1"},
        }
    if method == "tools/list":
        return {"tools": listed(tools)}
    if method == "tools/call":
        return {"content": [{"type": "text", "text": ""}]}
    return {}


def serve(tools: list[dict]) -> None:
    for line in sys.stdin:
        message = json.loads(line)
        if "id" not in message:
            continue
        reply = {
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": result(message["method"], message.get("params", {}), tools),
        }
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    serve(json.loads(open(sys.argv[1]).read()))
