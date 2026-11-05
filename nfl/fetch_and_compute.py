import json
from pathlib import Path
import requests

url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
data = requests.get(url).json()

output = []
for event in data.get("events", []):
    competition = event["competitions"][0]
    competitors = competition["competitors"]
    
    home = next(c for c in competitors if c["homeAway"] == "home")
    away = next(c for c in competitors if c["homeAway"] == "away")
    
    home_score = int(home.get("score", 0))
    away_score = int(away.get("score", 0))
    
    # Custom metric: Point Differential Margin
    custom_margin = home_score - away_score

    output.append({
        "matchup": event["name"],
        "status": event["status"]["type"]["description"],
        "home_team": home["team"]["displayName"],
        "home_score": home_score,
        "away_team": away["team"]["displayName"],
        "away_score": away_score,
        "custom_home_margin": custom_margin
    })

# Save directly inside the nfl/ directory
output_path = Path(__file__).parent / "nfl_scores.json"
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)

print("NFL Data Processed:")
print(json.dumps(output[:2], indent=2))