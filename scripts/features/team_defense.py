"""
scripts/features/team_defense.py
NBA Analytics Platform - 2-Way Team Defense & Opponent Science Engine

Cross-pairs matchup game logs and shot charts to compute:
1. True Defensive Rating (DRTG) & Net Rating (NetRTG)
2. Complete Opponent Four Factors
3. Defensive Shot Quality Allowed (xEFGA) & Defensive Finishing Delta
4. Possession Ledger Margin (Extra Possessions Won/Lost)
5. Scheme Modernization (MoreyBall Index)
"""

import glob
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("TeamDefense")

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


# ---------------------------------------------------------------------------
# Inverted Matchup Engine
# ---------------------------------------------------------------------------
def build_paired_matchups(season: str) -> pd.DataFrame:
    """
    Pairs each team's game log row with their exact opponent's row
    by joining on GAME_ID.
    """
    team_log_file = os.path.join("data", "raw", "game_logs", f"team_{season}.json")
    if not os.path.exists(team_log_file):
        logger.error(f"Missing team log file: {team_log_file}")
        return pd.DataFrame()

    df = pd.DataFrame(load_json(team_log_file))
    if df.empty:
        return pd.DataFrame()

    # Self-join on GAME_ID where TEAM_ID differs
    merged = pd.merge(
        df,
        df,
        on="GAME_ID",
        suffixes=("", "_OPP"),
    )
    # Filter out self-pairs (ensure Team != Opponent)
    paired = merged[merged["TEAM_ID"] != merged["TEAM_ID_OPP"]].copy()

    logger.info(f"Paired {len(paired)} team-game matchups for season {season}.")
    return paired


# ---------------------------------------------------------------------------
# Defensive Shot Chart Suppression (xEFGA)
# ---------------------------------------------------------------------------
def compute_defensive_shot_suppression(
    season: str,
    game_to_defenders_map: Dict[str, Dict[int, int]],
    zone_xpps_map: Dict[str, float],
) -> Dict[int, Dict[str, Any]]:
    """
    Determines every shot taken AGAINST each defense, aggregating
    opponent shot quality allowed (xEFGA) and defensive finishing delta.
    game_to_defenders_map: GAME_ID -> {offense_team_id: defense_team_id}
    """
    shot_files = glob.glob(os.path.join("data", "raw", "shots", season, "*.json"))
    logger.info(f"Mapping opponent shots across {len(shot_files)} files for {season}...")

    # def_team_id -> stats
    def_shots = defaultdict(
        lambda: {"opp_fga": 0, "opp_fgm": 0, "opp_pts": 0, "opp_xpts": 0.0, "zones": defaultdict(int)}
    )

    for filepath in shot_files:
        shots = load_json(filepath)
        for shot in shots:
            gid = str(shot.get("GAME_ID"))
            off_tid = int(shot.get("TEAM_ID", 0))

            # Identify defending team ID
            def_tid = game_to_defenders_map.get(gid, {}).get(off_tid)
            if not def_tid:
                continue

            is_made = int(shot.get("SHOT_MADE_FLAG", 0))
            shot_type = str(shot.get("SHOT_TYPE", ""))
            zone_basic = shot.get("SHOT_ZONE_BASIC", "Mid-Range")

            is_3pt = 1 if "3PT" in shot_type else 0
            shot_pts = (3 if is_3pt else 2) if is_made else 0
            expected_pts = zone_xpps_map.get(zone_basic, 1.0)

            def_shots[def_tid]["opp_fga"] += 1
            def_shots[def_tid]["opp_fgm"] += is_made
            def_shots[def_tid]["opp_pts"] += shot_pts
            def_shots[def_tid]["opp_xpts"] += expected_pts
            def_shots[def_tid]["zones"][zone_basic] += 1

    compiled_def_shots = {}
    for tid, data in def_shots.items():
        fga = data["opp_fga"]
        if fga == 0:
            continue
        actual_opp_efg = data["opp_pts"] / (2.0 * fga)
        xefga = data["opp_xpts"] / (2.0 * fga)

        compiled_def_shots[tid] = {
            "opp_shots_defended": fga,
            "actual_opp_efg": round(actual_opp_efg, 4),
            "defensive_shot_quality_allowed_xefga": round(xefga, 4),
            "defensive_finishing_delta": round(actual_opp_efg - xefga, 4),
            "zone_distribution_allowed": {
                k: round(v / fga, 4) for k, v in data["zones"].items()
            },
        }

    return compiled_def_shots


