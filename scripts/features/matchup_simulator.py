"""
scripts/features/matchup_simulator.py
NBA Analytics Platform - Interactive Head-to-Head Matchup Simulation Engine

Computes tactical matchup clash metrics and pre-game predictions:
1. Expected Game Pace & Total Possessions
2. Predicted Team Scores & Margin
3. Logistic Win Probabilities (Elo + Home Advantage + 2-Way Defensive Adjustment)
4. Tactical Clashes:
   - Rim Battle: Rim Pressure vs Rim Denial Efficiency
   - Perimeter Battle: 3PT Generation vs Perimeter Suppression
   - Turnover & Rebound Battle: Possession Ledger Margin

Exports:
- data/analytics/matchups_{season}.json (Complete 30x30 matrix)
- data/analytics/matchups/{season}/{HOME}_{AWAY}.json (Instant static route payloads)
"""

import json
import logging
import math
import os
import sys
from typing import Any, Dict, List, Optional
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("MatchupSim")

SEASONS = ["2026-27", "2025-26"]
HOME_COURT_ELO_ADVANTAGE = 0  # not needed
HOME_COURT_RATING_ADVANTAGE = 0  # not needed


def load_json(filepath: str) -> Any:
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath: str, data: Any) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, filepath)


def expected_win_prob(elo_home: float, elo_away: float) -> float:
    diff = (elo_home + HOME_COURT_ELO_ADVANTAGE) - elo_away
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def evaluate_edge(val_a: float, val_b: float, threshold: float = 0.02) -> str:
    if (val_a - val_b) >= threshold:
        return "home"
    elif (val_b - val_a) >= threshold:
        return "away"
    return "even"


