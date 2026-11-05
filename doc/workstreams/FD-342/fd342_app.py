"""Launch ONE visible app (personal|pro) against the running FD-342 sandbox server."""
import sys
from pathlib import Path

WT = Path("/Users/patrick/theapp/familydiagram/.claude/worktrees/FD-342")
sys.path.insert(0, str(WT / "mcpserver"))
from mcp_server import TestInstance, LoginState  # noqa: E402

kind, server = sys.argv[1], sys.argv[2]
s = TestInstance.create()
ok, msg = s.launch(
    headless=False,
    personal=(kind == "personal"),
    enable_bridge=False,
    login_state=LoginState.LoggedIn,
    ephemeral_server=False,
    server_url=server,
    username="patrick@alaskafamilysystems.com",
    timeout=90,
)
print(f">>> {kind.upper()} ok={ok} msg={msg} server={server}", flush=True)
if not ok:
    for ln in (getattr(s, "_stderr_lines", []) or [])[-25:]:
        print("   ", ln, flush=True)
    sys.exit(1)
try:
    s.process.wait()
finally:
    s.close()
