#!/opt/hermes/.venv/bin/python
"""Configure and supervise the Buzz ACP bridge next to Hermes."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import html
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlparse

HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))
# Deliberately NOT Hermes' own ${HERMES_HOME}/.env: the dashboard in the `web`
# container rewrites that file whenever a provider or integration credential is
# saved, and a read-modify-write from two containers can drop the other's keys.
ENV_FILE = HERMES_HOME / "buzz-acp.env"
SETUP_TOKEN = os.environ.get("BUZZ_SETUP_TOKEN", "")
CSRF_TOKEN = os.urandom(32).hex()
CONFIG_CHANGED = threading.Event()
SHUTDOWN = threading.Event()
CHILD_LOCK = threading.Lock()
CHILD: subprocess.Popen[bytes] | None = None

BRIDGE_LOG = HERMES_HOME / "bridge.log"
BRIDGE_LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_LOCK = threading.Lock()

MANAGED_KEYS = (
    "BUZZ_RELAY_URL",
    "BUZZ_PRIVATE_KEY",
    "BUZZ_AUTH_TAG",
    "BUZZ_API_TOKEN",
    "BUZZ_ACP_AGENT_OWNER",
)
REQUIRED_KEYS = (
    "BUZZ_RELAY_URL",
    "BUZZ_PRIVATE_KEY",
    "BUZZ_ACP_AGENT_OWNER",
)
ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")


def log(line: str) -> None:
    """Write one line to stdout and to the persistent bridge log.

    `docker logs` needs host root on umbrelOS, so without a file the owner can
    read under app-data, a headless agent that will not connect gives up no
    evidence at all.
    """
    print(line, flush=True)
    with LOG_LOCK:
        try:
            HERMES_HOME.mkdir(parents=True, exist_ok=True)
            if BRIDGE_LOG.exists() and BRIDGE_LOG.stat().st_size > BRIDGE_LOG_MAX_BYTES:
                BRIDGE_LOG.replace(BRIDGE_LOG.with_suffix(".log.1"))
            with BRIDGE_LOG.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as error:
            print(f"bridge log write failed: {error}", flush=True)


def mirror_child_output(stream) -> None:
    """Pump the bridge's merged stdout/stderr into `log`, line by line."""
    with stream:
        for raw in iter(stream.readline, b""):
            log(raw.decode("utf-8", "replace").rstrip("\n"))


def parse_value(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
            return value if isinstance(value, str) else raw
        except json.JSONDecodeError:
            return raw
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1]
    return raw


def read_managed_env() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values
    for line in lines:
        match = ENV_LINE.match(line.strip())
        if match and match.group(1) in MANAGED_KEYS:
            values[match.group(1)] = parse_value(match.group(2))
    return values


