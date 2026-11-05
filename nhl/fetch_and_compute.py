import json
from pathlib import Path
import requests

url = "https://api-web.nhle.com/v1/standings/now"
data = requests.get(url).json()

output = []
for team in data.get("standings", []):
    gp = team["gamesPlayed"]
    pts = team["points"]
    gf = team["goalFor"]
    ga = team["goalAgainst"]
    
    # Custom Metric: Goal Differential Per Game
    custom_gd_per_game = round((gf - ga) / gp, 3) if gp > 0 else 0

    output.append({
        "team": team["teamName"]["default"],
        "games_played": gp,
        "points": pts,
        "goal_diff": team["goalDifferential"],
        "custom_gd_per_game": custom_gd_per_game
    })

# Save directly inside the nhl/ directory
output_path = Path(__file__).parent / "nhl_standings.json"
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)

print("NHL Data Processed:")
print(json.dumps(output[:3], indent=2))