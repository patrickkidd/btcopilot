"""
MCP Server for managing the btcopilot Flask development server.

This server provides tools to start, stop, restart, kill, and get status
for a singleton Flask server instance on port 5555.

Usage:
    # Run standalone
    python mcp_server.py

    # Or via uv
    uv run python btcopilot/mcp-server/mcp_server.py

Configuration:
    Add to .mcp.json in project root to use with Claude Code.
"""

import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("btcopilot-flask-mcp")

mcp = FastMCP("btcopilot-flask")

DEFAULT_PORT = 5555
MAX_PORT = 5565


class FlaskServerManager:
    """
    Singleton manager for the Flask development server.

    Handles:
    - Starting/stopping the Flask server
    - Port management (finds available port in range 5555-5565)
    - Process lifecycle management
    - Auto-auth configuration
    """

    _instance: Optional["FlaskServerManager"] = None

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.port: Optional[int] = None
        self.start_time: Optional[float] = None
        self.project_root = Path(__file__).parent.parent.parent
        self._stdout_lines: List[str] = []
        self._stderr_lines: List[str] = []
        self._auto_auth_user: str = "patrick@alaskafamilysystems.com"

    @classmethod
    def get_instance(cls) -> "FlaskServerManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = FlaskServerManager()
        return cls._instance

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        if self.process is None:
            return False
        return self.process.poll() is None

    @property
    def pid(self) -> Optional[int]:
        """Get process ID if running."""
        if self.is_running:
            return self.process.pid
        return None

    @property
    def uptime(self) -> Optional[float]:
        """Get uptime in seconds."""
        if self.is_running and self.start_time:
            return time.time() - self.start_time
        return None

    def _find_available_port(self) -> Optional[int]:
        """Find an available port in range 5555-5565."""
        for port in range(DEFAULT_PORT, MAX_PORT + 1):
            if not self._is_port_in_use(port):
                return port
        return None

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())

    def _get_pids_on_port(self, port: int) -> List[int]:
        """Get list of PIDs using a port."""
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            return [int(pid) for pid in result.stdout.strip().split("\n") if pid]
        return []

    def _clear_bytecode_cache(self) -> None:
        """Clear Python bytecode cache to prevent stale imports."""
        btcopilot_pycache = (
            self.project_root / "btcopilot" / "btcopilot" / "__pycache__"
        )
        if btcopilot_pycache.exists():
            shutil.rmtree(btcopilot_pycache)
            logger.info(f"Cleared pycache: {btcopilot_pycache}")

        for pyc in (self.project_root / "btcopilot").rglob("*.pyc"):
            pyc.unlink()

        venv_path = self.project_root / ".venv"
        if venv_path.exists():
            for pyc in venv_path.rglob("*.pyc"):
                try:
                    pyc.unlink()
                except OSError:
                    pass

    def start(
        self,
        auto_auth_user: Optional[str] = None,
        reload: bool = True,
        clear_cache: bool = True,
    ) -> Tuple[bool, str]:
        """
        Start the Flask development server.

        Args:
            auto_auth_user: User email for auto-auth (default: patrick@alaskafamilysystems.com)
            reload: Enable live reloading (default: True)
            clear_cache: Clear bytecode cache before starting (default: True)

        Returns:
            Tuple of (success, message)
        """
        if self.is_running:
            return (
                False,
                f"Server already running on port {self.port} (PID: {self.pid})",
            )

        if clear_cache:
            self._clear_bytecode_cache()

        port = self._find_available_port()
        if port is None:
            return False, f"No available ports in range {DEFAULT_PORT}-{MAX_PORT}"

        auth_user = auto_auth_user or self._auto_auth_user

        env = os.environ.copy()
        env.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "FLASK_APP": "btcopilot.app:create_app",
                "FLASK_CONFIG": "development",
                "FLASK_DEBUG": "1",
                "FLASK_AUTO_AUTH_USER": auth_user,
            }
        )

        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "flask",
            "run",
            "-p",
            str(port),
        ]

        if not reload:
            cmd.append("--no-reload")

        try:
            logger.info(f"Starting Flask server: {' '.join(cmd)}")
            logger.info(f"Auto-auth user: {auth_user}")
            logger.info(f"Working directory: {self.project_root / 'btcopilot'}")

            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root / "btcopilot"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.port = port
            self.start_time = time.time()
            self._stdout_lines = []
            self._stderr_lines = []

            time.sleep(2)

            if not self.is_running:
                stderr = (
                    self.process.stderr.read().decode() if self.process.stderr else ""
                )
                return False, f"Server failed to start: {stderr}"

            logger.info(f"Flask server started on port {port} (PID: {self.pid})")
            return True, f"Server started on http://127.0.0.1:{port} (PID: {self.pid})"

        except OSError as e:
            logger.exception("Failed to start Flask server")
            return False, f"Failed to start: {str(e)}"

    def stop(self, timeout: int = 10) -> Tuple[bool, str]:
        """
        Stop the Flask server gracefully.

        Args:
            timeout: Timeout for graceful shutdown

        Returns:
            Tuple of (success, message)
        """
        if not self.is_running:
            return True, "Server not running"

        pid = self.pid
        port = self.port

        try:
            self.process.terminate()

            try:
                self.process.wait(timeout=timeout)
                logger.info(f"Flask server stopped gracefully (PID: {pid})")
                self._cleanup()
                return True, f"Server stopped (was on port {port}, PID: {pid})"
            except subprocess.TimeoutExpired:
                return False, f"Graceful shutdown timed out. Use kill() to force stop."

        except OSError as e:
            logger.exception("Failed to stop Flask server")
            return False, f"Failed to stop: {str(e)}"

    def kill(self) -> Tuple[bool, str]:
        """
        Force kill the Flask server.

        Returns:
            Tuple of (success, message)
        """
        if not self.is_running and self.port is None:
            return True, "Server not running"

        killed_pids = []
        port = self.port or DEFAULT_PORT

        if self.is_running and self.process:
            pid = self.pid
            try:
                self.process.kill()
                self.process.wait(timeout=5)
                killed_pids.append(pid)
            except (OSError, subprocess.TimeoutExpired):
                pass

        for p in range(DEFAULT_PORT, MAX_PORT + 1):
            pids = self._get_pids_on_port(p)
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                    killed_pids.append(pid)
                    logger.info(f"Killed process {pid} on port {p}")
                except OSError:
                    pass

        self._cleanup()

        if killed_pids:
            return True, f"Killed processes: {killed_pids}"
        return True, "No processes to kill"

    def restart(
        self,
        auto_auth_user: Optional[str] = None,
        reload: bool = True,
    ) -> Tuple[bool, str]:
        """
        Restart the Flask server.

        Args:
            auto_auth_user: User email for auto-auth
            reload: Enable live reloading

        Returns:
            Tuple of (success, message)
        """
        stop_success, stop_msg = self.stop()
        if not stop_success:
            kill_success, kill_msg = self.kill()
            if not kill_success:
                return False, f"Failed to stop server: {kill_msg}"

        time.sleep(1)

        return self.start(auto_auth_user=auto_auth_user, reload=reload)

    def status(self) -> Dict[str, Any]:
        """
        Get server status.

        Returns:
            Dict with status information
        """
        self._collect_output()

        running_ports = []
        for p in range(DEFAULT_PORT, MAX_PORT + 1):
            pids = self._get_pids_on_port(p)
            if pids:
                running_ports.append({"port": p, "pids": pids})

        return {
            "running": self.is_running,
            "pid": self.pid,
            "port": self.port,
            "uptime_seconds": self.uptime,
            "url": f"http://127.0.0.1:{self.port}" if self.is_running else None,
            "running_ports": running_ports,
            "recent_stdout": self._stdout_lines[-20:] if self._stdout_lines else [],
            "recent_stderr": self._stderr_lines[-20:] if self._stderr_lines else [],
        }

    def _collect_output(self) -> None:
        """Collect non-blocking stdout/stderr from the running process."""
        if not self.process or not self.is_running:
            return

        import select

        if self.process.stdout:
            try:
                while True:
                    if sys.platform != "win32":
                        ready, _, _ = select.select([self.process.stdout], [], [], 0)
                        if not ready:
                            break
                    line = self.process.stdout.readline()
                    if not line:
                        break
                    self._stdout_lines.append(
                        line.decode("utf-8", errors="replace").rstrip()
                    )
            except (OSError, ValueError):
                pass

        if self.process.stderr:
            try:
                while True:
                    if sys.platform != "win32":
                        ready, _, _ = select.select([self.process.stderr], [], [], 0)
                        if not ready:
                            break
                    line = self.process.stderr.readline()
                    if not line:
                        break
                    self._stderr_lines.append(
                        line.decode("utf-8", errors="replace").rstrip()
                    )
            except (OSError, ValueError):
                pass

    def _cleanup(self) -> None:
        """Clean up process state."""
        self.process = None
        self.port = None
        self.start_time = None


