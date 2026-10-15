"""One coach call answered on the Claude Code subscription instead of the API:
a request the suite dumped (LIVE_REPLAY=dump) goes to `claude -p` with the
coach's system prompt as the whole system prompt, the coach's tools served by
toolserver.py under their own names and schemas, and the chat as a resumed
session plus stdin. The model's first message is the answer, in the
shape answer.py saves.

What Claude Code still adds, seen by capturing its request (README.md): a
billing line and one sentence naming the Agent SDK ahead of the system prompt;
reminders of the working folder, the model, the account's email and today's
date at the head of the first user message; the `mcp__coach__` prefix on every
tool name; after the first tool call, "No response requested." ahead of the
coach's last message.
"""

import datetime
import json
import os
import re
import subprocess
import uuid
from pathlib import Path

from btcopilot.tests.live.replay import REPO

SERVER = "coach"
PREFIX = f"mcp__{SERVER}__"
SESSIONS = Path.home() / ".claude" / "projects"
TIMEOUT = 600


def system_text(system: str | list[str]) -> str:
    return system if isinstance(system, str) else "\n\n".join(p for p in system if p)


def sendable(content, prefix: str):
    """The app's cache marks go: Claude Code sets its own, and the API
    refuses more than four in all. They change the cost, not the answer."""
    if isinstance(content, str):
        return content
    blocks = []
    for block in content:
        block = {k: v for k, v in block.items() if k != "cache_control"}
        if block["type"] == "tool_use":
            block = dict(block, name=prefix + block["name"])
        elif block["type"] in ("thinking", "redacted_thinking"):
            continue
        blocks.append(block)
    return blocks


def transcript(messages: list[dict], session: str, cwd: Path) -> list[dict]:
    """The chat before the last tool call as a Claude Code session, so it is
    sent as the chat's own turns, tool calls and results included. The last
    call and its results go on stdin: a resumed session that ends on the
    user's side gets Claude Code's own "No response requested." reply, and one
    that ends on a call gets an "interrupted" result in place of the real one."""
    lines, parent = [], None
    now = (
        datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    )
    for message in messages:
        line = {
            "parentUuid": parent,
            "isSidechain": False,
            "type": message["role"],
            "message": {
                "role": message["role"],
                "content": sendable(message["content"], PREFIX),
            },
            "uuid": str(uuid.uuid4()),
            "timestamp": now,
            "userType": "external",
            "entrypoint": "sdk-cli",
            "cwd": str(cwd),
            "sessionId": session,
            "version": "",
        }
        if message["role"] == "assistant":
            line["message"].update(
                id=f"msg_{uuid.uuid4().hex}",
                type="message",
                model="",
                stop_reason="tool_use",
                stop_sequence=None,
                usage={"input_tokens": 0, "output_tokens": 0},
            )
        lines.append(line)
        parent = line["uuid"]
    return lines


def command(request: dict, work: Path, session: str, resume: bool) -> list[str]:
    return [
        "claude",
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--system-prompt-file",
        str(work / "system.txt"),
        "--model",
        request["model"],
        "--effort",
        request["effort"],
        "--tools",
        "",
        "--max-turns",
        "1",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--allowedTools",
        f"{PREFIX}*",
        *(["--resume", session] if resume else ["--session-id", session]),
        "--mcp-config",
        str(work / "mcp.json"),
    ]


def environment(request: dict, base_url: str | None) -> dict:
    """A clean environment: nothing from a Claude Code session this runs
    inside, the request's own output limit, and a capture server when asked."""
    env = {
        k: os.environ[k] for k in ("HOME", "PATH", "USER", "LANG") if k in os.environ
    }
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(request["max_tokens"])
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    return env


def first_message(lines: list[str]) -> dict:
    """The model's first message: Claude Code streams it a block at a time
    under one id, then runs any tool it called and stops at the turn cap."""
    events = [json.loads(line) for line in lines if line.strip()]
    failed = [
        e
        for e in events
        if e["type"] == "result"
        and e.get("is_error")
        and e.get("subtype") != "error_max_turns"
    ]
    if failed:
        raise RuntimeError(
            f"claude -p failed: {failed[0].get('result') or failed[0].get('subtype')}"
        )
    messages = [
        e["message"]
        for e in events
        if e["type"] == "assistant" and e["message"]["model"] != "<synthetic>"
    ]
    if not messages:
        raise RuntimeError(f"claude -p gave no answer: {[e['type'] for e in events]}")
    first = messages[0]["id"]
    content = []
    for message in messages:
        if message["id"] == first:
            content += [
                b for b in message["content"] if b["type"] in ("text", "tool_use")
            ]
    for block in content:
        if block["type"] == "tool_use":
            block["name"] = block["name"].removeprefix(PREFIX)
    return {"model": messages[0]["model"], "content": content}


def answer(request: dict, work: Path, base_url: str | None = None) -> dict:
    """The subscription's answer to one dumped request. `work` holds the
    private prompt while it runs and is emptied after."""
    work = work.resolve()
    cwd = work / "cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    (work / "system.txt").write_text(system_text(request["system"]))
    (work / "tools.json").write_text(json.dumps(request["tools"]))
    (work / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    SERVER: {
                        "type": "stdio",
                        "command": str(REPO / ".venv" / "bin" / "python"),
                        "args": [
                            "-m",
                            "btcopilot.tests.live.toolserver",
                            str(work / "tools.json"),
                        ],
                        "env": {"PYTHONPATH": str(REPO)},
                    }
                }
            }
        )
    )
    session = str(uuid.uuid4())
    history, tail = request["messages"][:-2], request["messages"][-2:]
    stored = SESSIONS / re.sub(r"[^A-Za-z0-9]", "-", str(cwd)) / f"{session}.jsonl"
    if history:
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_text(
            "".join(
                json.dumps(line) + "\n" for line in transcript(history, session, cwd)
            )
        )
    stdin = "".join(
        json.dumps(
            {
                "type": m["role"],
                "message": {
                    "role": m["role"],
                    "content": sendable(m["content"], PREFIX),
                },
            }
        )
        + "\n"
        for m in tail
    )
    try:
        ran = subprocess.run(
            command(request, work, session, bool(history)),
            input=stdin,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=environment(request, base_url),
            timeout=TIMEOUT,
        )
        if ran.returncode and not ran.stdout.strip():
            raise RuntimeError(f"claude -p failed: {ran.stderr.strip()}")
        return first_message(ran.stdout.splitlines())
    finally:
        stored.unlink(missing_ok=True)
        if stored.parent.exists() and not any(stored.parent.iterdir()):
            stored.parent.rmdir()
        for name in ("system.txt", "tools.json", "mcp.json"):
            (work / name).unlink(missing_ok=True)
