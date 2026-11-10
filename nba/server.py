"""
server.py - 100% isolated NBA analytics server on clean port 8055.
Lives inside nba/ and serves only nba/ files and API endpoints.
"""

import json
import socket
import sys
import traceback
import urllib.parse
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

NBA_DIR = Path(__file__).resolve().parent
if str(NBA_DIR) not in sys.path:
    sys.path.insert(0, str(NBA_DIR))

from calculator import (
    compute_window_player_stats,
    search_player_game_performances,
    compute_window_single_player_profile
)

PORT = 8055


class IsolatedNbaHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(NBA_DIR), **kwargs)

    def log_message(self, format, *args):
        # Override to ensure it prints to stdout immediately
        sys.stdout.write(f">> [SERVER LOG] {self.address_string()} - {format % args}\n")
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
        print(f"\n=======================================================")
        print(f">> INCOMING REQUEST: {self.path}")
        print(f"=======================================================")
        sys.stdout.flush()

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.lower()
        params = urllib.parse.parse_qs(parsed.query)

        # 1. Custom Range Recalculation
        if "custom_range" in path:
            start_date = params.get("start", ["2025-10-22"])[0]
            end_date = params.get("end", ["2026-04-15"])[0]
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

        # 2. Game Finder Query
        elif "game_finder" in path:
            filters = {}
            if "min_pts" in params and params["min_pts"][0].isdigit():
                filters["min_pts"] = int(params["min_pts"][0])
            if "min_reb" in params and params["min_reb"][0].isdigit():
                filters["min_reb"] = int(params["min_reb"][0])
            if "min_ast" in params and params["min_ast"][0].isdigit():
                filters["min_ast"] = int(params["min_ast"][0])
            if "min_min" in params and params["min_min"][0].isdigit():
                filters["min_min"] = int(params["min_min"][0])
            if "result" in params and params["result"][0]:
                filters["result"] = params["result"][0].upper()
            if "start" in params and "end" in params:
                filters["start_date"] = params["start"][0]
                filters["end_date"] = params["end"][0]
            if "season_year" in params and params["season_year"][0].isdigit():
                filters["season_year"] = int(params["season_year"][0])
            if "season_type" in params and params["season_type"][0].isdigit():
                filters["season_type"] = int(params["season_type"][0])

            print(f">> [API] Game Finder Query: {filters}")
            try:
                results = search_player_game_performances(filters=filters)
                print(f">> [API Success] Found {len(results)} games.")
                self._send_json_response({"rows": results})
            except Exception as e:
                print(f">> [API ERROR] {e}")
                traceback.print_exc()
                self._send_json_response({"error": str(e), "rows": []}, status=500)
            return

        # 3. Player Window Recalculation
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

        # Fallback to static file server
        super().do_GET()

    def _send_json_response(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server():
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, IsolatedNbaHandler)
    print("=" * 65)
    print(f" NBA Analytics Server running on clean port {PORT}")
    print(f" Open in Browser: http://127.0.0.1:{PORT}/index.html")
    print("=" * 65)
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()