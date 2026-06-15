#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strategy 4 (optional / heavy weapon): local Chrome headless fetcher.

- Use cases: CSR-limited or mild-captcha articles
- Launch ~1.5s, fetch ~2–3s
- Chrome DevTools Protocol (CDP) via `websocket-client`

Design principles:
- No background processes left behind (each call starts an independent Chrome instance)
- `--user-data-dir` for isolation (no pollution of the user's main Chrome)
- 30s auto-kill timeout
"""

from __future__ import annotations
import os
import re
import subprocess
import tempfile
import time
import json
import urllib.request
from typing import Optional
from dataclasses import dataclass

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_TIMEOUT = 25


@dataclass
class ChromeFetchResult:
    success: bool
    method: str = "chrome_headless"
    html: str = ""
    status_code: int = 0
    error: str = ""
    duration: float = 0.0


def _find_free_port() -> int:
    """Find a free port for Chrome DevTools."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_devtools(port: int, timeout: float = 10.0) -> bool:
    """Wait for the Chrome DevTools endpoint to be ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def fetch_with_chrome(url: str, timeout: int = DEFAULT_TIMEOUT, wait_js: float = 2.5) -> ChromeFetchResult:
    """
    Fetch a URL with local Chrome headless.

    wait_js: seconds to wait for JS rendering (WeChat CSR needs ~2s).
    """
    if not os.path.exists(CHROME_PATH):
        return ChromeFetchResult(
            success=False,
            error=f"Chrome not found at {CHROME_PATH}",
        )

    port = _find_free_port()
    user_data_dir = tempfile.mkdtemp(prefix="wechat-fetch-")

    # Chrome command-line arguments
    args = [
        CHROME_PATH,
        "--headless=new",                  # New headless mode
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--user-data-dir={user_data_dir}",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--disable-translate",
        "--metrics-recording-only",
        "--no-first-run",
        "--safebrowsing-disable-auto-update",
        "--hide-scrollbars",
        "--window-size=1280,800",
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "about:blank",                     # Open about:blank first, navigate later
    ]

    proc = None
    start_time = time.time()
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,         # Independent process group, easy to kill
        )

        # Wait for DevTools to be ready
        if not _wait_for_devtools(port, timeout=8):
            return ChromeFetchResult(
                success=False,
                error="Chrome DevTools startup timeout",
            )

        # Find the newly opened target (about:blank)
        targets_url = f"http://127.0.0.1:{port}/json"
        with urllib.request.urlopen(targets_url, timeout=3) as r:
            targets = json.loads(r.read())
        target = next(
            (t for t in targets if t.get("type") == "page" and t.get("url") == "about:blank"),
            None,
        )
        if not target:
            return ChromeFetchResult(
                success=False,
                error="Could not find page target",
            )

        # Open a new WebSocket to the page target
        import websocket  # pip install websocket-client
        ws = websocket.create_connection(
            target["webSocketDebuggerUrl"],
            timeout=timeout,
        )

        try:
            mid = [0]
            def send(method: str, params: Optional[dict] = None) -> int:
                mid[0] += 1
                msg = {"id": mid[0], "method": method}
                if params:
                    msg["params"] = params
                ws.send(json.dumps(msg))
                return mid[0]

            # Navigate to the target URL
            send("Page.enable")
            send("Page.navigate", {"url": url})

            # Wait for Page.loadEventFired or timeout
            load_deadline = time.time() + timeout
            while time.time() < load_deadline:
                try:
                    ws.settimeout(1)
                    msg = json.loads(ws.recv())
                    if msg.get("method") == "Page.loadEventFired":
                        break
                except Exception:
                    pass
                if time.time() - start_time > timeout:
                    break

            # Wait for JS render
            time.sleep(wait_js)

            # Get HTML
            send("DOM.getDocument", {"depth": -1, "pierce": True})
            while True:
                try:
                    ws.settimeout(2)
                    msg = json.loads(ws.recv())
                    if msg.get("id") == mid[0] and "result" in msg:
                        doc = msg["result"]["root"]
                        break
                except Exception:
                    return ChromeFetchResult(success=False, error="DOM retrieval timeout")

            # Serialise HTML
            def get_outer_html(node_id: str) -> str:
                send("DOM.getOuterHTML", {"nodeId": node_id, "outerHTMLPolicy": "prefer"})
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get("id") == mid[0] and "result" in msg:
                        return msg["result"]["outerHTML"]

            html = get_outer_html(doc["nodeId"])

            return ChromeFetchResult(
                success=True,
                html=html,
                status_code=200,
                duration=time.time() - start_time,
            )
        finally:
            try:
                ws.close()
            except Exception:
                pass
    except Exception as e:
        return ChromeFetchResult(
            success=False,
            error=f"{type(e).__name__}: {e}",
        )
    finally:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        # Clean up user data dir
        try:
            import shutil
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(f"Fetching {url} ...")
    r = fetch_with_chrome(url, timeout=20, wait_js=2)
    print(f"Success: {r.success}, duration: {r.duration:.1f}s, html len: {len(r.html)}")
    if r.error:
        print(f"Error: {r.error}")
    if r.success:
        # Check meta
        m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', r.html)
        if m:
            print(f"og:title = {m.group(1)}")
