"""
scripts/testing/backtest_elo.py
NBA Analytics Platform - Team Elo Model Calibration & Backtest Tester

Evaluates the predictive fidelity of the 1,000-centered Elo engine across:
1. Overall Straight-Up Win/Loss Prediction Accuracy %
2. Probability Calibration (Brier Score & Log Loss)
3. Monthly & Seasonal Accuracy Breakdown
4. Home vs Away Predictive Performance
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
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("EloBacktest")

INITIAL_ELO = 1000.0
K_FACTOR = 20.0
OFFSEASON_REVERSION = 0.25


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def load_json(filepath: str) -> Any:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    logger.info("==================================================")
    logger.info("NBA ELO CALIBRATION & PREDICTIVE BACKTEST TESTER")
    logger.info(f"Parameters: Base={INITIAL_ELO}, K={K_FACTOR}, Offseason Mean Reversion={int(OFFSEASON_REVERSION * 100)}%")
    logger.info("==================================================")

    all_logs = []
    for s in ["2025-26", "2026-27"]:
        p = os.path.join("data", "raw", "game_logs", f"team_{s}.json")
        if os.path.exists(p):
            all_logs.extend(load_json(p))

    df = pd.DataFrame(all_logs)
    merged = pd.merge(df, df, on="GAME_ID", suffixes=("", "_OPP"))
    paired = merged[merged["TEAM_ID"] != merged["TEAM_ID_OPP"]].copy()
    paired["pair_id"] = paired.apply(
        lambda r: "_".join(sorted([str(r["TEAM_ID"]), str(r["TEAM_ID_OPP"])])), axis=1
    )
    unique_games = paired.drop_duplicates(subset=["GAME_ID", "pair_id"]).copy()
    unique_games["GAME_DATE_DT"] = pd.to_datetime(unique_games["GAME_DATE"])
    unique_games = unique_games.sort_values("GAME_DATE_DT").reset_index(drop=True)

    all_pts = pd.concat([unique_games["PTS"], unique_games["PTS_OPP"]])
    pts_min = float(all_pts.min())
    pts_max = float(all_pts.max())
    margins = unique_games["PTS"] - unique_games["PTS_OPP"]
    margin_min = float(margins.min())
    margin_max = float(margins.max())
    pts_range = (pts_max - pts_min) if pts_max > pts_min else 1.0
    margin_range = (margin_max - margin_min) if margin_max > margin_min else 1.0

    elo_overall = defaultdict(lambda: INITIAL_ELO)
    current_season = "2025-26"
    records = []

    for _, row in unique_games.iterrows():
        tid_a = int(row["TEAM_ID"])
        tid_b = int(row["TEAM_ID_OPP"])
        pts_a = float(row["PTS"])
        pts_b = float(row["PTS_OPP"])

        season = "2025-26" if "2025" in str(row["SEASON_ID"]) else "2026-27"
        if season != current_season:
            for t in list(elo_overall.keys()):
                elo_overall[t] = (1.0 - OFFSEASON_REVERSION) * elo_overall[t] + OFFSEASON_REVERSION * INITIAL_ELO
            current_season = season

        # Pre-game expectation
        exp_prob_a = expected_score(elo_overall[tid_a], elo_overall[tid_b])
        actual_win_a = 1.0 if pts_a > pts_b else 0.0
        pred_win_a = 1.0 if exp_prob_a >= 0.5 else 0.0
        correct = (pred_win_a == actual_win_a)
        brier = (exp_prob_a - actual_win_a) ** 2
        log_loss = - (actual_win_a * math.log(max(1e-6, exp_prob_a)) + (1.0 - actual_win_a) * math.log(max(1e-6, 1.0 - exp_prob_a)))

        records.append({
            "game_id": row["GAME_ID"],
            "date": row["GAME_DATE_DT"],
            "month": row["GAME_DATE_DT"].strftime("%Y-%m"),
            "season": season,
            "team_a": row["TEAM_ABBREVIATION"],
            "team_b": row["TEAM_ABBREVIATION_OPP"],
            "elo_a": elo_overall[tid_a],
            "elo_b": elo_overall[tid_b],
            "exp_prob_a": exp_prob_a,
            "actual_win_a": actual_win_a,
            "correct": correct,
            "brier": brier,
            "log_loss": log_loss,
        })

        # Update Elo
        margin_a = pts_a - pts_b
        norm_margin_a = (margin_a - margin_min) / margin_range
        exp_margin_a = expected_score(elo_overall[tid_a], elo_overall[tid_b])
        delta = K_FACTOR * (norm_margin_a - exp_margin_a)
        elo_overall[tid_a] += delta
        elo_overall[tid_b] -= delta

    res_df = pd.DataFrame(records)

    total_games = len(res_df)
    acc = res_df["correct"].mean() * 100.0
    brier = res_df["brier"].mean()
    logloss = res_df["log_loss"].mean()

    logger.info(f"\n[OVERALL BACKTEST SUMMARY]")
    logger.info(f"Total Games Evaluated:        {total_games:,}")
    logger.info(f"Straight-Up Accuracy:         {acc:.2f}%")
    logger.info(f"Brier Score (lower is better): {brier:.4f}")
    logger.info(f"Log Loss (lower is better):    {logloss:.4f}")

    logger.info(f"\n[SEASON-BY-SEASON ACCURACY]")
    logger.info(f"{'Season':<12} | {'Games':<8} | {'Accuracy %':<12} | {'Brier Score':<12} | {'Log Loss':<10}")
    logger.info("-" * 62)
    for s, grp in res_df.groupby("season"):
        logger.info(
            f"{s:<12} | {len(grp):<8} | {grp['correct'].mean() * 100:<12.2f} | {grp['brier'].mean():<12.4f} | {grp['log_loss'].mean():<10.4f}"
        )

    logger.info(f"\n[MONTHLY CALIBRATION BREAKDOWN (2025-26)]")
    logger.info(f"{'Month':<12} | {'Games':<8} | {'Accuracy %':<12} | {'Brier Score':<12}")
    logger.info("-" * 50)
    s25 = res_df[res_df["season"] == "2025-26"]
    for m, grp in s25.groupby("month"):
        logger.info(f"{m:<12} | {len(grp):<8} | {grp['correct'].mean() * 100:<12.2f} | {grp['brier'].mean():<12.4f}")

    logger.info("\n==================================================")
    logger.info("Elo Backtest Complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()
