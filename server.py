#!/usr/bin/env python3
"""DouNai App — Static server + Backup API"""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 23018
BACKUP_DIR = Path(__file__).parent / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
AUTH_TOKEN = os.environ.get("DOUNAI_TOKEN", "changeme")  # set via environment variable

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def do_GET(self):
        if self.path == '/api/backup':
            self.handle_backup_get()
        elif self.path == '/api/health':
            self.send_json(200, {"ok": True, "time": datetime.now().isoformat()})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/backup':
            self.handle_backup_post()
        else:
            self.send_json(404, {"error": "not found"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def check_auth(self):
        auth = self.headers.get('Authorization', '')
        if auth != f'Bearer {AUTH_TOKEN}':
            self.send_json(401, {"error": "unauthorized"})
            return False
        return True

    def handle_backup_get(self):
        if not self.check_auth():
            return
        backup_file = BACKUP_DIR / "state.json"
        if backup_file.exists():
            data = json.loads(backup_file.read_text('utf-8'))
            self.send_json(200, data)
        else:
            self.send_json(404, {"error": "no backup found"})

    def handle_backup_post(self):
        if not self.check_auth():
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            # Save current backup
            backup_file = BACKUP_DIR / "state.json"
            backup_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')

            # Also keep a timestamped copy (max 30)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            versioned = BACKUP_DIR / f"state_{ts}.json"
            versioned.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')

            # Clean old versioned backups (keep latest 30)
            versions = sorted(BACKUP_DIR.glob("state_*.json"), reverse=True)
            for old in versions[30:]:
                old.unlink()

            self.send_json(200, {"ok": True, "saved": ts})
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_cors_headers()
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')

    def log_message(self, format, *args):
        # Quieter logging
        if '/api/' in (args[0] if args else ''):
            super().log_message(format, *args)

if __name__ == '__main__':
    print(f"🌸 DouNai server starting on port {PORT}...")
    server = HTTPServer(('127.0.0.1', PORT), Handler)
    print(f"🌸 Listening at http://127.0.0.1:{PORT}")
    server.serve_forever()
