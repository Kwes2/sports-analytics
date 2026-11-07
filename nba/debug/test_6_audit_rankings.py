import sys
import json
import math
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "data"
STATS_FILE = DATA_DIR / "player_stats.json"

print("=== TEST 6: INFLUENCE AUDIT & TOP/BOTTOM 5 LEADERBOARDS ===")

if not STATS_FILE.exists():
    print(f"File not found: {STATS_FILE}")
    sys.exit(1)

with open(STATS_FILE, "r") as f:
    payload = json.load(f)

all_players = payload.get("rows", [])
print(f"Total players in database: {len(all_players)}")

# Filter for qualified rotation players (GP >= 15, MIN/G >= 15.0)
qualified = [p for p in all_players if p.get("gp", 0) >= 15 and p.get("min_pg", 0) >= 15.0]
print(f"Qualified rotation players (GP >= 15, MIN/G >= 15.0): {len(qualified)}\n")

METRICS = [
    # 3 Teammate Metrics
    ("Teammate Off Impact", "teammate_off_impact", "higher = elevates teammate scoring"),
    ("Teammate Def Impact", "teammate_def_impact", "higher = helps teammates concede fewer points"),
    ("Teammate Net Impact", "teammate_overall_impact", "higher = total net rating lift to teammates"),
    # 3 Opponent Metrics
    ("Opponent Off Impact", "opponent_off_impact", "higher = suppresses opponent scoring below their baseline"),
    ("Opponent Def Impact", "opponent_def_impact", "higher = forces opponent defense to concede more points"),
    ("Opponent Net Impact", "opponent_overall_impact", "higher = total net rating suppression against opponents"),
    # 1 Master Metric
    ("Overall Master Impact", "overall_impact", "50/50 composite of Teammate and Opponent Net Impact")
]


def get_percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return round(d0 + d1, 2)


for label, key, description in METRICS:
    # Sort players by this metric
    sorted_players = sorted(qualified, key=lambda x: float(x.get(key, 0.0)))
    vals = [float(p.get(key, 0.0)) for p in sorted_players]

    p_min = vals[0]
    p_05 = get_percentile(vals, 5)
    p_30 = get_percentile(vals, 30)
    p_50 = get_percentile(vals, 50)  # Median
    p_70 = get_percentile(vals, 70)
    p_95 = get_percentile(vals, 95)
    p_max = vals[-1]

    mean_val = sum(vals) / len(vals)

    print("=" * 75)
    print(f"METRIC: {label.upper()} ({key})")
    print(f"Meaning: {description}")
    print(f"Mean: {mean_val:+.2f} | Median: {p_50:+.2f}")
    print("-" * 75)
    print(f"  Min:   {p_min:+6.2f}")
    print(f"  5th%:  {p_05:+6.2f}")
    print(f"  30th%: {p_30:+6.2f}")
    print(f"  50th%: {p_50:+6.2f} (Median)")
    print(f"  70th%: {p_70:+6.2f}")
    print(f"  95th%: {p_95:+6.2f}")
    print(f"  Max:   {p_max:+6.2f}")
    print("-" * 75)

    # Top 5 (highest to lowest)
    top_5 = sorted_players[-5:][::-1]
    print("  TOP 5 PLAYERS:")
    for rank, p in enumerate(top_5, 1):
        val = float(p.get(key, 0.0))
        print(f"    {rank}. {p.get('player'):<24} ({p.get('team'):<4} | {p.get('pos'):<2}) : {val:+6.2f} (GP: {p.get('gp')}, MIN/G: {p.get('min_pg')})")

    # Bottom 5 (lowest to highest)
    bottom_5 = sorted_players[:5]
    print("\n  BOTTOM 5 PLAYERS:")
    for rank, p in enumerate(bottom_5, 1):
        val = float(p.get(key, 0.0))
        print(f"    {rank}. {p.get('player'):<24} ({p.get('team'):<4} | {p.get('pos'):<2}) : {val:+6.2f} (GP: {p.get('gp')}, MIN/G: {p.get('min_pg')})")
    print("\n")