import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from crawler import fetch_game_summary, crawl_team_rosters
from stats import process_boxscore_players

print("=== IMPACT LAB: LIVE STINT TRACER ===")

# Test Game: Celtics vs Knicks
TEST_GAME_ID = "401704627"
print(f"Fetching raw game summary for {TEST_GAME_ID}...")

_, data = fetch_game_summary(TEST_GAME_ID)
if not data:
    print("Could not fetch game!")
    sys.exit(1)

header = data.get("header", {})
comp = header.get("competitions", [{}])[0]
competitors = comp.get("competitors", [])
home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})

home_id = str(home_comp.get("team", {}).get("id"))
away_id = str(away_comp.get("team", {}).get("id"))
home_name = home_comp.get("team", {}).get("displayName")
away_name = away_comp.get("team", {}).get("displayName")
print(f"Matchup: {away_name} @ {home_name}")

position_map = crawl_team_rosters()
game_players = data.get("boxscore", {}).get("players", [])
date_str = comp.get("date", "")[:10]

game_team_rows, _ = process_boxscore_players(
    game_players, "AWAY", "HOME", 100, 100, date_str, position_map
)

home_starters = [r["player_id"] for r in game_team_rows.get(home_id, {}).get("starters", [])]
away_starters = [r["player_id"] for r in game_team_rows.get(away_id, {}).get("starters", [])]

# Standalone clean tracker to trace every stint
class DiagnosticTracker:
    def __init__(self, h_starters, a_starters, h_id, a_id):
        self.h_id = str(h_id)
        self.a_id = str(a_id)
        self.home_on_court = set(str(p) for p in h_starters)
        self.away_on_court = set(str(p) for p in a_starters)
        self.current_period = 1

        self.h_pts = 0
        self.a_pts = 0
        self.h_poss = 0.0
        self.a_poss = 0.0
        self.stint_number = 1

    def handle_play(self, play):
        txt = play.get("text", "").lower()
        period = play.get("period", {}).get("number", 1)
        team_id = str(play.get("team", {}).get("id", ""))

        if period != self.current_period:
            self.commit(f"End of Q{self.current_period}")
            self.current_period = period

        is_scoring = play.get("scoringPlay", False)
        score_val = play.get("scoreValue", 0)

        if is_scoring and score_val > 0:
            if team_id == self.h_id:
                self.h_pts += score_val
            elif team_id == self.a_id:
                self.a_pts += score_val

        # Possessions
        if "defensive rebound" in txt or ("rebound" in txt and "offensive" not in txt):
            if team_id == self.h_id: self.a_poss += 1.0
            elif team_id == self.a_id: self.h_poss += 1.0
        elif "turnover" in txt or "lost ball" in txt or "bad pass" in txt:
            if team_id == self.h_id: self.h_poss += 1.0
            elif team_id == self.a_id: self.a_poss += 1.0
        elif "makes free throw" in txt and ("2 of 2" in txt or "3 of 3" in txt or "1 of 1" in txt):
            if team_id == self.h_id: self.h_poss += 1.0
            elif team_id == self.a_id: self.a_poss += 1.0
        elif is_scoring and ("jumper" in txt or "layup" in txt or "dunk" in txt or "three point" in txt or "shot" in txt):
            if team_id == self.h_id: self.h_poss += 1.0
            elif team_id == self.a_id: self.a_poss += 1.0

        # Sub
        if "enters the game" in txt or "substitutions" in play.get("type", {}).get("text", "").lower():
            parts = play.get("participants", [])
            if len(parts) >= 2:
                p_in = str(parts[0].get("athlete", {}).get("id", ""))
                p_out = str(parts[1].get("athlete", {}).get("id", ""))
                if p_in and p_out:
                    self.commit(f"Sub: {p_in} for {p_out}")
                    if p_out in self.home_on_court:
                        self.home_on_court.discard(p_out)
                        self.home_on_court.add(p_in)
                    elif p_out in self.away_on_court:
                        self.away_on_court.discard(p_out)
                        self.away_on_court.add(p_in)

    def commit(self, reason):
        tot_poss = (self.h_poss + self.a_poss) / 2.0
        if tot_poss > 0 or self.h_pts > 0 or self.a_pts > 0:
            h_ortg = (self.h_pts / max(self.h_poss, 1.0)) * 100.0
            a_ortg = (self.a_pts / max(self.a_poss, 1.0)) * 100.0
            print(f"Stint #{self.stint_number:02d} [{reason:<22}] -> Poss: {tot_poss:4.1f} | Score: {self.a_pts:2d}-{self.h_pts:2d} | Away ORtg: {a_ortg:5.1f} | Home ORtg: {h_ortg:5.1f}")
            self.stint_number += 1

        self.h_pts = 0
        self.a_pts = 0
        self.h_poss = 0.0
        self.a_poss = 0.0


# Run on all plays of this game
tracer = DiagnosticTracker(home_starters, away_starters, home_id, away_id)
for play in data.get("plays", []):
    tracer.handle_play(play)
tracer.commit("End of Game")