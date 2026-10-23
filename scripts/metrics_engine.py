import os
import json
import glob
from datetime import datetime, timezone
import pandas as pd
from raw_scraper import get_current_season

def calculate_player_custom_metrics(df):
    """Computes advanced metrics for a dataframe of player performances."""
    df = df.copy()
    
    # 1. True Shooting %
    denom = 2 * (df['FGA'] + (0.44 * df['FTA']))
    df['TS_PCT'] = ((df['PTS'] / denom.replace(0, 1)) * 100).round(1).fillna(0.0)

    # 2. Floor General Index (Playmaking volume & security)
    df['FGI'] = round(((df['AST'] * 2.2) - (df['TOV'] * 1.8)) + (df['PTS'] * 0.2), 1)

    # 3. Defensive Disruption Rate (Stocks / 36 min)
    min_safe = df['MIN'].replace(0, 1)
    df['DDR'] = round(((df['STL'] + df['BLK']) / min_safe) * 36, 1)

    # 4. Holistic Impact Rating (HIR)
    df['HIR'] = round(
        (df['PTS'] * 1.0) +
        (df['REB'] * 1.2) +
        (df['AST'] * 1.5) +
        (df['STL'] * 2.5) +
        (df['BLK'] * 2.2) -
        (df['TOV'] * 2.0),
        1
    )
    return df

