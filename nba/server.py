"""
server.py - Production & Local Web Server for StatsWebsite.
Binds to 0.0.0.0 and respects cloud host assigned PORT.
"""

import json
import os
import socket
import sys
import traceback
import urllib.parse
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

# Identify project root: handles running from root or from inside nba/
CURRENT_DIR = Path(__file__).resolve().parent
if (CURRENT_DIR / "nba").exists():
    PROJECT_ROOT = CURRENT_DIR
elif CURRENT_DIR.name.lower() == "nba":
    PROJECT_ROOT = CURRENT_DIR.parent
else:
    PROJECT_ROOT = CURRENT_DIR

NBA_DIR = PROJECT_ROOT / "nba"
if str(NBA_DIR) not in sys.path:
    sys.path.insert(0, str(NBA_DIR))

from calculator import (
    compute_window_player_stats,
    search_player_game_performances,
    compute_window_single_player_profile
)

# Use cloud host assigned port, or fallback to 8000 locally
PORT = int(os.environ.get("PORT", 8000))


class WebsiteRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def log_message(self, format, *args):
        sys.stdout.write(f">> [SERVER] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.lower()
        params = urllib.parse.parse_qs(parsed.query)

        # -------------------------------------------------------------
        # 1. API: Custom Range Recalculation (Player Stats Table)
        # -------------------------------------------------------------
        if "custom_range" in path:
            start_date = params.get("start", [None])[0]
            end_date = params.get("end", [None])[0]
            season_years = [int(y) for y in params.get("season_year", []) if y.isdigit()]
            season_types = [int(t) for t in params.get("season_type", []) if t.isdigit()]

            print(f">> [API] Custom Range Query: {start_date} to {end_date} | Seasons: {season_years}")
            try:
                rows = compute_window_player_stats(
                    start_date=start_date,
                    end_date=end_date,
                    season_years=season_years or None,
                    season_types=season_types or None
                )
                print(f">> [API Success] Computed {len(rows)} players.")
                self._send_json_response({"rows": rows})
            except Exception as e:
                print(f">> [API ERROR] {e}")
                traceback.print_exc()
                self._send_json_response({"error": str(e), "rows": []}, status=500)
            return

        # -------------------------------------------------------------
        # 2. API: Game Finder Single-Game Performance Search
        # -------------------------------------------------------------
        elif "game_finder" in path:
            filters = {}
            for k in ["min_pts", "min_reb", "min_ast", "min_min", "season_year", "season_type"]:
                if k in params and params[k][0].isdigit():
                    filters[k] = int(params[k][0])
            if "result" in params and params["result"][0]:
                filters["result"] = params["result"][0].upper()
            if "start" in params and "end" in params:
                filters["start_date"] = params["start"][0]
                filters["end_date"] = params["end"][0]

            print(f">> [API] Game Finder Query: {filters}")
            try:
                results = search_player_game_performances(filters=filters)
                print(f">> [API Success] Found {len(results)} game records.")
                self._send_json_response({"rows": results})
            except Exception as e:
                print(f">> [API ERROR] {e}")
                traceback.print_exc()
                self._send_json_response({"error": str(e), "rows": []}, status=500)
            return

        # -------------------------------------------------------------
        # 3. API: Single Player Window Recalculation (Profile Page)
        # -------------------------------------------------------------
        elif "player_window" in path:
            player_id = params.get("id", [None])[0]
            start_date = params.get("start", [None])[0]
            end_date = params.get("end", [None])[0]
            season_years = [int(y) for y in params.get("season_year", []) if y.isdigit()]
            season_types = [int(t) for t in params.get("season_type", []) if t.isdigit()]

            print(f">> [API] Player Window Query: #{player_id} ({start_date} to {end_date})")
            try:
                profile = compute_window_single_player_profile(
                    player_id=player_id,
                    start_date=start_date,
                    end_date=end_date,
                    season_years=season_years or None,
                    season_types=season_types or None
                )
                if profile:
                    self._send_json_response(profile)
                else:
                    self._send_json_response({"error": "No records for window"}, status=404)
            except Exception as e:
                print(f">> [API ERROR] {e}")
                traceback.print_exc()
                self._send_json_response({"error": str(e)}, status=500)
            return

        # Standard file serving for all sports
        super().do_GET()

    def _send_json_response(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ReusableServer(HTTPServer):
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


def run_server():
    # 0.0.0.0 is REQUIRED for Render and public cloud containers
    server_address = ("0.0.0.0", PORT)
    httpd = ReusableServer(server_address, WebsiteRequestHandler)
    print("=" * 65)
    print(f" StatsWebsite Server running on 0.0.0.0:{PORT}")
    print(f" Serving Root: {PROJECT_ROOT}")
    print("=" * 65)
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()