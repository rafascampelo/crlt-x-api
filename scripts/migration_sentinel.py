"""Private readiness sentinel; performs no migration and serves no clinical data."""

import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from scripts.migrate_production import check_schema


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()
        if self.path == "/health":
            self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *_args):
        pass


def main():
    try:
        check_schema()
        HTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), Handler).serve_forever()
    except Exception as error:  # noqa: BLE001 -- Redact connection details at the CLI boundary.
        print(f"Migration readiness failed ({type(error).__name__})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
