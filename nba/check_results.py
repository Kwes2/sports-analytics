import json

with open("nba/data/game_performances.json", "r", encoding="utf-8") as f:
    data = json.load(f)

rows = data.get("rows", [])
print(f"Total performances in file: {len(rows)}")

result_counts = {}
for r in rows:
    res = r.get("result", "UNKNOWN")
    result_counts[res] = result_counts.get(res, 0) + 1

print("\nExact Result Tokens found in game_performances.json:")
for k, v in result_counts.items():
    print(f"  '{k}': {v} games")