def write_managed_env(values: dict[str, str]) -> None:
    HERMES_HOME.mkdir(parents=True, exist_ok=True)
    try:
        original = ENV_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        original = []

    pending = dict(values)
    output: list[str] = []
    for line in original:
        match = ENV_LINE.match(line.strip())
        key = match.group(1) if match else None
        if key not in MANAGED_KEYS:
            output.append(line)
            continue
        value = pending.pop(key, "")
        if value:
            output.append(f"{key}={json.dumps(value)}")

    for key in MANAGED_KEYS:
        value = pending.get(key, "")
        if value:
            output.append(f"{key}={json.dumps(value)}")

    temporary = ENV_FILE.with_suffix(".env.tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(ENV_FILE)


def validate(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    relay = values.get("BUZZ_RELAY_URL", "")
    parsed = urlparse(relay)
    if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
        errors.append("Relay URL must be a ws:// or wss:// URL.")
    private_key = values.get("BUZZ_PRIVATE_KEY", "")
    if not (private_key.startswith("nsec1") or HEX_64.fullmatch(private_key)):
        errors.append("Private key must be an nsec or 64-character hex key.")
    if not HEX_64.fullmatch(values.get("BUZZ_ACP_AGENT_OWNER", "")):
        errors.append("Owner pubkey must be 64-character hex.")
    return errors


def bridge_state() -> tuple[bool, bool]:
    configured = all(read_managed_env().get(key) for key in REQUIRED_KEYS)
    with CHILD_LOCK:
        running = CHILD is not None and CHILD.poll() is None
    return configured, running


def render_page(message: str = "", errors: list[str] | None = None) -> bytes:
    configured, running = bridge_state()
    values = read_managed_env()
    status = "Connected" if running else ("Starting" if configured else "Setup required")
    status_class = "ok" if running else "waiting"
    notice = f'<p class="notice">{html.escape(message)}</p>' if message else ""
    error_html = "".join(f'<li>{html.escape(error)}</li>' for error in (errors or []))
    error_block = f'<ul class="errors">{error_html}</ul>' if error_html else ""
    relay = html.escape(values.get("BUZZ_RELAY_URL", ""), quote=True)
    owner = html.escape(values.get("BUZZ_ACP_AGENT_OWNER", ""), quote=True)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Buzz Agent Setup</title><style>
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
body {{ margin: 0; background: #0d0918; color: #f6f2ff; }}
main {{ max-width: 760px; margin: 0 auto; padding: 48px 24px 80px; }}
h1 {{ font-size: 2.2rem; margin: 0 0 8px; }} h2 {{ margin-top: 36px; }}
p {{ color: #c9c0da; line-height: 1.55; }}
.card {{ background: #171025; border: 1px solid #302243; border-radius: 18px; padding: 24px; margin-top: 24px; }}
.status {{ display: inline-flex; gap: 8px; align-items: center; padding: 7px 12px; border-radius: 99px; background: #241834; }}
.dot {{ width: 9px; height: 9px; border-radius: 50%; background: #f4a261; }} .ok .dot {{ background: #63d6a1; }}
label {{ display: block; margin: 18px 0 7px; font-weight: 650; }}
input {{ box-sizing: border-box; width: 100%; border: 1px solid #46325e; border-radius: 10px; background: #0f0a18; color: #fff; padding: 12px; }}
small {{ color: #9e91b3; }} button, .button {{ display: inline-block; margin-top: 22px; border: 0; border-radius: 10px; background: #8b5cf6; color: white; padding: 12px 18px; font-weight: 700; text-decoration: none; cursor: pointer; }}
.button.secondary {{ background: #302243; margin-left: 8px; }} .errors {{ color: #ff9f9f; }} .notice {{ color: #8ee8ba; }} code {{ color: #d8c7ff; }}
</style></head><body><main>
<h1>Buzz Agent</h1><p>Run a persistent Hermes Agent in your Buzz community using the stock <code>buzz-acp</code> bridge.</p>
<div class="card"><div class="status {status_class}"><span class="dot"></span>{status}</div>
{notice}{error_block}
<form method="post" action="/buzz-setup/">
<input type="hidden" name="csrf" value="{CSRF_TOKEN}">
<label for="relay">Community relay URL</label><input id="relay" name="relay" value="{relay}" placeholder="wss://relay.example.com" required>
<label for="private_key">Dedicated agent private key</label><input id="private_key" type="password" name="private_key" placeholder="nsec1… (leave blank to keep the current key)">
<small>This key controls only the remote agent identity. Never use your personal key.</small>
<label for="owner">Owner pubkey (hex)</label><input id="owner" name="owner" value="{owner}" minlength="64" maxlength="64" required>
<label for="auth_tag">Owner authorization tag (optional)</label><input id="auth_tag" type="password" name="auth_tag" placeholder="Leave blank to keep the current tag">
<label for="api_token">Relay API token (optional)</label><input id="api_token" type="password" name="api_token" placeholder="Leave blank to keep the current token">
<label><input style="width:auto" type="checkbox" name="clear_auth" value="1"> Clear the stored authorization tag and API token</label>
<button type="submit">Save and start bridge</button><a class="button secondary" href="/chat">Open Hermes</a>
</form></div>
<h2>Before connecting</h2><p>Create a dedicated agent identity in Buzz, authorize it for the community, and add it to only the channels it needs. The bridge accepts input from the owner only by default.</p>
</main></body></html>""".encode()


class SetupHandler(BaseHTTPRequestHandler):
    server_version = "BuzzSetup/0.1"

    def authorized(self) -> bool:
        return bool(SETUP_TOKEN) and hmac.compare_digest(
            self.headers.get("X-Buzz-Setup-Token", ""), SETUP_TOKEN
        )

    def send_page(self, body: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            body = b"ok\n"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not self.authorized():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_page(render_page())

    def do_POST(self) -> None:
        if not self.authorized():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 32_768:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        csrf = form.get("csrf", [""])[0]
        if not hmac.compare_digest(csrf, CSRF_TOKEN):
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        current = read_managed_env()
        clear_auth = form.get("clear_auth", [""])[0] == "1"
        values = {
            "BUZZ_RELAY_URL": form.get("relay", [""])[0].strip(),
            "BUZZ_PRIVATE_KEY": form.get("private_key", [""])[0].strip() or current.get("BUZZ_PRIVATE_KEY", ""),
            "BUZZ_ACP_AGENT_OWNER": form.get("owner", [""])[0].strip().lower(),
            "BUZZ_AUTH_TAG": "" if clear_auth else (form.get("auth_tag", [""])[0].strip() or current.get("BUZZ_AUTH_TAG", "")),
            "BUZZ_API_TOKEN": "" if clear_auth else (form.get("api_token", [""])[0].strip() or current.get("BUZZ_API_TOKEN", "")),
        }
        errors = validate(values)
        if errors:
            self.send_page(render_page(errors=errors), HTTPStatus.BAD_REQUEST)
            return
        write_managed_env(values)
        CONFIG_CHANGED.set()
        self.send_page(render_page("Configuration saved. The bridge is starting."))

    def log_message(self, format: str, *args: object) -> None:
        message = format % args
        # The container healthcheck polls /healthz every 30s; logging it would
        # bury the bridge output that makes this log worth keeping.
        if "/healthz" in message:
            return
        log(f"setup: {message}")


def run_setup_server() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8788), SetupHandler)
    server.timeout = 1
    while not SHUTDOWN.is_set():
        server.handle_request()
    server.server_close()


def load_bridge_environment() -> list[str]:
    # Compose hands every optional BUZZ_* variable through as an empty string
    # when user.env does not set it. clap reads env vars before defaults, so an
    # empty BUZZ_AUTH_TAG or BUZZ_API_TOKEN would reach buzz-acp as a present
    # but blank value. Unset them and let the file, then clap's defaults, win.
    for key in [k for k, v in os.environ.items() if k.startswith("BUZZ_") and not v]:
        os.environ.pop(key, None)

    values = read_managed_env()
    for key, value in values.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
    return [key for key in REQUIRED_KEYS if not os.environ.get(key)]


def supervise_bridge() -> None:
    global CHILD
    while not SHUTDOWN.is_set():
        missing = load_bridge_environment()
        if missing:
            log("Buzz bridge waiting for: " + " ".join(missing))
            CONFIG_CHANGED.wait(5)
            CONFIG_CHANGED.clear()
            continue

        # Dependency/adapter import check only — it does not need a configured
        # model provider. Never fatal: exiting here would take the setup page
        # down with it, leaving no way to fix the configuration from Umbrel.
        check = subprocess.run(
            ["hermes", "acp", "--check"], capture_output=True, text=True
        )
        for line in (check.stdout + check.stderr).splitlines():
            log(f"hermes acp --check: {line}")
        if check.returncode != 0:
            log(f"hermes acp --check failed ({check.returncode}); retrying in 30s")
            CONFIG_CHANGED.wait(30)
            CONFIG_CHANGED.clear()
            continue

        with CHILD_LOCK:
            CHILD = subprocess.Popen(
                ["buzz-acp"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            stream = CHILD.stdout
        threading.Thread(
            target=mirror_child_output, args=(stream,), daemon=True
        ).start()
        log("Buzz bridge started.")

        while not SHUTDOWN.is_set() and not CONFIG_CHANGED.wait(2):
            with CHILD_LOCK:
                if CHILD is not None and CHILD.poll() is not None:
                    break
        CONFIG_CHANGED.clear()
        with CHILD_LOCK:
            child = CHILD
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        with CHILD_LOCK:
            CHILD = None
        if not SHUTDOWN.is_set():
            time.sleep(2)


def handle_signal(signum: int, _frame: object) -> None:
    SHUTDOWN.set()
    CONFIG_CHANGED.set()


def main() -> None:
    if not SETUP_TOKEN:
        raise SystemExit("BUZZ_SETUP_TOKEN is required")
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    server_thread = threading.Thread(target=run_setup_server, daemon=True)
    server_thread.start()
    supervise_bridge()
    server_thread.join(timeout=3)


if __name__ == "__main__":
    main()
