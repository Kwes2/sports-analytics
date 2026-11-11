"""
test_windows.py - Diagnostic test script validating all season windows, 
preset date ranges, and player comparisons relative to current date (2026-11-11).
"""

import sqlite3
from pathlib import Path
from calculator import compute_window_player_stats, search_player_game_performances

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "nba.db"

CURRENT_DATE = "2026-11-11"

print("=" * 70)
print(f" NBA WINDOW VALIDATION TEST (CURRENT DATE: {CURRENT_DATE})")
print("=" * 70)

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# 1. Database Range Audit
cur.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM games")
min_d, max_d, total_games = cur.fetchone()
print(f"Total Games in Database: {total_games}")
print(f"Date Range in Database : {min_d} to {max_d}")

# 2. Games per Season Year
cur.execute("SELECT season_year, COUNT(*) FROM games GROUP BY season_year")
seasons = cur.fetchall()
print("\nGames per Season Year in SQLite:")
for sy, count in seasons:
    print(f"  Season {sy}: {count} games")

# 3. Test Distinct Players
cur.execute("SELECT player_id, player_name FROM players WHERE player_name LIKE '%Luka%' OR player_name LIKE '%Shai%'")
test_players = cur.fetchall()
print("\nTest Player IDs:")
for pid, name in test_players:
    print(f"  {name} -> ID: {pid}")

conn.close()

# 4. Test Calculator Windows for Luka Doncic
luka_id = next((pid for pid, name in test_players if "Luka" in name), None)

if luka_id:
    print("\n" + "=" * 70)
    print(f" TESTING CALCULATOR OUTPUT FOR LUKA DONCIC (#{luka_id})")
    print("=" * 70)

    windows_to_test = [
        ("Current Season 2026-2027 (Oct 2026 -> Present)", "2026-10-01", CURRENT_DATE, [2027]),
        ("Previous Season 2025-2026 (Oct 2025 -> Jun 2026)", "2025-10-01", "2026-06-30", [2026]),
        ("Last 1 Week (Nov 4 -> Nov 11, 2026)", "2026-11-04", CURRENT_DATE, None),
        ("Last 5 Weeks (Oct 7 -> Nov 11, 2026)", "2026-10-07", CURRENT_DATE, None),
        ("Last 5 Weeks (Oct 7 -> Nov 11, 2026)", "2026-10-07", CURRENT_DATE, None),
    ]

    for label, s_date, e_date, s_years in windows_to_test:
        print(f"\n--- Testing Window: {label} ---")
        print(f"    Dates: {s_date} to {e_date} | Season Filter: {s_years}")

        res = compute_window_player_stats(
            start_date=s_date,
            end_date=e_date,
            season_years=s_years
        )

        luka_row = next((p for p in res if str(p["player_id"]) == str(luka_id)), None)

        if luka_row:
            gp = luka_row.get("gp")
            pts = luka_row.get("pts_pg")
            reb = luka_row.get("reb_pg")
            ast = luka_row.get("ast_pg")
            team_share = luka_row.get("team_reb_share")
            on_court_reb = luka_row.get("on_court_reb_pct")
            ast_3p = luka_row.get("ast_3p_pct")
            unast_3p = luka_row.get("unast_3p_pct")
            xprf = luka_row.get("xprf_pg")
            prfoe = luka_row.get("prfoe_pg")

            print(f"    [MATCH FOUND]")
            print(f"    GP: {gp} games | PTS: {pts} | REB: {reb} | AST: {ast}")
            print(f"    Rebound Share: {team_share}% | On-Court Rebounds: {on_court_reb}%")
            print(f"    3PT Creation : {ast_3p}% Assisted | {unast_3p}% Unassisted (Self-Created)")
            print(f"    Volume & PRF : Actual {luka_row.get('prf_pg')} PRF | Expected {xprf} xPRF | Net PRFOE: {prfoe}")
        else:
            print("    [NO GAMES FOUND] (Luka did not play in this date slice)")

print("\n" + "=" * 70)
print(" 5. TESTING GAME FINDER OVERTIME QUERY")
print("=" * 70)

ot_results = search_player_game_performances({"result": "OT"})
print(f"Game performances matching 'OT' token: {len(ot_results)}")
if ot_results:
    for r in ot_results[:3]:
        print(f"  -> {r['date']} | {r['player']} ({r['team']}): {r['pts']} PTS, {r['reb']} REB, {r['ast']} AST | Result: {r['result']} ({r.get('score')})")

print("=" * 70)