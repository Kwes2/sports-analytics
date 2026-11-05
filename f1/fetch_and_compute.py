import json
from pathlib import Path
import requests

url = "https://api.jolpi.ca/ergast/f1/current/driverStandings.json"
data = requests.get(url).json()

standings = data["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]

output = []
for driver in standings:
    pts = float(driver["points"])
    wins = int(driver["wins"])
    
    output.append({
        "position": driver["position"],
        "driver": f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}",
        "team": driver["Constructors"][0]["name"] if driver.get("Constructors") else "N/A",
        "points": pts,
        "wins": wins,
        "custom_win_share": round((wins / pts * 100), 2) if pts > 0 else 0
    })

# Save directly inside the f1/ directory
output_path = Path(__file__).parent / "f1_standings.json"
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)

print("F1 Data Processed:")
print(json.dumps(output[:3], indent=2))