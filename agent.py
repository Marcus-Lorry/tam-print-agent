#!/usr/bin/env python3
"""Local ESC/POS print agent for Shazada invoices.

Runs a plain-HTTP server on 127.0.0.1 that the admin site's browser calls
directly to print thermal receipts on the Xprinter T80Q, bypassing the
OS print pipeline (browser -> print dialog -> driver) entirely.

No TLS/cert is needed: browsers treat http://127.0.0.1 as a secure origin, so
an HTTPS admin page may call it as long as we return the CORS + Private-Network-
Access headers below. That removes the per-PC cert-trust step entirely.

Endpoints:
  GET  /health  -> {"status": "ok", "version": ..., "printer_mode": ...}
  POST /print   -> body is the JSON from GET /admin/invoices/{id}/print-data
"""
from __future__ import annotations

import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from printer import ReceiptPrinter

VERSION = "1.0.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("print-agent")


def base_dir() -> Path:
    # PyInstaller --onefile extracts to a temp dir (sys._MEIPASS) on every run;
    # config.json must live next to the actual exe so edits survive updates.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_config(base: Path) -> dict:
    config_path = base / "config.json"
    example_path = base / "config.example.json"
    if not config_path.exists():
        if not example_path.exists():
            raise SystemExit("config.json missing and no config.example.json to copy from.")
        config_path.write_text(example_path.read_text())
        log.warning("config.json not found - created from config.example.json. Edit it, then restart.")
    return json.loads(config_path.read_text())


class Handler(BaseHTTPRequestHandler):
    config: dict = {}
    printer: ReceiptPrinter | None = None

    def _cors_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        allowed = self.config.get("allowed_origin")
        if origin and allowed and origin == allowed:
            return origin
        return None

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # CORS preflight for POST /print
        self.send_response(204)
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            # Chrome's Private Network Access preflight (HTTPS page -> loopback).
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {
                "status": "ok",
                "version": VERSION,
                "printer_mode": self.config.get("printer", {}).get("mode"),
            })
            return
        self._send_json(404, {"success": False, "message": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/print":
            self._send_json(404, {"success": False, "message": "Not found"})
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"success": False, "message": "Invalid JSON"})
            return
        try:
            self.printer.print_receipt(data)
        except Exception as exc:  # printer offline, wrong VID/PID, USB permission, etc.
            log.exception("Print failed")
            self._send_json(500, {"success": False, "message": str(exc)})
            return
        self._send_json(200, {"success": True})

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    base = base_dir()
    config = load_config(base)

    Handler.config = config
    Handler.printer = ReceiptPrinter(config)

    port = config.get("port", 17777)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)

    log.info("Shazada print agent listening on http://127.0.0.1:%s", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
