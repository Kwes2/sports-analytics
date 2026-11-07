import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Set path to allow importing calculator and db
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR / "nba"))

from calculator import compute_window_player_stats
from db import DB_PATH


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        start_date = query_components.get("start", [None])[0]
        end_date = query_components.get("end", [None])[0]

        if not start_date or not end_date:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Both 'start' and 'end' date query parameters are required (YYYY-MM-DD)."}).encode())
            return

        try:
            # Query and compute window on the fly
            rows = compute_window_player_stats(start_date, end_date, db_path=DB_PATH)

            payload = {
                "start_date": start_date,
                "end_date": end_date,
                "player_count": len(rows),
                "meta_keys": ["player", "team", "pos"],
                "rows": rows
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "s-maxage=600, stale-while-revalidate")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())