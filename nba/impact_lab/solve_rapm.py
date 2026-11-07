import sys
import json
import sqlite3
from pathlib import Path
import numpy as np

sys.path.append(str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "nba.db"

print("=== IMPACT LAB: RIDGE-REGULARIZED RAPM SOLVER ===")

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

# 3. Map all unique players to matrix column indices
unique_players = sorted(list(players_meta.keys()))
player_to_idx = {pid: i for i, pid in enumerate(unique_players)}
n_players = len(unique_players)

print(f"Total unique players in matrix: {n_players}")

# 4. Build Design Matrix X, Target y, and Weight W
print("Building linear regression matrices (X, y, W)...")
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

    # Target: Home Net Margin per 100 possessions
    net_margin_per_100 = ((h_pts - a_pts) / poss) * 100.0

    # Row vector for X
    row_vec = np.zeros(n_players)
    for p in h_lineup:
        pid = str(p)
        if pid in player_to_idx:
            row_vec[player_to_idx[pid]] += 1.0
            
    for p in a_lineup:
        pid = str(p)
        if pid in player_to_idx:
            row_vec[player_to_idx[pid]] -= 1.0

    X_rows.append(row_vec)
    y_rows.append(net_margin_per_100)
    w_rows.append(poss)  # Weight by possessions

X = np.array(X_rows)
y = np.array(y_rows)
W = np.diag(np.array(w_rows))

print(f"Matrix shapes -> X: {X.shape}, y: {y.shape}")

# 5. Solve Ridge Regression: beta = (X^T W X + lambda * I)^-1 X^T W y
# Lambda (regularization penalty) controls shrinkage for low-sample players
LAMBDA_REG = 3000.0
print(f"Solving Ridge Regression with Lambda = {LAMBDA_REG}...")

XTW = X.T @ W
XTWX = XTW @ X
I_mat = np.eye(n_players)
# Prevent penalizing the intercept/mean shift if needed, or regularize all
beta = np.linalg.solve(XTWX + LAMBDA_REG * I_mat, XTW @ y)

print("Solving complete! Extracting player RAPM ratings...")

# 6. Rank Players
results = []
for pid, idx in player_to_idx.items():
    meta = players_meta.get(pid, {"name": f"Player {pid}", "team": "UNK", "pos": "-"})
    val = float(beta[idx])
    results.append({
        "player_id": pid,
        "player": meta["name"],
        "team": meta["team"],
        "pos": meta["pos"],
        "rapm": round(val, 2)
    })

results.sort(key=lambda x: x["rapm"], reverse=True)

print("\n=== TOP 15 RAPM PLAYERS (TRUE ISOLATED IMPACT) ===")
for rank, p in enumerate(results[:15], 1):
    print(f"  {rank:2d}. {p['player']:<24} ({p['team']:<4} | {p['pos']:<2}) : {p['rapm']:+6.2f}")

print("\n=== BOTTOM 10 RAPM PLAYERS ===")
for rank, p in enumerate(results[-10:], 1):
    print(f"  {rank:2d}. {p['player']:<24} ({p['team']:<4} | {p['pos']:<2}) : {p['rapm']:+6.2f}")