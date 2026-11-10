import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler
import urllib.parse
import json

NBA_DIR = Path(__file__).resolve().parent.parent / "nba"
if str(NBA_DIR) not in sys.path:
    sys.path.insert(0, str(NBA_DIR))

from calculator import (
    compute_window_player_stats,
    search_player_game_performances,
    compute_window_single_player_profile
)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.lower()
        params = urllib.parse.parse_qs(parsed.query)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        if "custom_range" in path:
            start_date = params.get("start", [None])[0]
            end_date = params.get("end", [None])[0]
            season_years = [int(y) for y in params.get("season_year", []) if y.isdigit()]
            season_types = [int(t) for t in params.get("season_type", []) if t.isdigit()]
            rows = compute_window_player_stats(start_date, end_date, season_years or None, season_types or None)
            self.wfile.write(json.dumps({"rows": rows}).encode('utf-8'))
        elif "game_finder" in path:
            filters = {}
            for k in ["min_pts", "min_reb", "min_ast", "min_min", "season_year", "season_type"]:
                if k in params and params[k][0].isdigit():
                    filters[k] = int(params[k][0])
            if "result" in params:
                filters["result"] = params["result"][0]
            if "start" in params and "end" in params:
                filters["start_date"] = params["start"][0]
                filters["end_date"] = params["end"][0]
            rows = search_player_game_performances(filters)
            self.wfile.write(json.dumps({"rows": rows}).encode('utf-8'))
        elif "player_window" in path:
            pid = params.get("id", [None])[0]
            start_date = params.get("start", [None])[0]
            end_date = params.get("end", [None])[0]
            profile = compute_window_single_player_profile(pid, start_date, end_date)
            self.wfile.write(json.dumps(profile or {"error": "Not found"}).encode('utf-8'))