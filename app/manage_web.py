import base64
import html
import json
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs


COMPOSE_FILE_NAMES = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)


@dataclass
class AppConfig:
    ttyd_credentials: str
    compose_root: Path
    state_file: Path
    host: str
    port: int
    prune_interval_hours: int


@dataclass
class AppState:
    auto_update_enabled: bool = False
    auto_prune_enabled: bool = False
    update_interval_hours: int = 24
    last_run_at: str = ""
    last_update_attempt_at: str = ""
    last_prune_attempt_at: str = ""
    last_update_status: str = "Idle"
    last_prune_status: str = "Idle"


def parse_ttyd_credentials(credentials: str) -> tuple[str, str]:
    if ":" not in credentials:
        raise ValueError("TTYD credentials must be in username:password format")
    username, password = credentials.split(":", 1)
    if not username or not password:
        raise ValueError("TTYD credentials must include both username and password")
    return username, password


def find_compose_file(root: Path) -> Optional[Path]:
    try:
        if not root.is_dir():
            return None
    except OSError:
        return None

    for file_name in COMPOSE_FILE_NAMES:
        candidate = root / file_name
        if candidate.is_file():
            return candidate
    return None


def backoff_delay_seconds(attempt: int) -> int:
    if attempt < 1:
        raise ValueError("Attempt number must be at least 1")
    return 2 ** (attempt - 1)


class StateStore:
    def __init__(self, config: AppConfig):
        self._config = config
        self._lock = threading.Lock()

    def load(self) -> AppState:
        with self._lock:
            return self._read_unlocked()

    def save(self, state: AppState) -> None:
        with self._lock:
            self._write_unlocked(state)

    def update(self, mutator) -> AppState:
        with self._lock:
            state = self._read_unlocked()
            mutator(state)
            self._write_unlocked(state)
            return state

    def _read_unlocked(self) -> AppState:
        if not self._config.state_file.exists():
            return AppState(update_interval_hours=self._config.prune_interval_hours)

        try:
            with self._config.state_file.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return AppState(update_interval_hours=self._config.prune_interval_hours)

        allowed_keys = {field for field in AppState.__dataclass_fields__}
        sanitized = {key: value for key, value in payload.items() if key in allowed_keys}
        return AppState(**sanitized)

    def _write_unlocked(self, state: AppState) -> None:
        self._config.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._config.state_file.with_suffix(self._config.state_file.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(state), handle, ensure_ascii=True, indent=2)
        temp_path.replace(self._config.state_file)


class JobRunner:
    def __init__(self, config: AppConfig, state_store: StateStore):
        self._config = config
        self._state_store = state_store
        self._stop_event = threading.Event()
        self._threads = []

    def start(self) -> None:
        self._threads = [threading.Thread(target=self._schedule_loop, name="job-schedule-loop", daemon=True)]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=1)

    def _schedule_loop(self) -> None:
        while not self._stop_event.wait(1):
            self.run_due_cycle()

    def run_due_cycle(self) -> None:
        state = self._state_store.load()
        if not state.auto_update_enabled and not state.auto_prune_enabled:
            return
        if not self._is_due(state.last_run_at, state.update_interval_hours):
            return

        now = utc_now()
        self._state_store.update(lambda current: setattr(current, "last_run_at", now))

        update_succeeded = True
        if state.auto_update_enabled:
            update_succeeded = self._run_update_job()

        if state.auto_prune_enabled and (not state.auto_update_enabled or update_succeeded):
            self._run_prune_job()
        elif state.auto_prune_enabled and state.auto_update_enabled and not update_succeeded:
            self._state_store.update(
                lambda current: setattr(
                    current,
                    "last_prune_status",
                    f"Skipped at {now}: waiting for successful docker compose update",
                )
            )

    def _is_due(self, timestamp: str, interval_hours: int) -> bool:
        if not timestamp:
            return True
        try:
            last_attempt = datetime.fromisoformat(timestamp)
        except ValueError:
            return True
        elapsed = datetime.now(timezone.utc) - last_attempt
        return elapsed.total_seconds() >= max(interval_hours, 1) * 3600

    def _run_update_job(self) -> bool:
        now = utc_now()
        self._state_store.update(lambda state: setattr(state, "last_update_attempt_at", now))

        compose_file = find_compose_file(self._config.compose_root)
        if compose_file is None:
            self._state_store.update(
                lambda state: setattr(
                    state,
                    "last_update_status",
                    f"Skipped at {now}: compose file not found in {self._config.compose_root}",
                )
            )
            return False

        pull_result = self._retry_pull(compose_file)
        if not pull_result["ok"]:
            self._state_store.update(
                lambda state: setattr(
                    state,
                    "last_update_status",
                    f"Failed at {now}: {pull_result['message']}",
                )
            )
            return False

        up_result = self._run_command(
            ["docker", "compose", "-f", str(compose_file), "up", "-d"],
            cwd=self._config.compose_root,
        )
        status = (
            f"Updated at {now}: {pull_result['message']} | {up_result['message']}"
            if up_result["ok"]
            else f"Failed at {now}: {up_result['message']}"
        )
        self._state_store.update(lambda state: setattr(state, "last_update_status", status))
        return up_result["ok"]

    def _retry_pull(self, compose_file: Path) -> dict:
        for attempt in range(1, 6):
            result = self._run_command(
                ["docker", "compose", "-f", str(compose_file), "pull"],
                cwd=self._config.compose_root,
            )
            if result["ok"]:
                result["message"] = f"pull succeeded on attempt {attempt}"
                return result
            if attempt < 5:
                time.sleep(backoff_delay_seconds(attempt))
        return {
            "ok": False,
            "message": f"pull failed after 5 attempts: {result['message']}",
        }

    def _run_prune_job(self) -> bool:
        now = utc_now()
        self._state_store.update(lambda state: setattr(state, "last_prune_attempt_at", now))
        result = self._run_command(["docker", "image", "prune", "-f"], cwd=self._config.compose_root)
        status = (
            f"Pruned at {now}: {result['message']}"
            if result["ok"]
            else f"Failed at {now}: {result['message']}"
        )
        self._state_store.update(lambda state: setattr(state, "last_prune_status", status))
        return result["ok"]

    def _run_command(self, command: list[str], cwd: Path) -> dict:
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return {"ok": False, "message": str(exc)}

        output = (completed.stdout or completed.stderr or "").strip()
        message = output.splitlines()[-1] if output else "command finished"
        return {"ok": completed.returncode == 0, "message": message}


