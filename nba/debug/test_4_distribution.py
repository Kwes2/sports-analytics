import sys
from pathlib import Path
import json
import math

sys.path.append(str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "data"

print("=== TEST 4: INFLUENCE DISTRIBUTION & PERCENTILE AUDIT ===")

stats_file = DATA_DIR / "player_stats.json"
if not stats_file.exists():
    print("player_stats.json not found.")
    sys.exit(1)

with open(stats_file, "r") as f:
    payload = json.load(f)

all_rows = payload.get("rows", [])
print(f"Total players in database: {len(all_rows)}")

# Filter for players with a meaningful sample (e.g. at least 10 games and 15 min/g)
sample_rows = [r for r in all_rows if r.get("gp", 0) >= 10 and r.get("min_pg", 0) >= 15.0]
print(f"Qualified rotation players (GP >= 10, MIN/G >= 15): {len(sample_rows)}\n")

METRICS = [
    ("Overall Impact", "overall_impact"),
    ("Teammate Net Impact", "teammate_overall_impact"),
    ("Teammate Off Impact", "teammate_off_impact"),
    ("Teammate Def Impact", "teammate_def_impact"),
    ("Opponent Net Impact", "opponent_overall_impact"),
    ("Opponent Off Impact", "opponent_off_impact"),
    ("Opponent Def Impact", "opponent_def_impact")
]

def get_percentile(sorted_vals, p):
    """Calculates exact percentile value from sorted list."""
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

def print_ascii_histogram(vals, num_bins=12):
    """Draws an ASCII distribution curve in the terminal."""
    if not vals:
        return
    min_v, max_v = min(vals), max(vals)
    if min_v == max_v:
        return
    bin_width = (max_v - min_v) / num_bins
    bins = [0] * num_bins
    
    for v in vals:
        idx = int((v - min_v) / bin_width)
        if idx >= num_bins:
            idx = num_bins - 1
        bins[idx] += 1
    
    max_count = max(bins)
    scale = 35.0 / max_count if max_count > 0 else 1.0

    print("  Distribution Curve:")
    for i in range(num_bins):
        b_start = min_v + i * bin_width
        b_end = b_start + bin_width
        bar = "█" * int(bins[i] * scale)
        print(f"  [{b_start:6.1f} to {b_end:6.1f}]: {bar:<36} ({bins[i]})")

for label, key in METRICS:
    vals = [float(r.get(key, 0.0)) for r in sample_rows]
    vals.sort()
    
    mean_val = sum(vals) / len(vals) if vals else 0.0
    variance = sum((x - mean_val) ** 2 for x in vals) / len(vals) if vals else 0.0
    std_dev = math.sqrt(variance)

    p_min = vals[0] if vals else 0.0
    p_05 = get_percentile(vals, 5)
    p_30 = get_percentile(vals, 30)
    p_50 = get_percentile(vals, 50)  # Median
    p_60 = get_percentile(vals, 60)
    p_95 = get_percentile(vals, 95)
    p_max = vals[-1] if vals else 0.0

    print("=" * 65)
    print(f"METRIC: {label.upper()} ({key})")
    print(f"Sample Size: {len(vals)} rotation players")
    print(f"Mean: {mean_val:+.2f} | Median: {p_50:+.2f} | Std Dev: {std_dev:.2f}")
    print("-" * 65)
    print(f"  Min:   {p_min:+6.2f}")
    print(f"  5th%:  {p_05:+6.2f}")
    print(f"  30th%: {p_30:+6.2f}")
    print(f"  50th%: {p_50:+6.2f} (Median)")
    print(f"  60th%: {p_60:+6.2f}")
    print(f"  95th%: {p_95:+6.2f}")
    print(f"  Max:   {p_max:+6.2f}")
    print("-" * 65)
    print_ascii_histogram(vals)
    print("\n")