def simulate_season_matchups(season: str) -> Dict[str, Any]:
    team_def_file = os.path.join("data", "processed", "features", f"team_defense_{season}.json")
    team_elo_file = os.path.join("data", "processed", "features", f"team_elo_{season}.json")
    team_shots_file = os.path.join("data", "processed", "features", f"shot_features_{season}.json")
    team_sp_file = os.path.join("data", "processed", "features", f"spatial_hot_cold_{season}.json")
    baseline_file = os.path.join("data", "processed", "league_baselines.json")

    team_def = load_json(team_def_file).get("teams", {})
    team_elo = load_json(team_elo_file).get("teams", {})
    team_shots = load_json(team_shots_file).get("teams", {})
    team_sp = load_json(team_sp_file).get("teams", {})
    baselines = load_json(baseline_file)

    if not team_def or not team_elo:
        logger.warning(f"Insufficient team data to simulate matchups for {season}.")
        return {}

    league_pace = baselines.get("possession_benchmarks", {}).get("pace_per_48", 98.0)
    league_ortg = baselines.get("possession_benchmarks", {}).get("offensive_rating_baseline", 115.0)

    team_ids = list(team_def.keys())
    matchups: Dict[str, Any] = {}

    for tid_h_str in team_ids:
        for tid_a_str in team_ids:
            if tid_h_str == tid_a_str:
                continue

            th_def = team_def[tid_h_str]
            ta_def = team_def[tid_a_str]

            th_elo = team_elo.get(tid_h_str, {})
            ta_elo = team_elo.get(tid_a_str, {})

            th_shot = team_shots.get(tid_h_str, {})
            ta_shot = team_shots.get(tid_a_str, {})

            th_sp = team_sp.get(tid_h_str, {})
            ta_sp = team_sp.get(tid_a_str, {})

            abbrev_h = th_def["team_abbrev"]
            abbrev_a = ta_def["team_abbrev"]
            matchup_key = f"{abbrev_h}_vs_{abbrev_a}"

            # 1. Pace Projection
            pace_h = th_def.get("pace", league_pace)
            pace_a = ta_def.get("pace", league_pace)
            exp_pace = (pace_h * pace_a) / league_pace if league_pace > 0 else 98.0

            # 2. Ratings & Score Projection
            # Home Offense vs Away Defense + Home Court
            h_ortg = th_def.get("ratings", {}).get("offensive_rating", league_ortg)
            a_drtg = ta_def.get("ratings", {}).get("defensive_rating", league_ortg)
            proj_h_ortg = h_ortg + (a_drtg - league_ortg) + HOME_COURT_RATING_ADVANTAGE

            # Away Offense vs Home Defense
            a_ortg = ta_def.get("ratings", {}).get("offensive_rating", league_ortg)
            h_drtg = th_def.get("ratings", {}).get("defensive_rating", league_ortg)
            proj_a_ortg = a_ortg + (h_drtg - league_ortg)

            proj_h_pts = round((proj_h_ortg * exp_pace) / 100.0, 1)
            proj_a_pts = round((proj_a_ortg * exp_pace) / 100.0, 1)

            # 3. Logistic Elo Win Probability
            elo_h = th_elo.get("overall_elo", 1000.0)
            elo_a = ta_elo.get("overall_elo", 1000.0)
            home_win_prob = round(expected_win_prob(elo_h, elo_a), 4)

            # 4. Tactical Clashes
            # Rim Clash
            h_rim_rate = th_shot.get("rim_pressure", {}).get("rim_pressure_rate", 0.28)
            a_rim_denial = ta_sp.get("rim_denial_efficiency", 0.0)
            rim_edge = "home" if h_rim_rate > 0.32 and a_rim_denial < 0.0 else ("away" if a_rim_denial > 0.03 else "even")

            # Perimeter Clash
            h_3pt_rate = th_def.get("scheme_profile", {}).get("three_point_attempt_rate", 0.38)
            a_3pt_opp_rate = ta_def.get("scheme_profile", {}).get("three_point_attempt_rate", 0.38)
            three_edge = evaluate_edge(h_3pt_rate, a_3pt_opp_rate, threshold=0.03)

            # Possession Battle (Rebound & TOV ledger)
            h_poss_margin = th_def.get("possession_ledger", {}).get("possession_margin_per_game", 0.0)
            a_poss_margin = ta_def.get("possession_ledger", {}).get("possession_margin_per_game", 0.0)
            poss_edge = evaluate_edge(h_poss_margin, a_poss_margin, threshold=1.0)

            matchup_data = {
                "matchup_id": matchup_key,
                "season": season,
                "home_team": {
                    "team_id": th_def["team_id"],
                    "team_name": th_def["team_name"],
                    "team_abbrev": abbrev_h,
                    "overall_elo": elo_h,
                },
                "away_team": {
                    "team_id": ta_def["team_id"],
                    "team_name": ta_def["team_name"],
                    "team_abbrev": abbrev_a,
                    "overall_elo": elo_a,
                },
                "predicted_pace": round(exp_pace, 1),
                "home_win_probability": home_win_prob,
                "away_win_probability": round(1.0 - home_win_prob, 4),
                "predicted_score": {
                    "home": proj_h_pts,
                    "away": proj_a_pts,
                    "margin": round(proj_h_pts - proj_a_pts, 1),
                    "total_points": round(proj_h_pts + proj_a_pts, 1),
                },
                "tactical_clashes": {
                    "rim_pressure_vs_denial": {
                        "home_rim_pressure_rate": h_rim_rate,
                        "away_rim_denial_efficiency": a_rim_denial,
                        "edge": rim_edge,
                    },
                    "perimeter_spacing_clash": {
                        "home_three_point_rate": h_3pt_rate,
                        "edge": three_edge,
                    },
                    "possession_turnover_war": {
                        "home_poss_margin_per_game": h_poss_margin,
                        "away_poss_margin_per_game": a_poss_margin,
                        "edge": poss_edge,
                    },
                },
            }

            matchups[matchup_key] = matchup_data

            # Export individual file for instant static routing: data/analytics/matchups/{season}/{matchup_key}.json
            single_out_path = os.path.join("data", "analytics", "matchups", season, f"{matchup_key}.json")
            write_json(single_out_path, matchup_data)

    return matchups


def main() -> None:
    logger.info("==================================================")
    logger.info("Simulation: Interactive Head-to-Head Matchup Engine")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Generating Matchup Simulations for Season: {season} ---")
        all_matchups = simulate_season_matchups(season)
        if not all_matchups:
            continue

        out_path = os.path.join("data", "analytics", f"matchups_{season}.json")
        payload = {
            "season": season,
            "total_matchups_simulated": len(all_matchups),
            "matchups": all_matchups,
        }
        write_json(out_path, payload)
        logger.info(f"Exported {len(all_matchups)} precomputed matchup projections to {out_path}")

    logger.info("==================================================")
    logger.info("Matchup simulation generation complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()
