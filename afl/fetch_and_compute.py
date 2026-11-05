import json
from pathlib import Path
import requests

# 1. Fetch current ladder from Squiggle
url = "https://api.squiggle.com.au/?q=standings"
headers = {"User-Agent": "MyStatsProject/1.0 (personal test)"}
response = requests.get(url, headers=headers)
data = response.json().get("standings", [])

output = []
for team in data:
    # 2. Custom metric calculation
    custom_rating = round((team["percentage"] / 100) * team["pts"], 2)

    output.append({
        "rank": team["rank"],
        "team": team["name"],
        "played": team["played"],
        "points": team["pts"],
        "percentage": team["percentage"],
        "custom_power_score": custom_rating
    })

# 3. Save directly inside the afl/ directory
output_path = Path(__file__).parent / "afl_standings.json"
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)

print("AFL Data Processed:")
print(json.dumps(output[:3], indent=2))