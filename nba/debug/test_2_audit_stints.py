import sys
from pathlib import Path
import json

sys.path.append(str(Path(__file__).parent.parent))

from crawler import fetch_game_summary, crawl_team_rosters
from stats import process_boxscore_players
from stints import StintTracker

print("=== TEST 2: SINGLE-GAME STINT & LINEUP AUDIT ===")

# Use a recent high-profile game (or the first completed game)
TEST_GAME_ID = "401704652" # Celtics vs Knicks or similar
print(f"Fetching raw summary for game ID: {TEST_GAME_ID}...")

_, data = fetch_game_summary(TEST_GAME_ID)
if not data:
    # Fallback to any recent game ID from summary
    print("Could not fetch 401704652, trying alternate...")
    TEST_GAME_ID = "401909923"
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

print(f"Matchup: {away_name} (ID: {away_id}) @ {home_name} (ID: {home_id})")

# 1. Process Starters
position_map = crawl_team_rosters()
game_players = data.get("boxscore", {}).get("players", [])
date_str = comp.get("date", "")[:10]

game_team_rows, _ = process_boxscore_players(
    game_players, "AWAY", "HOME", 100, 100, date_str, position_map
)

home_starters = [r["player_id"] for r in game_team_rows.get(home_id, {}).get("starters", [])]
away_starters = [r["player_id"] for r in game_team_rows.get(away_id, {}).get("starters", [])]

print(f"Home Starters Count: {len(home_starters)} -> {home_starters}")
print(f"Away Starters Count: {len(away_starters)} -> {away_starters}")

# 2. Step through Play-by-Play & Audit Lineup Integrity
plays = data.get("plays", [])
print(f"Total plays to simulate: {len(plays)}")

tracker = StintTracker(home_starters, away_starters, home_id, away_id)
ledger = {}

stint_count = 0
violations = 0

for idx, play in enumerate(plays):
    tracker.process_play(play, ledger)

    # Health Check: Are there always 5 players on each team?
    h_len = len(tracker.home_on_court)
    a_len = len(tracker.away_on_court)

    if h_len != 5 or a_len != 5:
        violations += 1
        if violations <= 5:
            print(f"[VIOLATION at play {idx} | Q{play.get('period', {}).get('number')} {play.get('clock', {}).get('displayValue')}]: Home on court = {h_len}, Away on court = {a_len}")
            print(f"Play Text: '{play.get('text')}'")

# Final Commit
tracker.commit_stint(ledger)

print(f"\nTotal Lineup Violations (Not 5-on-5): {violations}")
print(f"Tracked Players in Game Ledger: {len(ledger)}")

# Sample one player's interactions
if home_starters:
    sample_pid = home_starters[0]
    p_data = ledger.get(sample_pid, {})
    print(f"\n--- Co-occurrence data for Starter {sample_pid} ---")
    print(f"Teammates recorded with him: {len(p_data.get('teammates', {}))}")
    print(f"Opponents recorded against him: {len(p_data.get('opponents', {}))}")
    
    for tid, stats in list(p_data.get('teammates', {}).items())[:3]:
        poss = stats['poss']
        avg_ortg = stats['tot_ortg'] / poss if poss > 0 else 0
        avg_drtg = stats['tot_drtg'] / poss if poss > 0 else 0
        print(f"  Teammate {tid} -> Possessions: {poss} | Stint ORtg: {round(avg_ortg, 1)} | Stint DRtg: {round(avg_drtg, 1)}")