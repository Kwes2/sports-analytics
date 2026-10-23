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
        print(f"No raw game files found in {raw_dir}.")
        return

    print(f"Engine parsing {len(game_files)} raw games...")

    all_logs = []
    for file_path in game_files:
        with open(file_path, "r") as f:
            data = json.load(f)
            for log in data["player_logs"]:
                all_logs.append(log)

    df = pd.DataFrame(all_logs)
    df['MIN'] = pd.to_numeric(df['MIN'], errors='coerce').fillna(0)
    df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'])

    # Sort chronologically to calculate rolling form
    df = df.sort_values(by=['PLAYER_ID', 'GAME_DATE'], ascending=[True, True])

    # 1. Base Aggregations
    grouped = df.groupby(['PLAYER_ID', 'PLAYER_NAME', 'TEAM_ABBREVIATION'])
    agg = grouped.agg(
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

    # Minimum threshold: must play in at least 1 game
    agg = agg[agg['GP'] >= 1].copy()

    # Round core stats
    core_cols = ['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FGM', 'FGA', 'FG3M', 'FG3A', 'FTM', 'FTA']
    agg[core_cols] = agg[core_cols].round(1)

    print("Computing advanced proprietary metrics...")

    # METRIC 1: True Shooting % (TS%)
    denom = 2 * (agg['FGA'] + (0.44 * agg['FTA']))
    agg['TS_PCT'] = ((agg['PTS'] / denom.replace(0, 1)) * 100).round(1).fillna(0.0)

    # METRIC 2: Floor General Index (FGI) - Playmaking volume & ball security
    # Rewards high assists with low turnovers relative to touches
    agg['FGI'] = round(((agg['AST'] * 2.2) - (agg['TOV'] * 1.8)) + (agg['PTS'] * 0.2), 1)

    # METRIC 3: Defensive Disruption Rate (Stocks per 36 min)
    min_safe = agg['MIN'].replace(0, 1)
    agg['DDR'] = round(((agg['STL'] + agg['BLK']) / min_safe) * 36, 1)

    # METRIC 4: Composite Holistic Impact Rating (HIR)
    # Scaled metric balancing production, efficiency, and turnovers
    raw_hir = (
        (agg['PTS'] * 1.0) +
        (agg['REB'] * 1.2) +
        (agg['AST'] * 1.5) +
        (agg['STL'] * 2.5) +
        (agg['BLK'] * 2.2) -
        (agg['TOV'] * 2.0)
    )
    agg['HIR'] = round(raw_hir, 1)

    # Clean residual infs/nans
    agg = agg.fillna(0)

    # Save to processed directory
    output_path = os.path.join("data", "processed", "latest_metrics.json")
    output_payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%b %d, %Y • %H:%M UTC"),
        "season_year": year_folder,
        "total_players": len(agg),
        "players": agg.to_dict(orient="records")
    }

    with open(output_path, "w") as f:
        json.dump(output_payload, f, indent=2)

    print(f"Processed {len(agg)} players with new metric suite -> {output_path}")

if __name__ == "__main__":
    compute_metrics()