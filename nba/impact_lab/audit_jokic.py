import sys
import json
import sqlite3
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "nba.db"

print("=== IMPACT LAB: DISSECTING NIKOLA JOKIC ===")

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Find Jokic's player_id
cur.execute("SELECT player_id, player_name, team_abbrev FROM players WHERE player_name LIKE '%Jokic%'")
jokic_row = cur.fetchone()
if not jokic_row:
    print("Could not find Jokic in database!")
    sys.exit(1)

JOKIC_ID = str(jokic_row["player_id"])
print(f"Target: {jokic_row['player_name']} (ID: {JOKIC_ID} | {jokic_row['team_abbrev']})")

# 2. Get Jokic's on-court totals across all stints
cur.execute("SELECT * FROM stints")
all_stints = cur.fetchall()

jokic_pts_for = 0
jokic_pts_against = 0
jokic_poss = 0.0

teammate_pairs = {}
opponent_pairs = {}

for s in all_stints:
    h_lineup = json.loads(s["home_lineup"])
    a_lineup = json.loads(s["away_lineup"])
    poss = float(s["poss"])
    h_pts = int(s["home_pts"])
    a_pts = int(s["away_pts"])

    is_home = JOKIC_ID in h_lineup
    is_away = JOKIC_ID in a_lineup

    if not is_home and not is_away:
        continue

    pts_for = h_pts if is_home else a_pts
    pts_against = a_pts if is_home else h_pts
    my_lineup = h_lineup if is_home else a_lineup
    opp_lineup = a_lineup if is_home else h_lineup

    jokic_pts_for += pts_for
    jokic_pts_against += pts_against
    jokic_poss += poss

    # Track teammates sharing court with Jokic
    for mate in my_lineup:
        if mate != JOKIC_ID:
            if mate not in teammate_pairs:
                teammate_pairs[mate] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
            teammate_pairs[mate]["pts_for"] += pts_for
            teammate_pairs[mate]["pts_against"] += pts_against
            teammate_pairs[mate]["poss"] += poss

    # Track opponents facing Jokic
    for opp in opp_lineup:
        if opp not in opponent_pairs:
            opponent_pairs[opp] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
        opponent_pairs[opp]["pts_for"] += pts_for
        opponent_pairs[opp]["pts_against"] += pts_against
        opponent_pairs[opp]["poss"] += poss

conn.close()

jokic_on_court_ortg = (jokic_pts_for / jokic_poss * 100.0) if jokic_poss > 0 else 0
jokic_on_court_drtg = (jokic_pts_against / jokic_poss * 100.0) if jokic_poss > 0 else 0
jokic_on_court_net = jokic_on_court_ortg - jokic_on_court_drtg

print(f"\n--- JOKIC RAW ON-COURT PROFILE ---")
print(f"Total Stint Possessions: {jokic_poss:.1f}")
print(f"Points For: {jokic_pts_for} | Points Against: {jokic_pts_against}")
print(f"On-Court ORtg: {jokic_on_court_ortg:.2f}")
print(f"On-Court DRtg: {jokic_on_court_drtg:.2f}")
print(f"On-Court Net Rating: {jokic_on_court_net:+.2f}")

# 3. Audit Teammates
print(f"\n--- TOP 5 TEAMMATES SHARING COURT WITH JOKIC ---")
top_teammates = sorted(teammate_pairs.items(), key=lambda x: x[1]['poss'], reverse=True)[:5]
for tid, stats in top_teammates:
    p = stats['poss']
    ortg = (stats['pts_for'] / p * 100.0) if p > 0 else 0
    drtg = (stats['pts_against'] / p * 100.0) if p > 0 else 0
    print(f"Teammate {tid}: Poss={p:.1f} | With Jokic ORtg={ortg:.1f} | DRtg={drtg:.1f} | Net={ortg-drtg:+.1f}")

# 4. Audit Opponents
print(f"\n--- TOP 5 OPPONENTS FACING JOKIC ---")
top_opponents = sorted(opponent_pairs.items(), key=lambda x: x[1]['poss'], reverse=True)[:5]
for oid, stats in top_opponents:
    p = stats['poss']
    # Against Jokic:
    # Opponent points scored = stats['pts_against']
    # Opponent points conceded = stats['pts_for']
    opp_scoring_rate = (stats['pts_against'] / p * 100.0) if p > 0 else 0
    opp_conceding_rate = (stats['pts_for'] / p * 100.0) if p > 0 else 0
    print(f"Opponent {oid}: Poss={p:.1f} | Opponent Scored={opp_scoring_rate:.1f} ORtg | Opponent Conceded={opp_conceding_rate:.1f} DRtg")