"""
scripts/features/game_flow.py
NBA Analytics Platform - Game Flow, Momentum & Rest Advantage Engine

Computes:
1. Q1 Jumpstart Rating (Q1 eFG% vs Full-Game eFG%)
2. Q4 Production Rating (Q4 eFG% vs Q1-Q3 eFG%)
3. Clutch Execution Gap (Clutch eFG% vs Non-Clutch eFG%)
4. Schedule Rest Advantage Differential (NetRTG when holding rest advantage vs deficit)
"""

import glob
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("GameFlow")

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


def safe_div(num: float, den: float) -> Optional[float]:
    return (num / den) if den > 0 else None


# ---------------------------------------------------------------------------
# Rest Advantage Engine (Team Level)
# ---------------------------------------------------------------------------
def compute_team_rest_advantage(season: str) -> Dict[int, Dict[str, Any]]:
    team_log_file = os.path.join("data", "raw", "game_logs", f"team_{season}.json")
    if not os.path.exists(team_log_file):
        return {}

    df = pd.DataFrame(load_json(team_log_file))
    if df.empty:
        return {}

    df["GAME_DATE_DT"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values(by=["TEAM_ID", "GAME_DATE_DT"]).reset_index(drop=True)

    # 1. Compute Rest Days between consecutive games
    df["prev_game_date"] = df.groupby("TEAM_ID")["GAME_DATE_DT"].shift(1)
    df["rest_days"] = (df["GAME_DATE_DT"] - df["prev_game_date"]).dt.days - 1
    # First game or long gap: cap at 3+ days
    df["rest_days"] = df["rest_days"].fillna(3).clip(lower=0, upper=5)

    # 2. Pair opposing teams to compare rest days
    merged = pd.merge(df, df, on="GAME_ID", suffixes=("", "_OPP"))
    paired = merged[merged["TEAM_ID"] != merged["TEAM_ID_OPP"]].copy()

    # Calculate possessions per game
    paired["poss"] = 0.96 * (paired["FGA"] + 0.44 * paired["FTA"] - paired["OREB"] + paired["TOV"])
    paired["net_pts"] = paired["PTS"] - paired["PTS_OPP"]

    # 3. Aggregate performance by Rest Condition:
    # Advantage: my rest > opp rest
    # Deficit: my rest < opp rest
    # Even: my rest == opp rest
    team_rest_profiles = {}
    for tid, group in paired.groupby("TEAM_ID"):
        adv_df = group[group["rest_days"] > group["rest_days_OPP"]]
        def_df = group[group["rest_days"] < group["rest_days_OPP"]]
        even_df = group[group["rest_days"] == group["rest_days_OPP"]]

        def get_net_rtg(subset: pd.DataFrame) -> Optional[float]:
            tot_poss = subset["poss"].sum()
            tot_net = subset["net_pts"].sum()
            return round((tot_net / tot_poss) * 100.0, 2) if tot_poss > 0 else None

        net_adv = get_net_rtg(adv_df)
        net_def = get_net_rtg(def_df)
        net_even = get_net_rtg(even_df)

        delta_rest = (net_adv - net_def) if (net_adv is not None and net_def is not None) else None

        team_rest_profiles[int(tid)] = {
            "team_id": int(tid),
            "rest_advantage_games": len(adv_df),
            "rest_deficit_games": len(def_df),
            "even_rest_games": len(even_df),
            "net_rtg_with_rest_advantage": net_adv,
            "net_rtg_with_rest_deficit": net_def,
            "net_rtg_even_rest": net_even,
            "rest_advantage_differential": round(delta_rest, 2) if delta_rest is not None else None,
        }

    return team_rest_profiles


# ---------------------------------------------------------------------------
# Quarter & Clutch Engine (Shot-Level)
# ---------------------------------------------------------------------------
def compute_shot_game_flow(season: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    shot_files = glob.glob(os.path.join("data", "raw", "shots", season, "*.json"))
    if not shot_files:
        return {}, {}

    # Aggregator structures
    # pid -> { name, team_id, q1: {fga, pts}, q4: {fga, pts}, q1_3: {fga, pts}, clutch: {fga, pts}, non_clutch: {fga, pts}, total: {fga, pts} }
    def new_profile():
        return {
            "name": "",
            "team_id": 0,
            "q1": {"fga": 0, "pts": 0},
            "q4": {"fga": 0, "pts": 0},
            "q1_3": {"fga": 0, "pts": 0},
            "clutch": {"fga": 0, "pts": 0},
            "non_clutch": {"fga": 0, "pts": 0},
            "total": {"fga": 0, "pts": 0},
        }

    player_stats: Dict[int, Dict[str, Any]] = defaultdict(new_profile)
    team_stats: Dict[int, Dict[str, Any]] = defaultdict(new_profile)

    for filepath in shot_files:
        shots = load_json(filepath)
        for s in shots:
            pid = s.get("PLAYER_ID")
            tid = int(s.get("TEAM_ID", 0))
            pname = s.get("PLAYER_NAME", "Unknown")

            period = int(s.get("PERIOD", 1))
            min_rem = int(s.get("MINUTES_REMAINING", 0))
            sec_rem = int(s.get("SECONDS_REMAINING", 0))
            is_made = int(s.get("SHOT_MADE_FLAG", 0))
            is_3pt = 1 if "3PT" in str(s.get("SHOT_TYPE", "")) else 0
            pts = (3 if is_3pt else 2) if is_made else 0

            is_clutch = (period >= 4) and ((min_rem * 60 + sec_rem) <= 300)

            for entity, eid, name in [(player_stats, pid, pname), (team_stats, tid, f"Team {tid}")]:
                entity[eid]["name"] = name
                entity[eid]["team_id"] = tid
                entity[eid]["total"]["fga"] += 1
                entity[eid]["total"]["pts"] += pts

                # Quarter logic
                if period == 1:
                    entity[eid]["q1"]["fga"] += 1
                    entity[eid]["q1"]["pts"] += pts
                    entity[eid]["q1_3"]["fga"] += 1
                    entity[eid]["q1_3"]["pts"] += pts
                elif period in [2, 3]:
                    entity[eid]["q1_3"]["fga"] += 1
                    entity[eid]["q1_3"]["pts"] += pts
                elif period >= 4:
                    entity[eid]["q4"]["fga"] += 1
                    entity[eid]["q4"]["pts"] += pts

                # Clutch logic
                if is_clutch:
                    entity[eid]["clutch"]["fga"] += 1
                    entity[eid]["clutch"]["pts"] += pts
                else:
                    entity[eid]["non_clutch"]["fga"] += 1
                    entity[eid]["non_clutch"]["pts"] += pts

    def compile_flow(stats_map: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
        results = {}
        for eid, data in stats_map.items():
            tot_fga = data["total"]["fga"]
            if tot_fga == 0:
                continue

            overall_efg = data["total"]["pts"] / (2.0 * tot_fga)

            # Q1 Jumpstart
            q1_fga = data["q1"]["fga"]
            q1_efg = (data["q1"]["pts"] / (2.0 * q1_fga)) if q1_fga > 0 else None
            q1_jumpstart = (q1_efg - overall_efg) if q1_efg is not None else None

            # Q4 Production
            q4_fga = data["q4"]["fga"]
            q1_3_fga = data["q1_3"]["fga"]
            q4_efg = (data["q4"]["pts"] / (2.0 * q4_fga)) if q4_fga > 0 else None
            q1_3_efg = (data["q1_3"]["pts"] / (2.0 * q1_3_fga)) if q1_3_fga > 0 else None
            q4_production = (q4_efg - q1_3_efg) if (q4_efg is not None and q1_3_efg is not None) else None

            # Clutch Gap
            clutch_fga = data["clutch"]["fga"]
            non_clutch_fga = data["non_clutch"]["fga"]
            clutch_efg = (data["clutch"]["pts"] / (2.0 * clutch_fga)) if clutch_fga > 0 else None
            non_clutch_efg = (data["non_clutch"]["pts"] / (2.0 * non_clutch_fga)) if non_clutch_fga > 0 else None
            clutch_gap = (clutch_efg - non_clutch_efg) if (clutch_efg is not None and non_clutch_efg is not None) else None

            results[str(eid)] = {
                "entity_id": eid,
                "name": data["name"],
                "team_id": data["team_id"],
                "quarter_splits": {
                    "q1_fga": q1_fga,
                    "q1_efg": round(q1_efg, 4) if q1_efg is not None else None,
                    "q1_jumpstart_rating": round(q1_jumpstart, 4) if q1_jumpstart is not None else None,
                    "q4_fga": q4_fga,
                    "q4_efg": round(q4_efg, 4) if q4_efg is not None else None,
                    "q4_production_rating": round(q4_production, 4) if q4_production is not None else None,
                },
                "clutch_execution": {
                    "clutch_fga": clutch_fga,
                    "clutch_efg": round(clutch_efg, 4) if clutch_efg is not None else None,
                    "non_clutch_efg": round(non_clutch_efg, 4) if non_clutch_efg is not None else None,
                    "clutch_execution_gap": round(clutch_gap, 4) if clutch_gap is not None else None,
                },
            }
        return results

    return compile_flow(player_stats), compile_flow(team_stats)


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: Game Flow, Momentum & Rest Engine")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Processing Game Flow for Season: {season} ---")

        # 1. Team Rest Advantage Splits
        team_rest = compute_team_rest_advantage(season)

        # 2. Quarter and Clutch Flow
        player_flow, team_flow = compute_shot_game_flow(season)

        # Merge Team Flow with Rest Data
        for tid_str, t_obj in team_flow.items():
            tid = int(tid_str)
            t_obj["rest_advantage_profile"] = team_rest.get(tid, {})

        payload = {
            "season": season,
            "player_count": len(player_flow),
            "team_count": len(team_flow),
            "players": player_flow,
            "teams": team_flow,
        }

        out_path = os.path.join("data", "processed", "features", f"game_flow_{season}.json")
        write_json(out_path, payload)
        logger.info(f"Saved {len(player_flow)} player & {len(team_flow)} team game flow profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Game flow feature generation complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()