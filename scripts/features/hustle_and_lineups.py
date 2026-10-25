"""
scripts/features/hustle_and_lineups.py
NBA Analytics Platform - Hustle Tracking & 5-Man Lineup Synergy Engine

Computes:
1. Player Deflections, Screen Assists, Charges & Box-Outs per 100 possessions
2. Team 5-Man Lineup Ratings (Dominant 5 vs Leaky 5)
3. Team Hustle Aggregates (Deflections & Screen Points per game)
"""

import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("HustleAndLineups")

SEASONS = ["2026-27", "2025-26"]


def load_json(filepath: str) -> Any:
    if not os.path.exists(filepath):
        return []
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
# Core Processing
# ---------------------------------------------------------------------------
def process_hustle_and_lineups(season: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    p_hustle_raw = load_json(os.path.join("data", "raw", "hustle", f"player_{season}.json"))
    t_hustle_raw = load_json(os.path.join("data", "raw", "hustle", f"team_{season}.json"))
    lineups_raw = load_json(os.path.join("data", "raw", "lineups", f"lineups_5man_{season}.json"))
    team_logs_raw = load_json(os.path.join("data", "raw", "game_logs", f"team_{season}.json"))

    if not p_hustle_raw or not team_logs_raw:
        logger.warning(f"Missing hustle data for {season}.")
        return {}, {}

    # 1. Team Possessions Lookup for Normalization
    df_teams = pd.DataFrame(team_logs_raw)
    team_agg = df_teams.groupby("TEAM_ID").agg(
        games=("GAME_ID", "nunique"),
        min=("MIN", "sum"),
        fga=("FGA", "sum"),
        fta=("FTA", "sum"),
        oreb=("OREB", "sum"),
        tov=("TOV", "sum"),
    ).reset_index()
    team_agg["possessions"] = 0.96 * (team_agg["fga"] + 0.44 * team_agg["fta"] - team_agg["oreb"] + team_agg["tov"])
    team_map = team_agg.set_index("TEAM_ID").to_dict(orient="index")

    # 2. Player Hustle Rates per 100 Possessions
    player_results = {}
    for row in p_hustle_raw:
        pid = row.get("PLAYER_ID")
        tid = row.get("TEAM_ID")
        pname = row.get("PLAYER_NAME", "Unknown")
        minutes = float(row.get("MIN", 0) or 0)

        tm = team_map.get(tid)
        if not tm or minutes == 0 or not pid:
            continue

        pid = int(pid)
        tm_min_per_player = tm["min"] / 5.0
        player_poss = (tm["possessions"] * (minutes / tm_min_per_player)) if tm_min_per_player > 0 else 0.0
        poss_factor = (100.0 / player_poss) if player_poss > 0 else 0.0

        deflections = float(row.get("DEFLECTIONS", 0) or 0)
        screen_ast = float(row.get("SCREEN_ASSISTS", 0) or 0)
        screen_ast_pts = float(row.get("SCREEN_AST_PTS", 0) or 0)
        charges = float(row.get("CHARGES_DRAWN", 0) or 0)
        loose_balls = float(row.get("LOOSE_BALLS_RECOVERED", 0) or 0)
        box_outs = float(row.get("BOX_OUTS", 0) or 0)

        player_results[str(pid)] = {
            "player_id": pid,
            "player_name": pname,
            "team_id": tid,
            "hustle_stats": {
                "minutes_evaluated": round(minutes, 1),
                "deflections_total": int(deflections),
                "deflections_per_100": round(deflections * poss_factor, 1),
                "screen_assists_total": int(screen_ast),
                "screen_assists_per_100": round(screen_ast * poss_factor, 1),
                "screen_assist_points_total": int(screen_ast_pts),
                "screen_assist_pts_per_100": round(screen_ast_pts * poss_factor, 1),
                "charges_drawn_total": int(charges),
                "charges_drawn_per_100": round(charges * poss_factor, 2),
                "loose_balls_recovered_per_100": round(loose_balls * poss_factor, 1),
                "box_outs_per_100": round(box_outs * poss_factor, 1),
            },
        }

    # 3. Team Hustle & Lineups
    team_results = {}
    team_hustle_lookup = {int(r["TEAM_ID"]): r for r in t_hustle_raw if r.get("TEAM_ID")}

    # Group lineups by team
    df_lineups = pd.DataFrame(lineups_raw) if lineups_raw else pd.DataFrame()

    for tid, tm in team_map.items():
        games = tm["games"]
        t_hustle = team_hustle_lookup.get(tid, {})

        def_tot = float(t_hustle.get("DEFLECTIONS", 0) or 0)
        screen_pts_tot = float(t_hustle.get("SCREEN_AST_PTS", 0) or 0)
        charges_tot = float(t_hustle.get("CHARGES_DRAWN", 0) or 0)

        # 5-Man Lineup Processing
        best_lineup = None
        leakiest_lineup = None
        top_lineups_list = []

        if not df_lineups.empty and "TEAM_ID" in df_lineups.columns:
            tm_lineups = df_lineups[df_lineups["TEAM_ID"] == tid].copy()
            if not tm_lineups.empty and "MIN" in tm_lineups.columns:
                # Filter lineups with >= 5 minutes (or top 5 by minutes)
                qualified_lineups = tm_lineups.sort_values(by="MIN", ascending=False).head(5)

                for _, l_row in qualified_lineups.iterrows():
                    l_min = float(l_row.get("MIN", 0) or 0)
                    l_pts = float(l_row.get("PTS", 0) or 0)
                    l_plus_minus = float(l_row.get("PLUS_MINUS", 0) or 0)
                    # Approximate net rating
                    l_net = round((l_plus_minus / l_min) * 48.0, 1) if l_min > 0 else 0.0

                    top_lineups_list.append({
                        "lineup_name": str(l_row.get("GROUP_NAME", "Lineup")),
                        "minutes": round(l_min, 1),
                        "plus_minus": int(l_plus_minus),
                        "net_rating_per_48": l_net,
                    })

                if top_lineups_list:
                    sorted_by_net = sorted(top_lineups_list, key=lambda x: x["net_rating_per_48"], reverse=True)
                    best_lineup = sorted_by_net[0]
                    leakiest_lineup = sorted_by_net[-1]

        team_results[str(tid)] = {
            "team_id": tid,
            "games_evaluated": games,
            "team_hustle_per_game": {
                "deflections_per_game": round(def_tot / games, 1) if games > 0 else 0.0,
                "screen_assist_pts_per_game": round(screen_pts_tot / games, 1) if games > 0 else 0.0,
                "charges_drawn_per_game": round(charges_tot / games, 2) if games > 0 else 0.0,
            },
            "lineup_rotation_profiles": {
                "top_5man_lineups_evaluated": len(top_lineups_list),
                "best_net_lineup": best_lineup,
                "leakiest_net_lineup": leakiest_lineup,
                "primary_lineups": top_lineups_list[:3],
            },
        }

    return player_results, team_results


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: Hustle Tracking & 5-Man Lineups")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Processing Hustle & Lineups for Season: {season} ---")
        players, teams = process_hustle_and_lineups(season)

        payload = {
            "season": season,
            "player_count": len(players),
            "team_count": len(teams),
            "players": players,
            "teams": teams,
        }

        out_path = os.path.join("data", "processed", "features", f"hustle_and_lineups_{season}.json")
        write_json(out_path, payload)
        logger.info(f"Saved {len(players)} player & {len(teams)} team profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Hustle & lineup modeling complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()