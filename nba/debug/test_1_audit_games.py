import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from crawler import crawl_full_season_schedule, crawl_team_rosters

print("=== TEST 1: AUDITING SCHEDULE & GAME TYPES ===")

# 1. Crawl Schedule
completed_games, upcoming_games, completed_ids = crawl_full_season_schedule(seasons=[2025, 2026])

print(f"\nTotal completed games captured: {len(completed_games)}")
print(f"Total upcoming games captured: {len(upcoming_games)}")

# 2. Inspect First and Last 5 Completed Games
print("\n--- SAMPLE COMPLETED GAMES (Oldest to Newest) ---")
for g in completed_games[-5:]:
    print(f"[{g['season_year']}] {g['date']} | {g['away_team']} @ {g['home_team']} (Score: {g['away_score']}-{g['home_score']}) | ID: {g['game_id']}")

print("\n--- SAMPLE COMPLETED GAMES (Most Recent) ---")
for g in completed_games[:5]:
    print(f"[{g['season_year']}] {g['date']} | {g['away_team']} @ {g['home_team']} (Score: {g['away_score']}-{g['home_score']}) | ID: {g['game_id']}")

# 3. Check for any non-NBA team names
nba_teams_found = set(g['home_team'] for g in completed_games)
print(f"\nUnique Home Teams Found: {len(nba_teams_found)}")
print("Sample teams:", list(nba_teams_found)[:8])