"""
server.py - Production & Local Web Server for StatsWebsite.
Auto-detects data locations, eliminates 502 OOM via fast-path profile caching,
and serves all sports seamlessly.
"""

import gc
import json
import os
import socket
import subprocess
import sys
import threading
import traceback
import urllib.parse
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent

if (CURRENT_DIR / "data").exists():
    NBA_DIR = CURRENT_DIR
    PROJECT_ROOT = CURRENT_DIR.parent if CURRENT_DIR.parent.name else CURRENT_DIR
elif (CURRENT_DIR.parent / "nba" / "data").exists():
    PROJECT_ROOT = CURRENT_DIR.parent
    NBA_DIR = PROJECT_ROOT / "nba"
else:
    PROJECT_ROOT = CURRENT_DIR
    NBA_DIR = CURRENT_DIR

if str(NBA_DIR) not in sys.path:
    sys.path.insert(0, str(NBA_DIR))

from calculator import (
    compute_window_player_stats,
    search_player_game_performances,
    compute_window_single_player_profile
)

PORT = int(os.environ.get("PORT", 8000))

UPDATE_LOCK = threading.Lock()
IS_UPDATING = False


def run_update_pipeline():
    global IS_UPDATING
    try:
        script_path = NBA_DIR / "fetch_and_compute.py"
        print(f">> [UPDATER] Running {script_path}...")
        subprocess.run([sys.executable, str(script_path)], check=True)
        print(">> [UPDATER] Pipeline completed successfully.")
    except Exception as e:
        print(f">> [UPDATER ERROR] {e}")
    finally:
        with UPDATE_LOCK:
            IS_UPDATING = False


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
        global IS_UPDATING
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
                gc.collect()
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
                gc.collect()
            except Exception as e:
                print(f">> [API ERROR] {e}")
                traceback.print_exc()
                self._send_json_response({"error": str(e), "rows": []}, status=500)
            return

        # -------------------------------------------------------------
        # 3. API: Single Player Window Recalculation (Profile & Compare)
        # -------------------------------------------------------------
        elif "player_window" in path:
            player_id = params.get("id", [None])[0]
            start_date = params.get("start", [None])[0]
            end_date = params.get("end", [None])[0]
            season_years = [int(y) for y in params.get("season_year", []) if y.isdigit()]
            season_types = [int(t) for t in params.get("season_type", []) if t.isdigit()]

            if not player_id:
                self._send_json_response({"error": "No player_id provided"}, status=400)
                return

            # FAST-PATH: If querying full season without date slices, serve precomputed JSON (0ms, 0MB RAM)
            is_full_season = (not start_date and not end_date and (not season_years or season_years == [2027]) and not season_types)
            if is_full_season:
                cached_file = NBA_DIR / "data" / "players" / f"{player_id}.json"
                if cached_file.exists():
                    print(f">> [API Fast-Path] Serving cached profile for Player #{player_id}")
                    try:
                        with open(cached_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        self._send_json_response(data)
                        return
                    except Exception:
                        pass

            print(f">> [API Dynamic] Computing Player #{player_id} Window: {start_date} to {end_date} | Season: {season_years}")
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
                    # Graceful fallback to static profile if database has no records for requested slice
                    cached_file = NBA_DIR / "data" / "players" / f"{player_id}.json"
                    if cached_file.exists():
                        with open(cached_file, "r", encoding="utf-8") as f:
                            self._send_json_response(json.load(f))
                    else:
                        self._send_json_response({"error": f"No records found for player #{player_id}"}, status=404)
                gc.collect()
            except Exception as e:
                print(f">> [API ERROR in player_window] {e}")
                traceback.print_exc()
                # Return static fallback rather than crashing with 500/502
                cached_file = NBA_DIR / "data" / "players" / f"{player_id}.json"
                if cached_file.exists():
                    with open(cached_file, "r", encoding="utf-8") as f:
                        self._send_json_response(json.load(f))
                else:
                    self._send_json_response({"error": str(e)}, status=500)
            return

        # -------------------------------------------------------------
        # 3b. API: Data Update Status & Trigger
        # -------------------------------------------------------------
        elif "update_status" in path:
            last_updated = "Unknown"
            lu_file = NBA_DIR / "data" / "last_updated.json"
            if lu_file.exists():
                try:
                    with open(lu_file, "r", encoding="utf-8") as f:
                        last_updated = json.load(f).get("last_updated", "Unknown")
                except Exception:
                    pass
            self._send_json_response({"updating": IS_UPDATING, "last_updated": last_updated})
            return

        elif "trigger_update" in path:
            with UPDATE_LOCK:
                if IS_UPDATING:
                    self._send_json_response({"status": "already_running", "updating": True})
                    return
                IS_UPDATING = True
                t = threading.Thread(target=run_update_pipeline, daemon=True)
                t.start()
            self._send_json_response({"status": "started", "updating": True})
            return

        # -------------------------------------------------------------
        # 4. Fallback Router for Static Data Files
        # -------------------------------------------------------------
        if path.startswith("/data/") or path.startswith("data/"):
            clean = path.replace("/data/", "").replace("data/", "")
            alt_nba_path = NBA_DIR / "data" / clean
            if alt_nba_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                with open(alt_nba_path, "rb") as f:
                    self.wfile.write(f.read())
                return

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
    server_address = ("0.0.0.0", PORT)
    httpd = ReusableServer(server_address, WebsiteRequestHandler)
    print(f">> Server ready on port {PORT}. Serving files...")
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()