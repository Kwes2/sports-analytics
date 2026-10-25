"""
scripts/features/playmaking_and_roles.py
NBA Analytics Platform - Playmaking Centrality, Role & Floor Share Engine

Computes:
1. Team Helicentrism Index, Assist Gini Coefficient & Playmaking Depth
2. Player True Oliver Rates (AST%, ORB%, DREB%)
3. Stock Rate (STL100 + BLK100) & Foul Drawing Premium (FTA/PF)
4. Pass-to-Shot Creation Leverage (AST/FGA)
5. Positional Mapping (Guard, Forward, Center)
"""

import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("PlaymakingAndRoles")

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


def calculate_gini(values: List[float]) -> float:
    """
    Computes Gini coefficient for a non-negative array.
    0.0 represents perfect equality, 1.0 represents total inequality.
    """
    arr = np.array(values, dtype=np.float64)
    arr = arr[arr >= 0]
    if len(arr) == 0 or np.sum(arr) == 0:
        return 0.0

    arr = np.sort(arr)
    n = len(arr)
    index = np.arange(1, n + 1)
    return float((2.0 * np.sum(index * arr) - (n + 1) * np.sum(arr)) / (n * np.sum(arr)))


def normalize_position(pos_str: Optional[str]) -> str:
    """Standardizes positions into Guard (G), Forward (F), or Center (C)."""
    if not pos_str or not isinstance(pos_str, str):
        return "F"  # neutral fallback
    pos_clean = pos_str.strip().upper()
    if pos_clean.startswith("G"):
        return "G"
    elif pos_clean.startswith("C"):
        return "C"
    elif pos_clean.startswith("F"):
        return "F"
    return "F"


