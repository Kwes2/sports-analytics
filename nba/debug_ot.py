"""
debug_ot.py - Diagnostic script to verify Overtime (OT) detection in raw game files.
"""

import json
from pathlib import Path

BOX_DIR = Path(__file__).parent / "data" / "boxscores"
GAMES_FILE = Path(__file__).parent / "data" / "completed_games.json"

print("=" * 65)
print(" 1. INSPECTING COMPLETED GAMES LIST FOR OVERTIME")
print("=" * 65)

if GAMES_FILE.exists():
    with open(GAMES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("rows", [])
    ot_games = [g for g in rows if g.get("is_overtime")]
    print(f"Total completed games: {len(rows)}")
    print(f"Games marked with is_overtime: {len(ot_games)}")
    for g in ot_games[:5]:
        print(f"  -> {g['date']} | {g['home_team']} {g['home_score']} vs {g['away_team']} {g['away_score']} (OT periods: {g.get('overtime_periods')})")

print("\n" + "=" * 65)
print(" 2. INSPECTING RAW BOXSCORE JSON FOR MAX PERIOD NUMBER")
print("=" * 65)

box_files = list(BOX_DIR.glob("*.json"))
print(f"Found {len(box_files)} box score files in {BOX_DIR}")

found_ot_count = 0
sample_ot_games = []

for bf in box_files[:400]:
    try:
        with open(bf, "r", encoding="utf-8") as f:
            game = json.load(f)
        pbp = game.get("play_by_play", {}).get("rows", [])
        
        # Check if any play has period > 4 or 'OT' in period string
        max_p = 4
        has_ot = False
        for p in pbp:
            period_str = str(p.get("period", ""))
            if "OT" in period_str or period_str in ["5", "6", "7"]:
                has_ot = True
                break
                
        if has_ot:
            found_ot_count += 1
            if len(sample_ot_games) < 5:
                sample_ot_games.append({
                    "id": game.get("game_id"),
                    "date": game.get("date"),
                    "matchup": f"{game.get('away_team')} {game.get('away_score')} @ {game.get('home_team')} {game.get('home_score')}"
                })
    except Exception:
        continue

print(f"Games with Overtime in play-by-play (sample of 400): {found_ot_count}")
for sg in sample_ot_games:
    print(f"  -> ID: {sg['id']} | {sg['date']} | {sg['matchup']}")

print("=" * 65)