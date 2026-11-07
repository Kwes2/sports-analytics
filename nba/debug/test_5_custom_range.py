import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from calculator import compute_window_player_stats

print("=== TEST 5: CUSTOM DATE RANGE QUERY & SPEED AUDIT ===")

# Test an arbitrary 2.5-month window in the middle of the 2025-26 season
START = "2025-11-01"
END = "2026-01-15"

print(f"Executing query for custom window: {START} to {END}...")

t0 = time.time()
rows = compute_window_player_stats(START, END)
duration = (time.time() - t0) * 1000.0  # in milliseconds

print(f"Recalculation Complete in: {duration:.1f} ms!")
print(f"Total active players in this custom window: {len(rows)}")

if rows:
    print("\n--- TOP 5 SCORERS IN THIS CUSTOM WINDOW ---")
    for r in rows[:5]:
        print(f"{r['player']} ({r['team']} | {r['pos']}):")
        print(f"  GP: {r['gp']} | MIN/G: {r['min_pg']} | PTS/G: {r['pts_pg']} | PRF/G: {r['prf_pg']}")
        print(f"  TS%: {r['ts_pct']}% | xeFG%: {r['xefg_pct']}% | SMOE: {r['smoe']}% | MEI: {r['mei']}%")
        print(f"  PAOE: {r['paoe']:+.2f} | Overall Impact: {r['overall_impact']:+.2f}")