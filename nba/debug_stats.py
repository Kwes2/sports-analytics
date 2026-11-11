"""
debug_stats.py - Diagnostic script to inspect rebound metrics,
assisted/unassisted play-by-play text, and verify exact formulas.
"""

import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "nba.db"
PLAYER_STATS_PATH = DATA_DIR / "player_stats.json"

print("=" * 65)
print(" 1. INSPECTING REBOUND STATS IN PLAYER_STATS.JSON")
print("=" * 65)

if PLAYER_STATS_PATH.exists():
    with open(PLAYER_STATS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("rows", [])
    print(f"Total player records: {len(rows)}")

    # Check top 5 for rebound metrics
    print("\nSample player rebound stats:")
    for r in rows[:10]:
        name = r.get("player")
        pos = r.get("pos")
        reb = r.get("reb_pg")
        trb = r.get("trb_pct")
        team_share = r.get("team_reb_share")
        on_court = r.get("on_court_reb_pct")
        ast_3p = r.get("ast_3p_pct")
        unast_3p = r.get("unast_3p_pct")
        ast_fg = r.get("ast_fg_pct")
        unast_fg = r.get("unast_fg_pct")
        print(f"[{pos}] {name:20} | Reb: {reb} | TRB%: {trb} | TeamShare: {team_share}% | OnCourtReb: {on_court}% | Ast3P: {ast_3p}% | Unast3P: {unast_3p}% | AstFG: {ast_fg}%")
else:
    print(f"Error: {PLAYER_STATS_PATH} not found.")

print("\n" + "=" * 65)
print(" 2. INSPECTING PLAY-BY-PLAY TEXT IN SQLITE FOR ASSISTED 3-POINTERS")
print("=" * 65)

if DB_PATH.exists():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Query sample assisted plays from assisted_baskets table
    cur.execute("SELECT passer_id, scorer_id, val, zone FROM assisted_baskets LIMIT 5")
    ab_rows = cur.fetchall()
    print(f"Assisted Baskets in DB: {len(ab_rows)} sample rows found")
    for row in ab_rows:
        print("  ->", row)

    cur.execute("SELECT COUNT(*) as total_assists, SUM(CASE WHEN val = 3 THEN 1 ELSE 0 END) as three_pt_assists FROM assisted_baskets")
    counts = cur.fetchone()
    print(f"\nTotal assisted plays logged: {counts[0]}")
    print(f"Total 3-point assisted plays logged: {counts[1]}")

    conn.close()
else:
    print(f"Error: {DB_PATH} not found.")

print("\n" + "=" * 65)