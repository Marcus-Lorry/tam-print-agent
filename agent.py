"""Local print agent: HTTPS web app -> localhost -> raw ESC/POS to the Windows printer.

The web app POSTs rendered ESC/POS bytes to http://127.0.0.1:9101/print; this
sends them RAW to the Windows default printer (or the one named in X-Printer).
RAW = the spooler passes bytes untouched, so USB and network printers work the
same way — Windows decides the transport. No dialog, no prompt.

  python agent.py            # run the agent
  python agent.py --selftest # runnable check (no printer needed)

Build a single .exe:  pyinstaller --onefile --noconsole agent.py
Autostart: drop a shortcut to the .exe in shell:startup (or a Run reg key).
"""
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 9101

try:
    import win32print  # pywin32, Windows only
except ImportError:
    win32print = None


def send_to_printer(data: bytes, printer: str | None = None) -> str:
    """RAW-print bytes. Returns the printer name used. Raises on failure."""
    if win32print is None or os.environ.get("AGENT_FAKE"):
        # Non-Windows or forced test mode: write to a file so behaviour is verifiable.
        with open("agent_out.bin", "wb") as f:
            f.write(data)
        return "file:agent_out.bin"
    name = printer or win32print.GetDefaultPrinter()
    h = win32print.OpenPrinter(name)
    try:
        win32print.StartDocPrinter(h, 1, ("receipt", None, "RAW"))
        win32print.StartPagePrinter(h)
        win32print.WritePrinter(h, data)
        win32print.EndPagePrinter(h)
        win32print.EndDocPrinter(h)
    finally:
        win32print.ClosePrinter(h)
    return name


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "*"))
        self.send_header("Access-Control-Allow-Private-Network", "true")  # Chrome PNA

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Printer")
        self.end_headers()

    def do_GET(self):
        # Lets the web app detect the agent (fetch then fall back to backend print).
        self.send_response(200)
        self._cors()
        self.end_headers()
        self.wfile.write(b"print-agent ok")

    def do_POST(self):
        data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            used = send_to_printer(data, self.headers.get("X-Printer") or None)
            code, body = 200, f"printed to {used}".encode()
        except Exception as e:  # bad printer name, offline, etc. -> report, don't crash
            code, body = 500, f"print failed: {e}".encode()
        self.send_response(code)
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass


def serve():
    print(f"print-agent on http://{HOST}:{PORT}  (win32print={'yes' if win32print else 'NO — file mode'})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


def selftest():
    import threading, urllib.request
    os.environ["AGENT_FAKE"] = "1"  # deterministic: file sink, no real printer needed
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    payload = b"\x1b@HELLO\n\n\n"
    r = urllib.request.urlopen(urllib.request.Request(
        f"http://{HOST}:{PORT}/print", data=payload, method="POST"))
    assert r.status == 200, r.status
    assert open("agent_out.bin", "rb").read() == payload
    os.remove("agent_out.bin")
    assert urllib.request.urlopen(f"http://{HOST}:{PORT}/").status == 200  # detection endpoint
    srv.shutdown()
    print("selftest OK")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else serve()
