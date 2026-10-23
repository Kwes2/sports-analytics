import os
import json
from datetime import datetime
import pandas as pd
from nba_api.stats.endpoints import leaguegamelog

def get_current_season():
    """
    Determines the NBA season string based on the current date.
    NBA seasons begin in October.
    E.g., October 2026 -> Season '2026-27', Folder Year '2026'
    """
    now = datetime.now()
    year = now.year
    if now.month >= 10:
        season_str = f"{year}-{str(year + 1)[-2:]}"
        year_folder = str(year)
    else:
        season_str = f"{year - 1}-{str(year)[-2:]}"
        year_folder = str(year - 1)
        
    return season_str, year_folder

def fetch_raw_games():
    season, year_folder = get_current_season()
    print(f"Targeting NBA Season: {season} (Directory: data/raw/{year_folder})")

    # Destination directory: data/raw/YYYY
    target_dir = os.path.join("data", "raw", year_folder)
    os.makedirs(target_dir, exist_ok=True)

    print("Fetching player game logs from NBA API...")
    try:
        # Pulls every individual player log for all games played this season
        log_endpoint = leaguegamelog.LeagueGameLog(
            season=season,
            player_or_team_abbreviation='P',
            direction='DESC',
            timeout=60
        )
        df_logs = log_endpoint.get_data_frames()[0]
    except Exception as e:
        print(f"Error connecting to NBA API: {e}")
        return

    if df_logs.empty:
        print(f"No game data available yet for season {season}.")
        return

    # Group records by GAME_ID
    games = df_logs.groupby('GAME_ID')
    new_games_saved = 0

    for game_id, game_df in games:
        file_path = os.path.join(target_dir, f"{game_id}.json")

        # Skip games we have already stored
        if os.path.exists(file_path):
            continue

        game_data = {
            "game_id": str(game_id),
            "season": season,
            "game_date": game_df['GAME_DATE'].iloc[0],
            "matchup": game_df['MATCHUP'].iloc[0],
            "player_logs": game_df.to_dict(orient="records")
        }

        with open(file_path, "w") as f:
            json.dump(game_data, f, indent=2)
            
        new_games_saved += 1

    print(f"Ingestion complete. Saved {new_games_saved} new games to {target_dir}/")

if __name__ == "__main__":
    fetch_raw_games()