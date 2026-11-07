import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from crawler import fetch_game_summary, crawl_team_rosters
from stats import process_boxscore_players

print("=== IMPACT LAB: TESTING INFLUENCE FORMULAS ON REAL GAME ===")

TEST_GAME_ID = "401704627" # Celtics 132, Knicks 109
_, data = fetch_game_summary(TEST_GAME_ID)

header = data.get("header", {})
comp = header.get("competitions", [{}])[0]
competitors = comp.get("competitors", [])
home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})

home_id = str(home_comp.get("team", {}).get("id"))
away_id = str(away_comp.get("team", {}).get("id"))
home_name = home_comp.get("team", {}).get("displayName")
away_name = away_comp.get("team", {}).get("displayName")

position_map = crawl_team_rosters()
game_players = data.get("boxscore", {}).get("players", [])
date_str = comp.get("date", "")[:10]

game_team_rows, _ = process_boxscore_players(
    game_players, "AWAY", "HOME", 100, 100, date_str, position_map
)

home_starters = [r["player_id"] for r in game_team_rows.get(home_id, {}).get("starters", [])]
away_starters = [r["player_id"] for r in game_team_rows.get(away_id, {}).get("starters", [])]

# Player ID to Name Map
player_names = {}
for p_group in [game_team_rows.get(home_id, {}).get("all_rows", []), game_team_rows.get(away_id, {}).get("all_rows", [])]:
    for p in p_group:
        player_names[p["player_id"]] = p["player"]

# Storage for this game
player_on_court_stats = {} # {pid: {pts_for, pts_against, poss}}
pair_stints = {} # {p1: {teammates: {p2: {pts_for, pts_against, poss}}, opponents: {...}}}

def log_stint(p1, p2, pts_for, pts_against, poss, is_teammate):
    if p1 not in pair_stints:
        pair_stints[p1] = {"teammates": {}, "opponents": {}}
    group = "teammates" if is_teammate else "opponents"
    if p2 not in pair_stints[p1][group]:
        pair_stints[p1][group][p2] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
    pair_stints[p1][group][p2]["pts_for"] += pts_for
    pair_stints[p1][group][p2]["pts_against"] += pts_against
    pair_stints[p1][group][p2]["poss"] += poss

# Working Stint Tracker
class StintEngine:
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

    def step(self, play):
        txt = play.get("text", "").lower()
        period = play.get("period", {}).get("number", 1)
        team_id = str(play.get("team", {}).get("id", ""))

        if period != self.current_period:
            self.commit()
            self.current_period = period

        is_scoring = play.get("scoringPlay", False)
        score_val = play.get("scoreValue", 0)

        if is_scoring and score_val > 0:
            if team_id == self.h_id: self.h_pts += score_val
            elif team_id == self.a_id: self.a_pts += score_val

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

        if "enters the game" in txt or "substitutions" in play.get("type", {}).get("text", "").lower():
            parts = play.get("participants", [])
            if len(parts) >= 2:
                p_in = str(parts[0].get("athlete", {}).get("id", ""))
                p_out = str(parts[1].get("athlete", {}).get("id", ""))
                if p_in and p_out:
                    self.commit()
                    if p_out in self.home_on_court:
                        self.home_on_court.discard(p_out)
                        self.home_on_court.add(p_in)
                    elif p_out in self.away_on_court:
                        self.away_on_court.discard(p_out)
                        self.away_on_court.add(p_in)

    def commit(self):
        stint_poss = (self.h_poss + self.a_poss) / 2.0
        if stint_poss <= 0 and self.h_pts == 0 and self.a_pts == 0:
            return
        if stint_poss <= 0:
            stint_poss = 0.5

        h_list = list(self.home_on_court)
        a_list = list(self.away_on_court)

        # 1. Update individual on-court stats
        for hp in h_list:
            if hp not in player_on_court_stats: player_on_court_stats[hp] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
            player_on_court_stats[hp]["pts_for"] += self.h_pts
            player_on_court_stats[hp]["pts_against"] += self.a_pts
            player_on_court_stats[hp]["poss"] += stint_poss

        for ap in a_list:
            if ap not in player_on_court_stats: player_on_court_stats[ap] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
            player_on_court_stats[ap]["pts_for"] += self.a_pts
            player_on_court_stats[ap]["pts_against"] += self.h_pts
            player_on_court_stats[ap]["poss"] += stint_poss

        # 2. Update Teammates
        for i in range(len(h_list)):
            for j in range(i + 1, len(h_list)):
                p1, p2 = h_list[i], h_list[j]
                log_stint(p1, p2, self.h_pts, self.a_pts, stint_poss, is_teammate=True)
                log_stint(p2, p1, self.h_pts, self.a_pts, stint_poss, is_teammate=True)

        for i in range(len(a_list)):
            for j in range(i + 1, len(a_list)):
                p1, p2 = a_list[i], a_list[j]
                log_stint(p1, p2, self.a_pts, self.h_pts, stint_poss, is_teammate=True)
                log_stint(p2, p1, self.a_pts, self.h_pts, stint_poss, is_teammate=True)

        # 3. Update Opponents
        for hp in h_list:
            for ap in a_list:
                log_stint(hp, ap, self.h_pts, self.a_pts, stint_poss, is_teammate=False)
                log_stint(ap, hp, self.a_pts, self.h_pts, stint_poss, is_teammate=False)

        self.h_pts, self.a_pts = 0, 0
        self.h_poss, self.a_poss = 0.0, 0.0


