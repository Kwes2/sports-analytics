import os
import json
import glob
from datetime import datetime, timezone
import pandas as pd
from raw_scraper import get_current_season

def compute_metrics():
    _, year_folder = get_current_season()
    raw_dir = os.path.join("data", "raw", year_folder)
    game_files = glob.glob(f"{raw_dir}/*.json")

    if not game_files:
        print(f"No raw game files found in {raw_dir}. Run raw_scraper.py first.")
        return

    print(f"Processing {len(game_files)} raw game files from {raw_dir}...")

    all_logs = []
    for file_path in game_files:
        with open(file_path, "r") as f:
            data = json.load(f)
            all_logs.extend(data["player_logs"])

    df = pd.DataFrame(all_logs)

    # Convert MIN to numeric if not already (handles cases where minutes are strings or ints)
    df['MIN'] = pd.to_numeric(df['MIN'], errors='coerce').fillna(0)

    # Group by player to get per-game averages
    grouped = df.groupby(['PLAYER_ID', 'PLAYER_NAME', 'TEAM_ABBREVIATION'])

    agg_df = grouped.agg(
        GP=('GAME_ID', 'nunique'),
        MIN=('MIN', 'mean'),
        PTS=('PTS', 'mean'),
        REB=('REB', 'mean'),
        AST=('AST', 'mean'),
        STL=('STL', 'mean'),
        BLK=('BLK', 'mean'),
        TOV=('TOV', 'mean'),
        FGM=('FGM', 'mean'),
        FGA=('FGA', 'mean'),
        FG3M=('FG3M', 'mean'),
        FG3A=('FG3A', 'mean'),
        FTM=('FTM', 'mean'),
        FTA=('FTA', 'mean')
    ).reset_index()

    # Dynamic GP filter: Only filter by >= 3 if the season has enough games
    # Early season (few games) keeps everyone with at least 1 game
    min_games = 1 if len(game_files) < 30 else 3
    agg_df = agg_df[agg_df['GP'] >= min_games].copy()

    # Round stats to 1 decimal place
    stat_cols = ['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FGM', 'FGA', 'FG3M', 'FG3A', 'FTM', 'FTA']
    agg_df[stat_cols] = agg_df[stat_cols].round(1)

    print("Calculating custom metrics...")

    # Metric 1: True Shooting % (True Formula)
    # TS% = PTS / (2 * (FGA + 0.44 * FTA))
    denom = 2 * (agg_df['FGA'] + (0.44 * agg_df['FTA']))
    agg_df['TS_PCT'] = (agg_df['PTS'] / denom.replace(0, 1)) * 100
    agg_df['TS_PCT'] = agg_df['TS_PCT'].round(1).fillna(0.0)

    # Metric 2: Assist-to-Turnover Ratio
    agg_df['AST_TOV'] = round(agg_df['AST'] / agg_df['TOV'].replace(0, 0.5), 2)

    # Metric 3: Custom Impact Score formula
    agg_df['CUSTOM_IMPACT'] = round(
        agg_df['PTS'] + 
        (1.2 * agg_df['REB']) + 
        (1.5 * agg_df['AST']) + 
        (2.0 * agg_df['STL']) + 
        (2.0 * agg_df['BLK']) - 
        (1.5 * agg_df['TOV']), 
        1
    )

    # Replace any residual NaN/inf with None/0 for valid JSON output
    agg_df = agg_df.fillna(0)

    # Save to processed folder
    os.makedirs(os.path.join("data", "processed"), exist_ok=True)
    output_path = os.path.join("data", "processed", "latest_metrics.json")

    output_payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "season_year": year_folder,
        "total_players": len(agg_df),
        "players": agg_df.to_dict(orient="records")
    }

    with open(output_path, "w") as f:
        json.dump(output_payload, f, indent=2)

    print(f"Metrics engine finished. Processed {len(agg_df)} players -> {output_path}")

if __name__ == "__main__":
    compute_metrics()