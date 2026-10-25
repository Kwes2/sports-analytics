"""
scripts/features/team_elo.py
NBA Analytics Platform - Custom 1,000-Centered Elo Engine

Builds 3 pure-score Elo ratings:
1. Offensive Elo (Team Offense vs Opponent Defense)
2. Defensive Elo (Team Defense vs Opponent Offense)
3. Overall Net Elo (Team Overall vs Opponent Overall based on game margin)

Features:
- Calibrated via min-max score mapping over rolling 1,000 games.
- Offseason mean reversion (25% regression to 1,000).
- Integrated pre-game predictive accuracy backtesting (Win %, Brier score, Log Loss).
"""

import json
import logging
import math
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("TeamElo")

SEASONS = ["2025-26", "2026-27"]
INITIAL_ELO = 1000.0
K_FACTOR = 20.0
OFFSEASON_REVERSION = 0.25  # 25% regression towards 1,000 mean between seasons


def load_json(filepath: str) -> Any:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath: str, data: Any) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, filepath)


def expected_score(rating_a: float, rating_b: float) -> float:
    """Logistic expectation of Rating A against Rating B."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def load_all_game_matchups() -> Tuple[pd.DataFrame, float, float, float, float]:
    """
    Loads all team game logs across 2025-26 and 2026-27, pairs opposing teams,
    sorts chronologically, and calculates empirical score/margin bounds.
    """
    all_logs = []
    for s in ["2025-26", "2026-27"]:
        path = os.path.join("data", "raw", "game_logs", f"team_{s}.json")
        if os.path.exists(path):
            all_logs.extend(load_json(path))

    df = pd.DataFrame(all_logs)
    if df.empty:
        raise RuntimeError("No team game logs available.")

    # Matchup pair join
    merged = pd.merge(df, df, on="GAME_ID", suffixes=("", "_OPP"))
    paired = merged[merged["TEAM_ID"] != merged["TEAM_ID_OPP"]].copy()

    # Deduplicate game pairs (isolate unique game pairings)
    paired["pair_id"] = paired.apply(
        lambda r: "_".join(sorted([str(r["TEAM_ID"]), str(r["TEAM_ID_OPP"])])), axis=1
    )
    unique_games = paired.drop_duplicates(subset=["GAME_ID", "pair_id"]).copy()

    unique_games["GAME_DATE_DT"] = pd.to_datetime(unique_games["GAME_DATE"])
    unique_games = unique_games.sort_values("GAME_DATE_DT").reset_index(drop=True)

    # Calculate empirical bounds
    all_pts = pd.concat([unique_games["PTS"], unique_games["PTS_OPP"]])
    pts_min = float(all_pts.min())
    pts_max = float(all_pts.max())

    margins = unique_games["PTS"] - unique_games["PTS_OPP"]
    margin_min = float(margins.min())
    margin_max = float(margins.max())

    logger.info(
        f"Calibrated on {len(unique_games)} games. "
        f"PTS Range: [{pts_min:.0f}, {pts_max:.0f}], Margin Range: [{margin_min:.0f}, {margin_max:.0f}]"
    )

    return unique_games, pts_min, pts_max, margin_min, margin_max


def run_elo_simulation() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    games_df, pts_min, pts_max, margin_min, margin_max = load_all_game_matchups()

    pts_range = (pts_max - pts_min) if pts_max > pts_min else 1.0
    margin_range = (margin_max - margin_min) if margin_max > margin_min else 1.0

    # Initialize Team Ratings
    elo_off: Dict[int, float] = defaultdict(lambda: INITIAL_ELO)
    elo_def: Dict[int, float] = defaultdict(lambda: INITIAL_ELO)
    elo_overall: Dict[int, float] = defaultdict(lambda: INITIAL_ELO)
    team_names: Dict[int, str] = {}
    team_abbrevs: Dict[int, str] = {}
    
    # Season-specific games played
    games_played_count: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

    # History snapshots by season
    season_snapshots: Dict[str, Dict[str, Any]] = {
        "2025-26": {},
        "2026-27": {},
    }
    
    # Backtest prediction logs by season
    backtest_records: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    current_season = "2025-26"

    for _, row in games_df.iterrows():
        tid_a = int(row["TEAM_ID"])
        tid_b = int(row["TEAM_ID_OPP"])

        # Format season code
        if "2025" in str(row["SEASON_ID"]):
            season = "2025-26"
        elif "2026" in str(row["SEASON_ID"]):
            season = "2026-27"
        else:
            season = "2025-26"

        # Track season transition: Save snapshot and apply offseason mean reversion
        if season != current_season:
            for t, val in elo_overall.items():
                season_snapshots["2025-26"][str(t)] = {
                    "team_id": t,
                    "team_name": team_names.get(t, f"Team {t}"),
                    "team_abbrev": team_abbrevs.get(t, "NBA"),
                    "games_played": games_played_count["2025-26"][t],
                    "offensive_elo": round(elo_off[t], 1),
                    "defensive_elo": round(elo_def[t], 1),
                    "overall_elo": round(elo_overall[t], 1),
                }

            # Apply 25% offseason mean-reversion
            for t in list(elo_overall.keys()):
                elo_off[t] = (1.0 - OFFSEASON_REVERSION) * elo_off[t] + OFFSEASON_REVERSION * INITIAL_ELO
                elo_def[t] = (1.0 - OFFSEASON_REVERSION) * elo_def[t] + OFFSEASON_REVERSION * INITIAL_ELO
                elo_overall[t] = (1.0 - OFFSEASON_REVERSION) * elo_overall[t] + OFFSEASON_REVERSION * INITIAL_ELO

            logger.info(f"Applied {int(OFFSEASON_REVERSION * 100)}% offseason mean-reversion at transition to {season}.")
            current_season = season

        team_names[tid_a] = str(row["TEAM_NAME"])
        team_abbrevs[tid_a] = str(row["TEAM_ABBREVIATION"])
        team_names[tid_b] = str(row["TEAM_NAME_OPP"])
        team_abbrevs[tid_b] = str(row["TEAM_ABBREVIATION_OPP"])
        games_played_count[season][tid_a] += 1
        games_played_count[season][tid_b] += 1

        pts_a = float(row["PTS"])
        pts_b = float(row["PTS_OPP"])

        # Pre-game win prediction (Backtesting)
        exp_prob_a = expected_score(elo_overall[tid_a], elo_overall[tid_b])
        actual_win_a = 1.0 if pts_a > pts_b else 0.0
        pred_win_a = 1.0 if exp_prob_a >= 0.5 else 0.0
        correct = (pred_win_a == actual_win_a)
        brier = (exp_prob_a - actual_win_a) ** 2
        log_loss = - (actual_win_a * math.log(max(1e-6, exp_prob_a)) + (1.0 - actual_win_a) * math.log(max(1e-6, 1.0 - exp_prob_a)))

        backtest_records[season].append({
            "exp_prob": exp_prob_a,
            "actual_win": actual_win_a,
            "correct": correct,
            "brier": brier,
            "log_loss": log_loss,
        })

        # 1. Map Scores to [0, 1]
        norm_score_a = (pts_a - pts_min) / pts_range
        norm_score_b = (pts_b - pts_min) / pts_range

        # 2. Offensive vs Defensive Duel: Team A Offense vs Team B Defense
        exp_a_off = expected_score(elo_off[tid_a], elo_def[tid_b])
        delta_a_off = K_FACTOR * (norm_score_a - exp_a_off)
        elo_off[tid_a] += delta_a_off
        elo_def[tid_b] -= delta_a_off

        # 3. Offensive vs Defensive Duel: Team B Offense vs Team A Defense
        exp_b_off = expected_score(elo_off[tid_b], elo_def[tid_a])
        delta_b_off = K_FACTOR * (norm_score_b - exp_b_off)
        elo_off[tid_b] += delta_b_off
        elo_def[tid_a] -= delta_b_off

        # 4. Overall Duel: Margin mapped to [0, 1]
        margin_a = pts_a - pts_b
        norm_margin_a = (margin_a - margin_min) / margin_range
        exp_margin_a = expected_score(elo_overall[tid_a], elo_overall[tid_b])
        delta_overall = K_FACTOR * (norm_margin_a - exp_margin_a)
        elo_overall[tid_a] += delta_overall
        elo_overall[tid_b] -= delta_overall

    # Capture final active snapshot (2026-27)
    for t in elo_overall.keys():
        season_snapshots["2026-27"][str(t)] = {
            "team_id": t,
            "team_name": team_names.get(t, f"Team {t}"),
            "team_abbrev": team_abbrevs.get(t, "NBA"),
            "games_played": games_played_count["2026-27"][t],
            "offensive_elo": round(elo_off[t], 1),
            "defensive_elo": round(elo_def[t], 1),
            "overall_elo": round(elo_overall[t], 1),
        }

    # Compile backtest summary statistics per season
    backtest_summaries = {}
    for s, recs in backtest_records.items():
        if recs:
            df_recs = pd.DataFrame(recs)
            backtest_summaries[s] = {
                "games_evaluated": len(df_recs),
                "straight_up_accuracy_pct": round(float(df_recs["correct"].mean() * 100.0), 2),
                "brier_score": round(float(df_recs["brier"].mean()), 4),
                "log_loss": round(float(df_recs["log_loss"].mean()), 4),
            }
        else:
            backtest_summaries[s] = {}

    return season_snapshots, backtest_summaries


def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: 1,000-Centered Team Elo Engine")
    logger.info("==================================================")

    elo_snapshots, backtest_summaries = run_elo_simulation()

    for season, data in elo_snapshots.items():
        if not data:
            continue
        out_path = os.path.join("data", "processed", "features", f"team_elo_{season}.json")
        payload = {
            "season": season,
            "anchor_elo": INITIAL_ELO,
            "k_factor": K_FACTOR,
            "offseason_reversion_pct": round(OFFSEASON_REVERSION * 100.0, 1),
            "backtest_evaluation": backtest_summaries.get(season, {}),
            "team_count": len(data),
            "teams": data,
        }
        write_json(out_path, payload)
        summary = backtest_summaries.get(season, {})
        acc = summary.get("straight_up_accuracy_pct", "N/A")
        logger.info(
            f"Saved {len(data)} team Elo profiles to {out_path} "
            f"(Season {season} Backtest Accuracy: {acc}%)"
        )

    logger.info("==================================================")
    logger.info("Team Elo engine complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()
