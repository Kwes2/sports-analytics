import sys
from pathlib import Path
import json

sys.path.append(str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "data"

print("=== TEST 3: CASE STUDY ON EXTREME PLAYERS ===")

# Load Player Stats
player_stats_file = DATA_DIR / "player_stats.json"
if not player_stats_file.exists():
    print("player_stats.json does not exist. Run fetch_and_compute.py first.")
    sys.exit(1)

with open(player_stats_file, "r") as f:
    data = json.load(f)

rows = data.get("rows", [])

# Target players to investigate
target_names = ["Hayden Gray", "Kadary Richmond", "Christian Braun", "Keion Brooks Jr.", "Nikola Jokic", "Trae Young"]

print(f"\nSearching among {len(rows)} total player records...")

found_players = []
for r in rows:
    for name in target_names:
        if name.lower() in r.get("player", "").lower():
            found_players.append(r)

for p in found_players:
    print(f"\n---------------------------------------------")
    print(f"PLAYER: {p.get('player')} ({p.get('team')} | {p.get('pos')})")
    print(f"GP: {p.get('gp')} | MIN/G: {p.get('min_pg')} | PTS/G: {p.get('pts_pg')}")
    print(f"Overall Impact: {p.get('overall_impact')}")
    print(f"Teammate Off Impact: {p.get('teammate_off_impact')} | Teammate Def: {p.get('teammate_def_impact')} | Net: {p.get('teammate_overall_impact')}")
    print(f"Opponent Off Impact: {p.get('opponent_off_impact')} | Opponent Def: {p.get('opponent_def_impact')} | Net: {p.get('opponent_overall_impact')}")

    # Check their individual JSON profile
    pid = p.get("player_id")
    profile_path = DATA_DIR / "players" / f"{pid}.json"
    if profile_path.exists():
        with open(profile_path, "r") as pf:
            profile = json.load(pf)
            logs = profile.get("game_logs", {}).get("rows", [])
            print(f"Actual Games in Log: {len(logs)}")
            print("Sample Game Dates in Log:", [l.get("date") for l in logs[:5]])