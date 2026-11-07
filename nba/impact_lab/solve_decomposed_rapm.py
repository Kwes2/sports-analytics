import sys
import json
import sqlite3
from pathlib import Path
import numpy as np

sys.path.append(str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "nba.db"

print("=== IMPACT LAB: DECOMPOSED RAPM (OFFENSE & DEFENSE) ===")

if not DB_PATH.exists():
    print("nba.db not found. Run fetch_and_compute.py first.")
    sys.exit(1)

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Load Players Lookup
cur.execute("SELECT player_id, player_name, team_abbrev, pos FROM players")
players_meta = {str(r["player_id"]): {"name": r["player_name"], "team": r["team_abbrev"], "pos": r["pos"]} for r in cur.fetchall()}

# 2. Load Stints
print("Loading stints from nba.db...")
cur.execute("SELECT home_lineup, away_lineup, home_pts, away_pts, poss FROM stints")
stint_rows = cur.fetchall()
conn.close()

print(f"Loaded {len(stint_rows)} stint records.")

unique_players = sorted(list(players_meta.keys()))
player_to_idx = {pid: i for i, pid in enumerate(unique_players)}
n_players = len(unique_players)

# Total coefficients = 2 * n_players (First N are Offense, Next N are Defense)
print(f"Total unique players: {n_players} | Matrix columns: {2 * n_players}")

print("Building linear regression matrices for Decomposed RAPM...")
X_rows = []
y_rows = []
w_rows = []

for sr in stint_rows:
    poss = float(sr["poss"])
    if poss <= 0:
        continue
    
    h_lineup = json.loads(sr["home_lineup"])
    a_lineup = json.loads(sr["away_lineup"])
    
    if len(h_lineup) != 5 or len(a_lineup) != 5:
        continue

    h_pts = int(sr["home_pts"])
    a_pts = int(sr["away_pts"])

    home_ortg = (h_pts / poss) * 100.0
    away_ortg = (a_pts / poss) * 100.0

    # Row 1: Home Offense vs Away Defense
    row_home_off = np.zeros(2 * n_players)
    for p in h_lineup:
        pid = str(p)
        if pid in player_to_idx:
            row_home_off[player_to_idx[pid]] += 1.0  # Offense
    for p in a_lineup:
        pid = str(p)
        if pid in player_to_idx:
            row_home_off[n_players + player_to_idx[pid]] -= 1.0  # Defense

    X_rows.append(row_home_off)
    y_rows.append(home_ortg)
    w_rows.append(poss)

    # Row 2: Away Offense vs Home Defense
    row_away_off = np.zeros(2 * n_players)
    for p in a_lineup:
        pid = str(p)
        if pid in player_to_idx:
            row_away_off[player_to_idx[pid]] += 1.0  # Offense
    for p in h_lineup:
        pid = str(p)
        if pid in player_to_idx:
            row_away_off[n_players + player_to_idx[pid]] -= 1.0  # Defense

    X_rows.append(row_away_off)
    y_rows.append(away_ortg)
    w_rows.append(poss)

X = np.array(X_rows)
y = np.array(y_rows)
W = np.diag(np.array(w_rows))

print(f"Matrix shapes -> X: {X.shape}, y: {y.shape}")

# Solve Ridge Regression
LAMBDA_REG = 4000.0
print(f"Solving Decomposed Ridge Regression with Lambda = {LAMBDA_REG}...")

XTW = X.T @ W
XTWX = XTW @ X
I_mat = np.eye(2 * n_players)
beta = np.linalg.solve(XTWX + LAMBDA_REG * I_mat, XTW @ y)

print("Solving complete! Extracting ORAPM and DRAPM ratings...")

results = []
for pid, idx in player_to_idx.items():
    meta = players_meta.get(pid, {"name": f"Player {pid}", "team": "UNK", "pos": "-"})
    orapm = float(beta[idx])
    drapm = float(beta[n_players + idx])
    net_rapm = orapm + drapm

    results.append({
        "player_id": pid,
        "player": meta["name"],
        "team": meta["team"],
        "pos": meta["pos"],
        "orapm": round(orapm, 2),
        "drapm": round(drapm, 2),
        "net_rapm": round(net_rapm, 2)
    })

# Top 15 Offensive RAPM
results.sort(key=lambda x: x["orapm"], reverse=True)
print("\n=== TOP 10 OFFENSIVE RAPM (ORAPM) ===")
for rank, p in enumerate(results[:10], 1):
    print(f"  {rank:2d}. {p['player']:<24} ({p['team']:<4} | {p['pos']:<2}) : {p['orapm']:+6.2f}")

# Top 15 Defensive RAPM
results.sort(key=lambda x: x["drapm"], reverse=True)
print("\n=== TOP 10 DEFENSIVE RAPM (DRAPM) ===")
for rank, p in enumerate(results[10:], 1):
    print(f"  {rank:2d}. {p['player']:<24} ({p['team']:<4} | {p['pos']:<2}) : {p['drapm']:+6.2f}")

# Top 15 Net RAPM
results.sort(key=lambda x: x["net_rapm"], reverse=True)
print("\n=== TOP 10 NET RAPM (OVERALL) ===")
for rank, p in enumerate(results[:10], 1):
    print(f"  {rank:2d}. {p['player']:<24} ({p['team']:<4} | {p['pos']:<2}) : Net: {p['net_rapm']:+6.2f} (Off: {p['orapm']:+5.2f}, Def: {p['drapm']:+5.2f})")