# ---------------------------------------------------------------------------
# Team 2-Way Metrics Engine
# ---------------------------------------------------------------------------
def compute_team_defense_features(
    season: str, zone_xpps_map: Dict[str, float]
) -> Dict[str, Any]:
    paired_df = build_paired_matchups(season)
    if paired_df.empty:
        return {}

    # Build lookup map: GAME_ID -> { offense_team_id: defense_team_id }
    game_defender_map = defaultdict(dict)
    for _, row in paired_df.iterrows():
        gid = str(row["GAME_ID"])
        game_defender_map[gid][int(row["TEAM_ID"])] = int(row["TEAM_ID_OPP"])

    # Aggregate Team totals (Offensive + Opponent Defensive)
    team_agg = paired_df.groupby("TEAM_ID").agg(
        team_name=("TEAM_NAME", "first"),
        team_abbrev=("TEAM_ABBREVIATION", "first"),
        games=("GAME_ID", "nunique"),
        min=("MIN", "sum"),
        # Offense
        pts=("PTS", "sum"),
        fga=("FGA", "sum"),
        fgm=("FGM", "sum"),
        fg3a=("FG3A", "sum"),
        fg3m=("FG3M", "sum"),
        fta=("FTA", "sum"),
        ftm=("FTM", "sum"),
        oreb=("OREB", "sum"),
        dreb=("DREB", "sum"),
        reb=("REB", "sum"),
        ast=("AST", "sum"),
        stl=("STL", "sum"),
        blk=("BLK", "sum"),
        tov=("TOV", "sum"),
        # Defense (Opponent stats)
        opp_pts=("PTS_OPP", "sum"),
        opp_fga=("FGA_OPP", "sum"),
        opp_fgm=("FGM_OPP", "sum"),
        opp_fg3a=("FG3A_OPP", "sum"),
        opp_fg3m=("FG3M_OPP", "sum"),
        opp_fta=("FTA_OPP", "sum"),
        opp_ftm=("FTM_OPP", "sum"),
        opp_oreb=("OREB_OPP", "sum"),
        opp_dreb=("DREB_OPP", "sum"),
        opp_reb=("REB_OPP", "sum"),
        opp_ast=("AST_OPP", "sum"),
        opp_stl=("STL_OPP", "sum"),
        opp_blk=("BLK_OPP", "sum"),
        opp_tov=("TOV_OPP", "sum"),
    ).reset_index()

    # Calculate spatial defensive suppression (xEFGA)
    def_shot_suppression = compute_defensive_shot_suppression(
        season, game_defender_map, zone_xpps_map
    )

    team_results = {}
    for _, row in team_agg.iterrows():
        tid = int(row["TEAM_ID"])
        games = int(row["games"])
        minutes = float(row["min"])

        # 1. Oliver Possessions
        # Off Possessions: 0.96 * (FGA + 0.44 * FTA - OREB + TOV)
        off_poss = 0.96 * (row["fga"] + 0.44 * row["fta"] - row["oreb"] + row["tov"])
        # Def Possessions: 0.96 * (OPP_FGA + 0.44 * OPP_FTA - OPP_OREB + OPP_TOV)
        def_poss = 0.96 * (row["opp_fga"] + 0.44 * row["opp_fta"] - row["opp_oreb"] + row["opp_tov"])

        ortg = (row["pts"] / off_poss) * 100.0 if off_poss > 0 else 0.0
        drtg = (row["opp_pts"] / def_poss) * 100.0 if def_poss > 0 else 0.0
        net_rtg = ortg - drtg
        pace = (off_poss / (minutes / 5.0)) * 48.0 if minutes > 0 else 0.0

        # 2. Defensive Four Factors
        opp_efg = (row["opp_fgm"] + 0.5 * row["opp_fg3m"]) / row["opp_fga"] if row["opp_fga"] > 0 else 0.0
        opp_tov_denom = row["opp_fga"] + 0.44 * row["opp_fta"] + row["opp_tov"]
        dtov_pct = (row["opp_tov"] / opp_tov_denom) if opp_tov_denom > 0 else 0.0
        dreb_pct = (row["dreb"] / (row["dreb"] + row["opp_oreb"])) if (row["dreb"] + row["opp_oreb"]) > 0 else 0.0
        opp_ft_rate = (row["opp_fta"] / row["opp_fga"]) if row["opp_fga"] > 0 else 0.0

        # 3. Possession Ledger Margin
        # Extra possessions won = (Team OREB - Team TOV) - (Opp OREB - Opp TOV)
        net_extra_poss = (row["oreb"] - row["tov"]) - (row["opp_oreb"] - row["opp_tov"])
        poss_margin_per_game = net_extra_poss / games if games > 0 else 0.0

        # 4. MoreyBall Index
        # % of FGA coming from 3-pointers or at the rim
        # Team 3PA + Estimated Rim FGA (from shot features if available, otherwise 3PA + FT load)
        three_pt_rate = row["fg3a"] / row["fga"] if row["fga"] > 0 else 0.0

        # Spatial shot suppression data
        suppression_data = def_shot_suppression.get(tid, {})

        team_results[str(tid)] = {
            "team_id": tid,
            "team_name": row["team_name"],
            "team_abbrev": row["team_abbrev"],
            "games_played": games,
            "pace": round(pace, 2),
            "ratings": {
                "offensive_rating": round(ortg, 2),
                "defensive_rating": round(drtg, 2),
                "net_rating": round(net_rtg, 2),
            },
            "defensive_four_factors": {
                "opp_effective_fg_pct": round(opp_efg, 4),
                "defensive_tov_pct_forced": round(dtov_pct, 4),
                "defensive_rebound_pct": round(dreb_pct, 4),
                "opp_free_throw_rate": round(opp_ft_rate, 4),
            },
            "possession_ledger": {
                "total_extra_possessions": round(net_extra_poss, 1),
                "possession_margin_per_game": round(poss_margin_per_game, 2),
            },
            "defensive_shot_quality": {
                "opp_shots_defended": suppression_data.get("opp_shots_defended", 0),
                "opp_shot_quality_allowed_xefga": suppression_data.get("defensive_shot_quality_allowed_xefga"),
                "actual_opp_efg": suppression_data.get("actual_opp_efg"),
                "defensive_finishing_delta": suppression_data.get("defensive_finishing_delta"),
                "zone_distribution_allowed": suppression_data.get("zone_distribution_allowed", {}),
            },
            "scheme_profile": {
                "three_point_attempt_rate": round(three_pt_rate, 4),
                "free_throw_attempt_rate": round(row["fta"] / row["fga"] if row["fga"] > 0 else 0.0, 4),
            },
        }

    return team_results


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: Team Defense & Opponent Engine")
    logger.info("==================================================")

    baseline_path = os.path.join("data", "processed", "league_baselines.json")
    if not os.path.exists(baseline_path):
        raise FileNotFoundError(
            f"Baselines file not found at {baseline_path}. Run build_baselines.py first."
        )

    baselines = load_json(baseline_path)
    zones = baselines.get("spatial_shooting_benchmarks", {}).get("zones", {})
    zone_xpps_map = {z_name: meta["xpps"] for z_name, meta in zones.items()}

    for season in SEASONS:
        logger.info(f"--- Generating 2-Way Features for Season: {season} ---")
        team_features = compute_team_defense_features(season, zone_xpps_map)

        payload = {
            "season": season,
            "team_count": len(team_features),
            "teams": team_features,
        }

        out_path = os.path.join("data", "processed", "features", f"team_defense_{season}.json")
        write_json(out_path, payload)
        logger.info(f"Saved {len(team_features)} 2-way team defense profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Team defense feature generation complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()