@mcp.tool()
def start_server(
    auto_auth_user: Optional[str] = None,
    reload: bool = True,
    clear_cache: bool = True,
) -> Dict[str, Any]:
    """Start Flask dev server. Returns {success, port, pid, url}. Auto-auth enabled by default."""
    manager = FlaskServerManager.get_instance()
    success, message = manager.start(
        auto_auth_user=auto_auth_user,
        reload=reload,
        clear_cache=clear_cache,
    )
    return {
        "success": success,
        "message": message,
        "port": manager.port,
        "pid": manager.pid,
        "url": f"http://127.0.0.1:{manager.port}" if success else None,
    }


@mcp.tool()
def stop_server(timeout: int = 10) -> Dict[str, Any]:
    """Stop Flask server gracefully. Use kill_server() if this times out."""
    manager = FlaskServerManager.get_instance()
    success, message = manager.stop(timeout=timeout)
    return {
        "success": success,
        "message": message,
    }


@mcp.tool()
def restart_server(
    auto_auth_user: Optional[str] = None,
    reload: bool = True,
) -> Dict[str, Any]:
    """Restart Flask server. Stops then starts with fresh cache clear."""
    manager = FlaskServerManager.get_instance()
    success, message = manager.restart(
        auto_auth_user=auto_auth_user,
        reload=reload,
    )
    return {
        "success": success,
        "message": message,
        "port": manager.port,
        "pid": manager.pid,
        "url": f"http://127.0.0.1:{manager.port}" if success else None,
    }


@mcp.tool()
def kill_server() -> Dict[str, Any]:
    """Force kill Flask server and any processes on ports 5555-5565."""
    manager = FlaskServerManager.get_instance()
    success, message = manager.kill()
    return {
        "success": success,
        "message": message,
    }


@mcp.tool()
def server_status() -> Dict[str, Any]:
    """Get Flask server status. Returns running state, port, pid, uptime, recent output."""
    manager = FlaskServerManager.get_instance()
    return manager.status()


if __name__ == "__main__":
    logger.info("Starting btcopilot Flask MCP Server")
    mcp.run(transport="stdio")
