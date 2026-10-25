"""
scripts/features/player_context.py
NBA Analytics Platform - Consistency, Volatility & Schedule Engine

Analyzes game-by-game variance to compute:
1. Scoring Volatility Index (SVI) & Scoring Floor/Ceiling (10th/90th percentiles)
2. Sub-Zero Game Rate (Disaster games) & Explosion Game Rate
3. Schedule Rest Splits & Back-to-Back Degradation (0 Days vs 2+ Days Rest)
4. Venue Splits (Home vs Road differentials)
"""

import json
import logging
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("PlayerContext")

SEASONS = ["2025-26", "2026-27"]

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def load_json(filepath: str) -> Any:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath: str, data: Any) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, filepath)


def safe_round(val: Optional[float], decimals: int = 2) -> Optional[float]:
    if val is None or math.isnan(val):
        return None
    return round(float(val), decimals)


# ---------------------------------------------------------------------------
# Context Computation
# ---------------------------------------------------------------------------
def process_player_context(season: str) -> Dict[str, Any]:
    player_log_file = os.path.join("data", "raw", "game_logs", f"player_{season}.json")
    team_log_file = os.path.join("data", "raw", "game_logs", f"team_{season}.json")

    if not os.path.exists(player_log_file) or not os.path.exists(team_log_file):
        logger.error(f"Missing raw logs for {season}. Skipping context features.")
        return {}

    df_players = pd.DataFrame(load_json(player_log_file))
    df_teams = pd.DataFrame(load_json(team_log_file))

    if df_players.empty or df_teams.empty:
        return {}

    # 1. Build Team Game Possessions Map: (GAME_ID, TEAM_ID) -> Team Possessions
    # Possessions = 0.96 * (FGA + 0.44 * FTA - OREB + TOV)
    df_teams["team_poss"] = 0.96 * (
        df_teams["FGA"] + 0.44 * df_teams["FTA"] - df_teams["OREB"] + df_teams["TOV"]
    )
    team_game_poss_map = df_teams.set_index(["GAME_ID", "TEAM_ID"])["team_poss"].to_dict()
    team_game_min_map = df_teams.set_index(["GAME_ID", "TEAM_ID"])["MIN"].to_dict()

    # 2. Parse dates and sort chronologically
    df_players["GAME_DATE_DT"] = pd.to_datetime(df_players["GAME_DATE"])
    df_players = df_players.sort_values(by=["PLAYER_ID", "GAME_DATE_DT"]).reset_index(drop=True)

    # 3. Add game-level possession and true shooting metrics
    records = []
    for row in df_players.to_dict(orient="records"):
        gid = row["GAME_ID"]
        tid = row["TEAM_ID"]
        tm_poss = team_game_poss_map.get((gid, tid), 100.0)
        tm_min = team_game_min_map.get((gid, tid), 240.0)

        p_min = float(row.get("MIN", 0) or 0)
        pts = float(row.get("PTS", 0) or 0)
        fga = float(row.get("FGA", 0) or 0)
        fta = float(row.get("FTA", 0) or 0)

        # Player possession share: tm_poss * (Player MIN / (Team MIN / 5))
        tm_min_per_player = tm_min / 5.0
        player_poss = (tm_poss * (p_min / tm_min_per_player)) if tm_min_per_player > 0 else 0.0

        pts_per_100 = (pts / player_poss * 100.0) if player_poss > 0 else 0.0
        ts_denom = 2.0 * (fga + 0.44 * fta)
        ts_pct = (pts / ts_denom) if ts_denom > 0 else None

        # Venue: "vs." indicates Home, "@" indicates Road
        matchup = str(row.get("MATCHUP", ""))
        is_home = 1 if "vs." in matchup else 0

        row["calc_player_poss"] = player_poss
        row["calc_pts_100"] = pts_per_100
        row["calc_ts_pct"] = ts_pct
        row["is_home"] = is_home
        records.append(row)

    df_calc = pd.DataFrame(records)

    # 4. Group by player and compute variance, rest, and venue profiles
    player_profiles = {}
    grouped = df_calc.groupby("PLAYER_ID")

    for pid, group in grouped:
        p_name = group["PLAYER_NAME"].iloc[0]
        team_id = int(group["TEAM_ID"].iloc[-1])
        team_abbrev = str(group["TEAM_ABBREVIATION"].iloc[-1])
        games_played = len(group)

        # Volatility: sample std dev requires >= 2 games
        pts_100_series = group[group["MIN"] >= 10.0]["calc_pts_100"]
        if len(pts_100_series) >= 2:
            svi = float(pts_100_series.std(ddof=1))
            floor_pts_100 = float(np.percentile(pts_100_series, 10))
            ceiling_pts_100 = float(np.percentile(pts_100_series, 90))
        else:
            svi = None
            floor_pts_100 = None
            ceiling_pts_100 = None

        # Sub-zero disaster games: FGA >= 8 and TS% < 50.0%
        fga_qualified = group[group["FGA"] >= 8]
        if not fga_qualified.empty:
            sub_zero_count = len(fga_qualified[fga_qualified["calc_ts_pct"] < 0.50])
            sub_zero_rate = sub_zero_count / len(fga_qualified)
        else:
            sub_zero_count = 0
            sub_zero_rate = None

        # Explosion games: >= 30 PTS/100 and MIN >= 15
        min_qualified = group[group["MIN"] >= 15.0]
        if not min_qualified.empty:
            explosion_count = len(min_qualified[min_qualified["calc_pts_100"] >= 30.0])
            explosion_rate = explosion_count / len(min_qualified)
        else:
            explosion_count = 0
            explosion_rate = None

        # Rest Splits: Days between consecutive games
        group_sorted = group.sort_values("GAME_DATE_DT").copy()
        date_diffs = group_sorted["GAME_DATE_DT"].diff().dt.days

        # Classify rest:
        # First game of season: treated as well-rested (3+ days)
        rest_categories = []
        for d in date_diffs:
            if pd.isna(d) or d >= 3:
                rest_categories.append("well_rested")
            elif d == 1:
                rest_categories.append("b2b_zero_rest")
            else:
                rest_categories.append("one_day_rest")

        group_sorted["rest_category"] = rest_categories

        rest_splits = {}
        for cat in ["b2b_zero_rest", "one_day_rest", "well_rested"]:
            cat_df = group_sorted[group_sorted["rest_category"] == cat]
            if not cat_df.empty:
                cat_pts = cat_df["PTS"].sum()
                cat_fga = cat_df["FGA"].sum()
                cat_fta = cat_df["FTA"].sum()
                cat_ts_denom = 2.0 * (cat_fga + 0.44 * cat_fta)
                cat_ts = (cat_pts / cat_ts_denom) if cat_ts_denom > 0 else None
                cat_pts_100 = cat_df["calc_pts_100"].mean()

                rest_splits[cat] = {
                    "games": len(cat_df),
                    "minutes_per_game": safe_round(cat_df["MIN"].mean(), 1),
                    "true_shooting_pct": safe_round(cat_ts, 4),
                    "pts_per_100": safe_round(cat_pts_100, 1),
                }
            else:
                rest_splits[cat] = None

        # Back-to-Back Degradation Delta (B2B TS% - Well-Rested TS%)
        b2b_ts = rest_splits["b2b_zero_rest"]["true_shooting_pct"] if rest_splits["b2b_zero_rest"] else None
        rested_ts = rest_splits["well_rested"]["true_shooting_pct"] if rest_splits["well_rested"] else None
        b2b_degradation = (b2b_ts - rested_ts) if (b2b_ts is not None and rested_ts is not None) else None

        # Venue Splits (Home vs Away)
        home_df = group[group["is_home"] == 1]
        away_df = group[group["is_home"] == 0]

        def summarize_venue(v_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
            if v_df.empty:
                return None
            v_pts = v_df["PTS"].sum()
            v_fga = v_df["FGA"].sum()
            v_fta = v_df["FTA"].sum()
            v_denom = 2.0 * (v_fga + 0.44 * v_fta)
            v_ts = (v_pts / v_denom) if v_denom > 0 else None
            return {
                "games": len(v_df),
                "minutes_per_game": safe_round(v_df["MIN"].mean(), 1),
                "true_shooting_pct": safe_round(v_ts, 4),
                "pts_per_100": safe_round(v_df["calc_pts_100"].mean(), 1),
            }

        home_summary = summarize_venue(home_df)
        away_summary = summarize_venue(away_df)

        home_ts = home_summary["true_shooting_pct"] if home_summary else None
        away_ts = away_summary["true_shooting_pct"] if away_summary else None
        road_dropoff = (away_ts - home_ts) if (away_ts is not None and home_ts is not None) else None

        player_profiles[str(pid)] = {
            "player_id": int(pid),
            "player_name": p_name,
            "team_id": team_id,
            "team_abbrev": team_abbrev,
            "games_evaluated": games_played,
            "volatility_profile": {
                "scoring_volatility_index_svi": safe_round(svi, 2),
                "scoring_floor_pts_100": safe_round(floor_pts_100, 1),
                "scoring_ceiling_pts_100": safe_round(ceiling_pts_100, 1),
                "sub_zero_game_rate": safe_round(sub_zero_rate, 4),
                "sub_zero_games_count": sub_zero_count,
                "explosion_game_rate": safe_round(explosion_rate, 4),
                "explosion_games_count": explosion_count,
            },
            "schedule_rest_splits": {
                "b2b_degradation_ts": safe_round(b2b_degradation, 4),
                "splits": rest_splits,
            },
            "venue_splits": {
                "road_dropoff_ts": safe_round(road_dropoff, 4),
                "home": home_summary,
                "away": away_summary,
            },
        }

    return player_profiles


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: Player Volatility & Schedule Engine")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Generating Context Features for Season: {season} ---")
        profiles = process_player_context(season)

        payload = {
            "season": season,
            "player_count": len(profiles),
            "players": profiles,
        }

        out_path = os.path.join("data", "processed", "features", f"player_context_{season}.json")
        write_json(out_path, payload)
        logger.info(f"Saved {len(profiles)} player context profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Player context feature generation complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()