# Run on real game
engine = StintEngine(home_starters, away_starters, home_id, away_id)
for play in data.get("plays", []):
    engine.step(play)
engine.commit()

# Compute Personal On-Court Baselines for this game
baselines = {}
for pid, st in player_on_court_stats.items():
    p = max(st["poss"], 1.0)
    baselines[pid] = {
        "ortg": (st["pts_for"] / p) * 100.0,
        "drtg": (st["pts_against"] / p) * 100.0
    }

# Compute Influence Deltas for Key Players
print("\n--- SAMPLE INFLUENCE RESULTS (SINGLE GAME REALITY) ---")
key_players = home_starters[:2] + away_starters[:2]

for pid in key_players:
    name = player_names.get(pid, f"Player {pid}")
    p_baseline = baselines.get(pid, {"ortg": 100, "drtg": 100})
    pairs = pair_stints.get(pid, {"teammates": {}, "opponents": {}})

    # Teammate Elevation
    t_off_sum, t_def_sum, t_poss = 0.0, 0.0, 0.0
    for tid, t_data in pairs["teammates"].items():
        poss = t_data["poss"]
        if poss < 2.0: continue
        actual_ortg = (t_data["pts_for"] / poss) * 100.0
        actual_drtg = (t_data["pts_against"] / poss) * 100.0
        t_base = baselines.get(tid, {"ortg": 100, "drtg": 100})

        t_off_sum += (actual_ortg - t_base["ortg"]) * poss
        t_def_sum += (t_base["drtg"] - actual_drtg) * poss
        t_poss += poss

    t_off = round(t_off_sum / t_poss, 2) if t_poss > 0 else 0.0
    t_def = round(t_def_sum / t_poss, 2) if t_poss > 0 else 0.0
    t_net = round(t_off + t_def, 2)

    # Opponent Suppression
    o_off_sum, o_def_sum, o_poss = 0.0, 0.0, 0.0
    for oid, o_data in pairs["opponents"].items():
        poss = o_data["poss"]
        if poss < 2.0: continue
        opp_actual_ortg = (o_data["pts_against"] / poss) * 100.0
        opp_actual_drtg = (o_data["pts_for"] / poss) * 100.0
        o_base = baselines.get(oid, {"ortg": 100, "drtg": 100})

        o_off_sum += (o_base["ortg"] - opp_actual_ortg) * poss
        o_def_sum += (opp_actual_drtg - o_base["drtg"]) * poss
        o_poss += poss

    o_off = round(o_off_sum / o_poss, 2) if o_poss > 0 else 0.0
    o_def = round(o_def_sum / o_poss, 2) if o_poss > 0 else 0.0
    o_net = round(o_off + o_def, 2)

    ovr = round(0.5 * t_net + 0.5 * o_net, 2)

    print(f"\n{name.upper()}:")
    print(f"  Personal Game Baseline: {p_baseline['ortg']:.1f} ORtg | {p_baseline['drtg']:.1f} DRtg")
    print(f"  Teammate Impact: Off: {t_off:+.2f} | Def: {t_def:+.2f} | Net: {t_net:+.2f}")
    print(f"  Opponent Impact: Off: {o_off:+.2f} | Def: {o_def:+.2f} | Net: {o_net:+.2f}")
    print(f"  Overall Impact:  {ovr:+.2f}")