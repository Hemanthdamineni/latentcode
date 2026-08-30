"""Spawn and manage the project's dev/start server."""
from __future__ import annotations

import os
import shlex
import signal
import subprocess
import time
from pathlib import Path


class ServerProcess:
    """Context manager that spawns a dev server and tears it down on exit.

    Safety: defaults to loopback-only binding. The `allow_remote` flag
    must be explicitly set to allow the server to bind to non-loopback
    interfaces. (audit Stage 3 finding)
    """

    LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")  # 0.0.0.0 is rejected too

    def __init__(self, repo: Path, dev_cmd: str, package_manager: str, timeout: float = 60.0, allow_remote: bool = False):
        self.repo = Path(repo)
        self.dev_cmd = dev_cmd
        self.package_manager = package_manager
        self.timeout = timeout
        self.allow_remote = allow_remote
        self.process: subprocess.Popen | None = None
        self.start_time: float = 0.0
        self.startup_seconds: float = 0.0
        self.base_url: str = "http://localhost:3000"
        self._logs: list[str] = []
        self.safety_error: str | None = None

    def __enter__(self):
        self._spawn()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._terminate()

    def _spawn(self):
        # Pre-flight: refuse to spawn if the cmd would bind to a non-loopback
        # address and allow_remote is not set.
        if not self.allow_remote and self._mentions_non_loopback():
            self.safety_error = (
                "refusing to spawn: dev_cmd appears to bind to a non-loopback host. "
                "Pass --allow-remote if this is intentional."
            )
            self.startup_seconds = -1
            return

        # Translate npm/pnpm/yarn if needed
        cmd = self.dev_cmd
        if self.package_manager == "pnpm" and cmd.startswith("npm "):
            cmd = cmd.replace("npm ", "pnpm ", 1)
        elif self.package_manager == "yarn" and cmd.startswith("npm "):
            cmd = cmd.replace("npm ", "yarn ", 1)

        env = os.environ.copy()
        env["BROWSER"] = "none"
        env["CI"] = "true"
        # Force loopback binding
        env["HOST"] = "127.0.0.1"
        env["PORT"] = env.get("PORT", "3000")

        args = shlex.split(cmd)
        if not args:
            return

        self.start_time = time.time()
        try:
            self.process = subprocess.Popen(
                args,
                cwd=self.repo,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                start_new_session=True,
            )
        except FileNotFoundError:
            self.startup_seconds = -1
            return

        # Wait for "ready" signal
        ready_markers = ["ready", "compiled", "listening", "started server", "local:"]
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                self.startup_seconds = -1
                return
            line = self._readline_nowait()
            if line:
                self._logs.append(line)
                if any(m in line.lower() for m in ready_markers):
                    self.startup_seconds = time.time() - self.start_time
                    return
            time.sleep(0.1)

        self.startup_seconds = time.time() - self.start_time

    def _mentions_non_loopback(self) -> bool:
        """Heuristic: detect if the dev_cmd explicitly binds to a public interface."""
        cmd = self.dev_cmd.lower()
        non_loopback = ("0.0.0.0", "--host", "-h ", "host 0.0.0.0", "public", "external")
        return any(tok in cmd for tok in non_loopback)

    def _readline_nowait(self) -> str | None:
        if not self.process or not self.process.stdout:
            return None
        try:
            import select
            if not select.select([self.process.stdout], [], [], 0.0)[0]:
                return None
            return self.process.stdout.readline().rstrip()
        except Exception:
            return None

    def logs_so_far(self) -> str:
        if self.process and self.process.stdout:
            try:
                import select
                while select.select([self.process.stdout], [], [], 0.05)[0]:
                    line = self.process.stdout.readline()
                    if not line:
                        break
                    self._logs.append(line.rstrip())
            except Exception:
                pass
        return "\n".join(self._logs)

    def _terminate(self):
        if not self.process:
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait(timeout=2)
        except (ProcessLookupError, OSError):
            pass