def compile_all():
    _, year_folder = get_current_season()
    raw_dir = os.path.join("data", "raw", year_folder)
    game_files = glob.glob(f"{raw_dir}/*.json")

    if not game_files:
        print(f"No raw game files found in {raw_dir}.")
        return

    print(f"Ingesting and compiling {len(game_files)} games...")

    # Output directories
    proc_dir = os.path.join("data", "processed")
    players_dir = os.path.join(proc_dir, "players")
    teams_dir = os.path.join(proc_dir, "teams")
    games_dir = os.path.join(proc_dir, "games")

    for d in [players_dir, teams_dir, games_dir]:
        os.makedirs(d, exist_ok=True)

    all_player_logs = []
    games_summary = []

    # Parse each raw game
    for file_path in game_files:
        with open(file_path, "r") as f:
            game = json.load(f)

        game_id = game["game_id"]
        game_date = game["game_date"]
        matchup = game["matchup"]
        logs = game["player_logs"]

        if not logs:
            continue

        df_game = pd.DataFrame(logs)
        df_game['MIN'] = pd.to_numeric(df_game['MIN'], errors='coerce').fillna(0)
        df_game = calculate_player_custom_metrics(df_game)

        # Team scores and totals for this game
        team_totals = df_game.groupby('TEAM_ABBREVIATION').agg(
            PTS=('PTS', 'sum'),
            FGA=('FGA', 'sum'),
            FTA=('FTA', 'sum'),
            TOV=('TOV', 'sum'),
            OREB=('OREB', 'sum'),
            DREB=('DREB', 'sum')
        ).reset_index()

        teams_in_game = team_totals['TEAM_ABBREVIATION'].tolist()

        # Save clean box score partition
        game_payload = {
            "game_id": game_id,
            "game_date": game_date,
            "matchup": matchup,
            "teams": team_totals.to_dict(orient="records"),
            "box_score": df_game.fillna(0).to_dict(orient="records")
        }
        with open(os.path.join(games_dir, f"{game_id}.json"), "w") as f:
            json.dump(game_payload, f, indent=2)

        # Build Game Summary entry
        games_summary.append({
            "game_id": game_id,
            "game_date": game_date,
            "matchup": matchup,
            "teams": team_totals.to_dict(orient="records")
        })

        all_player_logs.extend(df_game.to_dict(orient="records"))

    # Global Player Logs Dataframe
    df_all = pd.DataFrame(all_player_logs)
    df_all['GAME_DATE'] = pd.to_datetime(df_all['GAME_DATE'])
    df_all = df_all.sort_values(by=['PLAYER_ID', 'GAME_DATE'], ascending=[True, False])

    print("Building individual player profiles & game logs...")
    players_summary = []

    for (player_id, player_name), p_df in df_all.groupby(['PLAYER_ID', 'PLAYER_NAME']):
        p_df = p_df.sort_values(by='GAME_DATE', ascending=False)
        current_team = p_df['TEAM_ABBREVIATION'].iloc[0]

        # Calculate Season Averages
        gp = len(p_df)
        avg_stats = {
            "PLAYER_ID": int(player_id),
            "PLAYER_NAME": player_name,
            "TEAM_ABBREVIATION": current_team,
            "GP": gp,
            "MIN": round(p_df['MIN'].mean(), 1),
            "PTS": round(p_df['PTS'].mean(), 1),
            "REB": round(p_df['REB'].mean(), 1),
            "AST": round(p_df['AST'].mean(), 1),
            "STL": round(p_df['STL'].mean(), 1),
            "BLK": round(p_df['BLK'].mean(), 1),
            "TOV": round(p_df['TOV'].mean(), 1),
            "TS_PCT": round(p_df['TS_PCT'].mean(), 1),
            "FGI": round(p_df['FGI'].mean(), 1),
            "DDR": round(p_df['DDR'].mean(), 1),
            "HIR": round(p_df['HIR'].mean(), 1),
        }
        players_summary.append(avg_stats)

        # Save individual Player File with full game logs
        player_payload = {
            "profile": avg_stats,
            # Last 5 games rolling averages
            "last_5_avg": {
                "PTS": round(p_df.head(5)['PTS'].mean(), 1),
                "REB": round(p_df.head(5)['REB'].mean(), 1),
                "AST": round(p_df.head(5)['AST'].mean(), 1),
                "HIR": round(p_df.head(5)['HIR'].mean(), 1),
                "TS_PCT": round(p_df.head(5)['TS_PCT'].mean(), 1),
            },
            "game_logs": p_df.fillna(0).to_dict(orient="records")
        }

        with open(os.path.join(players_dir, f"{player_id}.json"), "w") as f:
            json.dump(player_payload, f, indent=2, default=str)

    print("Building team logs and standings...")
    teams_summary = []
    for team_abbr, t_df in df_all.groupby('TEAM_ABBREVIATION'):
        team_games = t_df.groupby('GAME_ID').first().reset_index()
        wins = (team_games['WL'] == 'W').sum()
        losses = (team_games['WL'] == 'L').sum()

        team_stats = {
            "TEAM_ABBREVIATION": team_abbr,
            "GP": len(team_games),
            "W": int(wins),
            "L": int(losses),
            "WIN_PCT": round(wins / max(1, (wins + losses)), 3),
            "ROSTER_COUNT": int(t_df['PLAYER_ID'].nunique())
        }
        teams_summary.append(team_stats)

        team_payload = {
            "profile": team_stats,
            "roster": t_df[['PLAYER_ID', 'PLAYER_NAME', 'HIR', 'PTS', 'MIN']].drop_duplicates(subset=['PLAYER_ID']).to_dict(orient="records")
        }
        with open(os.path.join(teams_dir, f"{team_abbr}.json"), "w") as f:
            json.dump(team_payload, f, indent=2, default=str)

    # Save Master Summaries
    timestamp = datetime.now(timezone.utc).strftime("%b %d, %Y • %H:%M UTC")

    # 1. Summary Players
    with open(os.path.join(proc_dir, "summary_players.json"), "w") as f:
        json.dump({"last_updated": timestamp, "season_year": year_folder, "players": players_summary}, f, indent=2)

    # 2. Summary Teams
    with open(os.path.join(proc_dir, "summary_teams.json"), "w") as f:
        json.dump({"last_updated": timestamp, "teams": teams_summary}, f, indent=2)

    # 3. Summary Games (sorted newest first)
    games_summary.sort(key=lambda x: x["game_date"], reverse=True)
    with open(os.path.join(proc_dir, "summary_games.json"), "w") as f:
        json.dump({"last_updated": timestamp, "games": games_summary}, f, indent=2)

    # Backward compatibility with existing page
    with open(os.path.join(proc_dir, "latest_metrics.json"), "w") as f:
        json.dump({"last_updated": timestamp, "season_year": year_folder, "total_players": len(players_summary), "players": players_summary}, f, indent=2)

    print(f"Compilation Complete!")
    print(f"-> Generated {len(players_summary)} Player Profiles (data/processed/players/)")
    print(f"-> Generated {len(teams_summary)} Team Profiles (data/processed/teams/)")
    print(f"-> Generated {len(games_summary)} Game Box Scores (data/processed/games/)")

if __name__ == "__main__":
    compile_all()