class ManagementApp:
    def __init__(self, config: AppConfig):
        self.config = config
        self.state_store = StateStore(config)
        self.job_runner = JobRunner(config, self.state_store)
        self.username, self.password = parse_ttyd_credentials(config.ttyd_credentials)

    def make_handler(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if not app.is_authorized(self.headers.get("Authorization")):
                    self._require_auth()
                    return
                if self.path != "/":
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._send_html(app.render_page())

            def do_POST(self):
                if not app.is_authorized(self.headers.get("Authorization")):
                    self._require_auth()
                    return
                if self.path != "/":
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return

                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                form = parse_qs(body)
                app.update_settings(form)

                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", "/")
                self.end_headers()

            def log_message(self, format, *args):
                return

            def _require_auth(self):
                self.send_response(HTTPStatus.UNAUTHORIZED)
                self.send_header("WWW-Authenticate", 'Basic realm="git-docker-tool"')
                self.end_headers()

            def _send_html(self, content: str):
                encoded = content.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler

    def is_authorized(self, authorization_header: Optional[str]) -> bool:
        if not authorization_header or not authorization_header.startswith("Basic "):
            return False
        encoded = authorization_header.split(" ", 1)[1]
        try:
            decoded = base64.b64decode(encoded).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        return decoded == f"{self.username}:{self.password}"

    def update_settings(self, form: dict[str, list[str]]) -> None:
        requested_update_enabled = "auto_update_enabled" in form
        requested_prune_enabled = "auto_prune_enabled" in form
        interval_raw = form.get("update_interval_hours", ["24"])[0]

        try:
            update_interval_hours = max(int(interval_raw), 1)
        except ValueError:
            update_interval_hours = self.config.prune_interval_hours

        def mutate(state: AppState):
            was_update_enabled = state.auto_update_enabled
            was_prune_enabled = state.auto_prune_enabled
            state.auto_update_enabled = requested_update_enabled
            state.auto_prune_enabled = requested_prune_enabled
            state.update_interval_hours = update_interval_hours
            if (requested_update_enabled and not was_update_enabled) or (
                requested_prune_enabled and not was_prune_enabled
            ):
                state.last_run_at = ""
            if requested_update_enabled and not was_update_enabled:
                state.last_update_attempt_at = ""
                state.last_update_status = "Scheduled: auto update enabled"
            if requested_prune_enabled and not was_prune_enabled:
                state.last_prune_attempt_at = ""
                state.last_prune_status = "Scheduled: auto prune enabled"
            if not requested_update_enabled:
                state.last_update_status = "Disabled"
            if not requested_prune_enabled:
                state.last_prune_status = "Disabled"

        self.state_store.update(mutate)

    def render_page(self) -> str:
        state = self.state_store.load()
        auto_update_checked = "checked" if state.auto_update_enabled else ""
        auto_prune_checked = "checked" if state.auto_prune_enabled else ""

        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Git Docker Tool</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f0e8;
      --paper: #fffdf8;
      --ink: #1d1a16;
      --accent: #8a3b12;
      --line: #d9ccb9;
      --muted: #6f6559;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Noto Serif SC", "Source Han Serif SC", serif;
      background:
        radial-gradient(circle at top left, rgba(138,59,18,0.15), transparent 28%),
        linear-gradient(180deg, #efe4d3, var(--bg));
      color: var(--ink);
      min-height: 100vh;
      padding: 24px;
    }}
    .page {{
      max-width: 820px;
      margin: 0 auto;
      background: var(--paper);
      border: 1px solid var(--line);
      box-shadow: 0 12px 30px rgba(72, 53, 33, 0.12);
    }}
    .masthead {{
      border-bottom: 3px double var(--line);
      padding: 24px;
      text-align: center;
    }}
    .masthead h1 {{
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.4rem);
      letter-spacing: 0.08em;
    }}
    .masthead p {{
      margin: 8px 0 0;
      color: var(--muted);
    }}
    form {{
      padding: 24px;
      display: grid;
      gap: 20px;
    }}
    .card {{
      border: 1px solid var(--line);
      padding: 18px;
      background: #fffaf1;
    }}
    .row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }}
    label.switch {{
      display: inline-flex;
      align-items: center;
      gap: 12px;
      font-size: 1.05rem;
      font-weight: 700;
    }}
    input[type="number"] {{
      width: 120px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      background: #fff;
      font: inherit;
    }}
    button {{
      border: 0;
      padding: 12px 18px;
      background: var(--accent);
      color: white;
      font: inherit;
      cursor: pointer;
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.6;
    }}
    code {{
      font-family: "Cascadia Code", monospace;
      font-size: 0.95em;
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="masthead">
      <h1>Docker 管理页</h1>
      <p>与 ttyd 共用同一套账号密码</p>
    </header>
    <form method="post" action="/">
      <section class="card">
        <div class="row">
          <label class="switch">
            <input type="checkbox" name="auto_update_enabled" {auto_update_checked}>
            自动更新 docker compose 镜像
          </label>
          <label>
            每隔
            <input type="number" min="1" name="update_interval_hours" value="{state.update_interval_hours}">
            小时
          </label>
        </div>
        <p class="meta">目标目录：<code>{html.escape(str(self.config.compose_root))}</code></p>
        <p class="meta">最近状态：{html.escape(state.last_update_status)}</p>
      </section>
      <section class="card">
        <div class="row">
          <label class="switch">
            <input type="checkbox" name="auto_prune_enabled" {auto_prune_checked}>
            自动清理 docker 无效镜像
          </label>
          <span class="meta">与更新任务共用同一调度周期</span>
        </div>
        <p class="meta">执行顺序：先更新 compose，成功后再执行 <code>docker image prune -f</code></p>
        <p class="meta">最近状态：{html.escape(state.last_prune_status)}</p>
      </section>
      <section class="row">
        <a href="/" class="meta">刷新状态</a>
        <button type="submit">保存并立即生效</button>
      </section>
    </form>
  </main>
</body>
</html>
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_config_from_env() -> AppConfig:
    return AppConfig(
        ttyd_credentials=os.environ.get("TTYD_CREDENTIALS", "admin:adminadmin"),
        compose_root=Path(os.environ.get("COMPOSE_ROOT", "/workspace/configs/docker")),
        state_file=Path(os.environ.get("STATE_FILE", "/workspace/.git-docker-tool-state.json")),
        host=os.environ.get("MANAGEMENT_HOST", "0.0.0.0"),
        port=int(os.environ.get("MANAGEMENT_PORT", "7680")),
        prune_interval_hours=max(
            int(os.environ.get("TASK_INTERVAL_HOURS", os.environ.get("PRUNE_INTERVAL_HOURS", "24"))),
            1,
        ),
    )


def run_server() -> None:
    config = build_config_from_env()
    app = ManagementApp(config)
    app.job_runner.start()
    server = ThreadingHTTPServer((config.host, config.port), app.make_handler())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.job_runner.stop()
        server.server_close()


if __name__ == "__main__":
    run_server()
