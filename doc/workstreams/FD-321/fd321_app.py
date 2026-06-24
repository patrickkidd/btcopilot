"""Launch ONE visible app (personal|pro) against an EXISTING independent sandbox server.
Does NOT start or stop that server, so app quit/restart preserves server state.
Used by fd321_sandbox.sh for the FD-321 human walkthrough."""
import sys
from pathlib import Path

WT = Path("/Users/patrick/worktrees/FD-321/familydiagram")
sys.path.insert(0, str(WT / "mcpserver"))
from mcp_server import TestInstance, LoginState  # noqa

kind = sys.argv[1]            # "personal" or "pro"
server = sys.argv[2]          # http://127.0.0.1:62090
personal = (kind == "personal")
s = TestInstance.create()
ok, msg = s.launch(
    headless=False, personal=personal, enable_bridge=False,
    login_state=LoginState.LoggedIn, ephemeral_server=False, server_url=server,
    username="patrick+fd321walk@example.com", timeout=90,
)
print(f">>> {kind.upper()} ok={ok} msg={msg} server={server}", flush=True)
if not ok:
    for ln in (getattr(s, "_stderr_lines", []) or [])[-25:]:
        print("   ", ln, flush=True)
    sys.exit(1)
print(f">>> {kind} window open.", flush=True)
try:
    s.process.wait()
finally:
    try:
        s.close()
    except Exception:
        pass