# ---------------------------------------------------------------------------
# Core Processing
# ---------------------------------------------------------------------------
def process_playmaking_and_roles(season: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    player_log_file = os.path.join("data", "raw", "game_logs", f"player_{season}.json")
    team_log_file = os.path.join("data", "raw", "game_logs", f"team_{season}.json")
    bio_file = os.path.join("data", "raw", "player_bios", f"{season}.json")

    if not os.path.exists(player_log_file) or not os.path.exists(team_log_file):
        logger.error(f"Missing logs for {season}.")
        return {}, {}

    df_players = pd.DataFrame(load_json(player_log_file))
    df_teams = pd.DataFrame(load_json(team_log_file))

    # 1. Load Positions from Bios
    pos_map: Dict[int, str] = {}
    if os.path.exists(bio_file):
        bios = load_json(bio_file)
        for b in bios:
            pid = int(b.get("PLAYER_ID", 0))
            pos = b.get("POSITION", "")
            pos_map[pid] = normalize_position(pos)

    # 2. Matchup pairing to get Opponent OREB and DREB for Oliver rebound percentages
    team_pairs = pd.merge(df_teams, df_teams, on="GAME_ID", suffixes=("", "_OPP"))
    paired = team_pairs[team_pairs["TEAM_ID"] != team_pairs["TEAM_ID_OPP"]].copy()

    # Aggregate Team totals (including Opponent Totals)
    team_agg = paired.groupby("TEAM_ID").agg(
        team_name=("TEAM_NAME", "first"),
        team_abbrev=("TEAM_ABBREVIATION", "first"),
        games=("GAME_ID", "nunique"),
        min=("MIN", "sum"),
        pts=("PTS", "sum"),
        fga=("FGA", "sum"),
        fgm=("FGM", "sum"),
        fta=("FTA", "sum"),
        oreb=("OREB", "sum"),
        dreb=("DREB", "sum"),
        ast=("AST", "sum"),
        tov=("TOV", "sum"),
        opp_oreb=("OREB_OPP", "sum"),
        opp_dreb=("DREB_OPP", "sum"),
    ).reset_index()

    team_lookup = team_agg.set_index("TEAM_ID").to_dict(orient="index")

    # 3. Team Playmaking Centrality (Gini, Helicentrism, Depth)
    team_results: Dict[str, Any] = {}
    for tid, tm in team_lookup.items():
        tm_players = df_players[df_players["TEAM_ID"] == tid]
        player_ast_totals = tm_players.groupby("PLAYER_ID")["AST"].sum().sort_values(ascending=False)

        total_team_ast = float(tm["ast"])
        if total_team_ast > 0 and len(player_ast_totals) > 0:
            top_1_ast = float(player_ast_totals.iloc[0])
            top_2_ast = float(player_ast_totals.iloc[:2].sum())
            helicentrism = top_1_ast / total_team_ast
            playmaking_depth = max(0.0, (total_team_ast - top_2_ast) / total_team_ast)
            ast_gini = calculate_gini(player_ast_totals.tolist())
        else:
            helicentrism = 0.0
            playmaking_depth = 0.0
            ast_gini = 0.0

        team_results[str(tid)] = {
            "team_id": tid,
            "team_name": tm["team_name"],
            "team_abbrev": tm["team_abbrev"],
            "total_assists": int(total_team_ast),
            "playmaking_centrality": {
                "helicentrism_index": round(helicentrism, 4),
                "assist_gini_coefficient": round(ast_gini, 4),
                "playmaking_depth_share": round(playmaking_depth, 4),
            },
        }

    # 4. Player True Floor Share Rates
    player_agg = df_players.groupby("PLAYER_ID").agg(
        player_name=("PLAYER_NAME", "first"),
        team_id=("TEAM_ID", "last"),
        team_abbrev=("TEAM_ABBREVIATION", "last"),
        games=("GAME_ID", "nunique"),
        min=("MIN", "sum"),
        fga=("FGA", "sum"),
        fgm=("FGM", "sum"),
        fta=("FTA", "sum"),
        oreb=("OREB", "sum"),
        dreb=("DREB", "sum"),
        reb=("REB", "sum"),
        ast=("AST", "sum"),
        stl=("STL", "sum"),
        blk=("BLK", "sum"),
        tov=("TOV", "sum"),
        pf=("PF", "sum"),
        pts=("PTS", "sum"),
    ).reset_index()

    player_results: Dict[str, Any] = {}
    for _, row in player_agg.iterrows():
        pid = int(row["PLAYER_ID"])
        tid = int(row["team_id"])
        tm = team_lookup.get(tid)

        if not tm or row["min"] == 0:
            continue

        p_min = float(row["min"])
        p_fga = float(row["fga"])
        p_fgm = float(row["fgm"])
        p_fta = float(row["fta"])
        p_ast = float(row["ast"])
        p_oreb = float(row["oreb"])
        p_dreb = float(row["dreb"])
        p_stl = float(row["stl"])
        p_blk = float(row["blk"])
        p_pf = float(row["pf"])

        tm_min = float(tm["min"])
        tm_fgm = float(tm["fgm"])
        tm_oreb = float(tm["oreb"])
        tm_dreb = float(tm["dreb"])
        tm_opp_oreb = float(tm["opp_oreb"])
        tm_opp_dreb = float(tm["opp_dreb"])

        tm_min_per_player = tm_min / 5.0
        tm_poss = 0.96 * (tm["fga"] + 0.44 * tm["fta"] - tm["oreb"] + tm["tov"])
        player_poss = (tm_poss * (p_min / tm_min_per_player)) if tm_min_per_player > 0 else 0.0

        # Dean Oliver AST%: 100 * AST / (((MIN / (Team MIN / 5)) * Team FGM) - FGM)
        denom_ast = ((p_min / tm_min_per_player) * tm_fgm) - p_fgm if tm_min_per_player > 0 else 0.0
        true_ast_pct = (100.0 * p_ast / denom_ast) if denom_ast > 0 else 0.0

        # Dean Oliver ORB%: 100 * (OREB * (Team MIN / 5)) / (MIN * (Team OREB + Opp DREB))
        denom_orb = p_min * (tm_oreb + tm_opp_dreb)
        true_orb_pct = (100.0 * (p_oreb * tm_min_per_player) / denom_orb) if denom_orb > 0 else 0.0

        # Dean Oliver DREB%: 100 * (DREB * (Team MIN / 5)) / (MIN * (Team DREB + Opp OREB))
        denom_dreb = p_min * (tm_dreb + tm_opp_oreb)
        true_dreb_pct = (100.0 * (p_dreb * tm_min_per_player) / denom_dreb) if denom_dreb > 0 else 0.0

        # Stock Rate: (STL + BLK) per 100 possessions
        stock_rate = ((p_stl + p_blk) / player_poss * 100.0) if player_poss > 0 else 0.0

        # Foul Drawing Premium: FTA / PF
        foul_drawing = (p_fta / p_pf) if p_pf > 0 else (p_fta if p_fta > 0 else 0.0)

        # Pass-to-Shot Creation Leverage: AST / FGA
        pass_shot_leverage = (p_ast / p_fga) if p_fga > 0 else 0.0

        position = pos_map.get(pid, "F")

        player_results[str(pid)] = {
            "player_id": pid,
            "player_name": row["player_name"],
            "team_id": tid,
            "team_abbrev": row["team_abbrev"],
            "position": position,
            "oliver_floor_rates": {
                "true_ast_pct": round(true_ast_pct, 2),
                "true_orb_pct": round(true_orb_pct, 2),
                "true_dreb_pct": round(true_dreb_pct, 2),
                "stock_rate_per_100": round(stock_rate, 2),
                "foul_drawing_premium": round(foul_drawing, 2),
            },
            "playmaking_leverage": {
                "assists_total": int(p_ast),
                "fga_total": int(p_fga),
                "pass_to_shot_ratio": round(pass_shot_leverage, 2),
            },
        }

    return team_results, player_results


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: Playmaking Centrality & True Floor Rates")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Processing Playmaking & Roles for Season: {season} ---")
        teams, players = process_playmaking_and_roles(season)

        payload = {
            "season": season,
            "player_count": len(players),
            "team_count": len(teams),
            "teams": teams,
            "players": players,
        }

        out_path = os.path.join("data", "processed", "features", f"playmaking_and_roles_{season}.json")
        write_json(out_path, payload)
        logger.info(f"Saved {len(teams)} team & {len(players)} player profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Playmaking & role feature generation complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()