"""
scripts/features/effective_plus_minus.py
NBA Analytics Platform - Stint Decomposition & Effective Plus-Minus (EPM / RAPM)

1. Decomposes Play-by-Play into 10-player on-court stints between substitutions.
2. Solves weighted Ridge Regression (L2) to compute:
   - Offensive EPM (OEPM)
   - Defensive EPM (DEPM)
   - Net EPM (Total isolated impact per 100 possessions)
3. Computes Relative Plus-Minus: Actual Net +/- vs Expected Net +/- given teammates & opponents.
"""

import glob
import json
import logging
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("EffectivePlusMinus")

SEASONS = ["2026-27", "2025-26"]
LAMBDA_RIDGE = 1500.0  # L2 Shrinkage penalty parameter
SUB_REGEX = re.compile(r"SUB:\s+([A-Za-z0-9\.\'\-\s]+?)\s+FOR\s+([A-Za-z0-9\.\'\-\s]+)", re.IGNORECASE)


def load_json(filepath: str) -> Any:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath: str, data: Any) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, filepath)


def parse_clock_seconds(clock_str: Optional[str]) -> float:
    """Converts 'PT11M45.00S' to total seconds remaining (705.0)."""
    if not clock_str or not isinstance(clock_str, str):
        return 0.0
    m = re.search(r"PT(\d+)M([\d\.]+)S", clock_str)
    if m:
        return float(m.group(1)) * 60.0 + float(m.group(2))
    return 0.0


def clean_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z]", "", name).lower()


# ---------------------------------------------------------------------------
# Stint Extraction Engine
# ---------------------------------------------------------------------------
class StintTracker:
    """Tracks on-court lineups across periods and substitution events."""

    def __init__(self, game_id: str, events: List[Dict[str, Any]], bio_map: Dict[Tuple[int, str], int]):
        self.game_id = game_id
        self.events = events
        self.bio_map = bio_map
        self.stints: List[Dict[str, Any]] = []

    def extract_stints(self) -> List[Dict[str, Any]]:
        # Identify Home & Away Team IDs
        team_ids = list({e["team_id"] for e in self.events if e.get("team_id") and e["team_id"] > 0})
        if len(team_ids) < 2:
            return []
        home_team_id, away_team_id = team_ids[0], team_ids[1]

        # Group by Period
        periods = defaultdict(list)
        for e in self.events:
            periods[e.get("period", 1)].append(e)

        for period, p_events in periods.items():
            self._process_period(period, p_events, home_team_id, away_team_id)

        return self.stints

    def _process_period(self, period: int, p_events: List[Dict[str, Any]], home_tid: int, away_tid: int):
        # 1. Identify on-court players at period start
        # Build initial 5 for each team by scanning events before substitutions
        home_on: Set[int] = set()
        away_on: Set[int] = set()

        # Map of (team_id, name) -> person_id in this period
        period_name_map: Dict[Tuple[int, str], int] = {}
        for e in p_events:
            pid = e.get("person_id")
            pname = e.get("player_name")
            tid = e.get("team_id")
            if pid and pname and tid:
                period_name_map[(tid, clean_name(pname))] = int(pid)

        # Scan players active in period
        for e in p_events:
            pid = e.get("person_id")
            tid = e.get("team_id")
            desc = e.get("description", "") or ""
            act_type = str(e.get("action_type", "")).lower()

            if "sub:" in desc.lower() or "substitution" in act_type:
                # Stop pre-sub accumulation
                break

            if pid and int(pid) > 0 and tid in [home_tid, away_tid]:
                if tid == home_tid and len(home_on) < 5:
                    home_on.add(int(pid))
                elif tid == away_tid and len(away_on) < 5:
                    away_on.add(int(pid))

        # Stint state
        period_seconds = 300.0 if period >= 5 else 720.0
        stint_start_clock = period_seconds
        stint_home_pts = 0
        stint_away_pts = 0

        prev_score_h = 0
        prev_score_a = 0

        for e in p_events:
            clock_sec = parse_clock_seconds(e.get("clock"))
            desc = e.get("description", "") or ""
            act_type = str(e.get("action_type", "")).lower()
            score_h_raw = e.get("score_home")
            score_a_raw = e.get("score_away")

            # Update scores
            if score_h_raw and score_h_raw.isdigit():
                cur_h = int(score_h_raw)
                if cur_h > prev_score_h:
                    stint_home_pts += (cur_h - prev_score_h)
                    prev_score_h = cur_h

            if score_a_raw and score_a_raw.isdigit():
                cur_a = int(score_a_raw)
                if cur_a > prev_score_a:
                    stint_away_pts += (cur_a - prev_score_a)
                    prev_score_a = cur_a

            # Check for substitution
            if "sub:" in desc.lower() or "substitution" in act_type:
                match = SUB_REGEX.search(desc)
                if match:
                    p_in_name = clean_name(match.group(1))
                    p_out_name = clean_name(match.group(2))
                    sub_tid = int(e.get("team_id", 0))

                    p_in_id = period_name_map.get((sub_tid, p_in_name)) or self.bio_map.get((sub_tid, p_in_name))
                    p_out_id = period_name_map.get((sub_tid, p_out_name)) or self.bio_map.get((sub_tid, p_out_name))

                    # Close current stint if duration > 0 and valid lineups
                    stint_duration = stint_start_clock - clock_sec
                    if stint_duration >= 5.0 and len(home_on) >= 3 and len(away_on) >= 3:
                        # Estimate possessions from duration (assuming ~100 pace = 1 poss / 28.8s)
                        poss = max(1.0, stint_duration / 28.8)
                        self.stints.append({
                            "game_id": self.game_id,
                            "period": period,
                            "duration_sec": stint_duration,
                            "possessions": round(poss, 2),
                            "home_pts": stint_home_pts,
                            "away_pts": stint_away_pts,
                            "net_pts": stint_home_pts - stint_away_pts,
                            "home_players": list(home_on),
                            "away_players": list(away_on),
                        })

                    # Reset stint
                    stint_start_clock = clock_sec
                    stint_home_pts = 0
                    stint_away_pts = 0

                    # Update on-court sets
                    if sub_tid == home_tid:
                        if p_out_id in home_on:
                            home_on.remove(p_out_id)
                        if p_in_id:
                            home_on.add(p_in_id)
                    elif sub_tid == away_tid:
                        if p_out_id in away_on:
                            away_on.remove(p_out_id)
                        if p_in_id:
                            away_on.add(p_in_id)

        # Close final stint of period
        stint_duration = stint_start_clock - 0.0
        if stint_duration >= 5.0 and len(home_on) >= 3 and len(away_on) >= 3:
            poss = max(1.0, stint_duration / 28.8)
            self.stints.append({
                "game_id": self.game_id,
                "period": period,
                "duration_sec": stint_duration,
                "possessions": round(poss, 2),
                "home_pts": stint_home_pts,
                "away_pts": stint_away_pts,
                "net_pts": stint_home_pts - stint_away_pts,
                "home_players": list(home_on),
                "away_players": list(away_on),
            })


# ---------------------------------------------------------------------------
# Ridge Regularized Adjusted Plus-Minus Solver
# ---------------------------------------------------------------------------
def solve_rapm(stints: List[Dict[str, Any]]) -> Dict[int, Dict[str, float]]:
    """
    Constructs Stint Design Matrix and solves Ridge Regression:
    (X^T W X + lambda * I) * beta = X^T W Y
    """
    if len(stints) < 10:
        logger.warning("Insufficient stints to solve RAPM.")
        return {}

    # Unique player index
    player_set: Set[int] = set()
    for s in stints:
        player_set.update(s["home_players"])
        player_set.update(s["away_players"])

    players = sorted(list(player_set))
    pid_to_idx = {pid: i for i, pid in enumerate(players)}
    num_players = len(players)
    num_stints = len(stints)

    logger.info(f"Assembling RAPM matrix: {num_stints:,} stints across {num_players} players...")

    # Design Matrix X and Targets
    X = np.zeros((num_stints, num_players), dtype=np.float32)
    weights = np.zeros(num_stints, dtype=np.float32)
    y_net = np.zeros(num_stints, dtype=np.float32)
    y_off_h = np.zeros(num_stints, dtype=np.float32)
    y_def_h = np.zeros(num_stints, dtype=np.float32)

    for i, s in enumerate(stints):
        poss = s["possessions"]
        weights[i] = poss

        # Home (+1)
        for h_pid in s["home_players"]:
            if h_pid in pid_to_idx:
                X[i, pid_to_idx[h_pid]] = 1.0

        # Away (-1)
        for a_pid in s["away_players"]:
            if a_pid in pid_to_idx:
                X[i, pid_to_idx[a_pid]] = -1.0

        # Net points per 100 poss
        y_net[i] = (s["net_pts"] / poss) * 100.0
        y_off_h[i] = (s["home_pts"] / poss) * 100.0
        y_def_h[i] = (s["away_pts"] / poss) * 100.0

    # Weighted Ridge Regression
    # W_sqrt = sqrt(weights)
    # (X_w^T X_w + lambda * I) * beta = X_w^T (W_sqrt * y)
    W_sqrt = np.sqrt(weights)[:, np.newaxis]
    X_w = X * W_sqrt
    XtX = np.dot(X_w.T, X_w)

    # Regularization Matrix (lambda * I)
    reg_matrix = np.eye(num_players, dtype=np.float32) * LAMBDA_RIDGE
    A = XtX + reg_matrix

    # 1. Net EPM
    b_net = np.dot(X_w.T, y_net * W_sqrt.squeeze())
    beta_net = np.linalg.solve(A, b_net)

    # 2. Offensive EPM
    b_off = np.dot(X_w.T, y_off_h * W_sqrt.squeeze())
    beta_off = np.linalg.solve(A, b_off)

    # 3. Defensive EPM
    # For defense, lower points allowed is better -> inverted
    b_def = np.dot(X_w.T, y_def_h * W_sqrt.squeeze())
    beta_def = -np.linalg.solve(A, b_def)

    # Compile results
    rapm_results = {}
    for i, pid in enumerate(players):
        rapm_results[pid] = {
            "offensive_epm": round(float(beta_off[i]), 2),
            "defensive_epm": round(float(beta_def[i]), 2),
            "net_epm": round(float(beta_net[i]), 2),
        }

    return rapm_results


# ---------------------------------------------------------------------------
# Relative Plus-Minus Calculator
# ---------------------------------------------------------------------------
def compute_relative_plus_minus(
    stints: List[Dict[str, Any]], rapm_results: Dict[int, Dict[str, float]]
) -> Dict[int, Dict[str, Any]]:
    """
    Computes Relative Plus-Minus:
    Actual Net Margin/100 minus Expected Margin/100 based on teammate/opponent ratings.
    """
    player_accum = defaultdict(lambda: {"poss": 0.0, "actual_pts_diff": 0.0, "expected_pts_diff": 0.0})

    for s in stints:
        poss = s["possessions"]
        home_players = s["home_players"]
        away_players = s["away_players"]
        net_pts = s["net_pts"]

        # Calculate Expected Margin for this stint based on player EPMs
        home_exp_epm = sum(rapm_results.get(p, {}).get("net_epm", 0.0) for p in home_players)
        away_exp_epm = sum(rapm_results.get(p, {}).get("net_epm", 0.0) for p in away_players)

        # For Home players:
        for p in home_players:
            # Expected without self (what teammates vs opponents should generate)
            team_exp = home_exp_epm - rapm_results.get(p, {}).get("net_epm", 0.0)
            stint_exp_net = (team_exp - away_exp_epm) * (poss / 100.0)

            player_accum[p]["poss"] += poss
            player_accum[p]["actual_pts_diff"] += net_pts
            player_accum[p]["expected_pts_diff"] += stint_exp_net

        # For Away players (inverted net):
        for p in away_players:
            team_exp = away_exp_epm - rapm_results.get(p, {}).get("net_epm", 0.0)
            stint_exp_net = (team_exp - home_exp_epm) * (poss / 100.0)

            player_accum[p]["poss"] += poss
            player_accum[p]["actual_pts_diff"] += (-net_pts)
            player_accum[p]["expected_pts_diff"] += stint_exp_net

    relative_pm_results = {}
    for pid, data in player_accum.items():
        poss = data["poss"]
        if poss < 5.0:
            continue
        actual_per_100 = (data["actual_pts_diff"] / poss) * 100.0
        expected_per_100 = (data["expected_pts_diff"] / poss) * 100.0
        rel_pm = actual_per_100 - expected_per_100

        relative_pm_results[pid] = {
            "stint_possessions_evaluated": round(poss, 1),
            "actual_net_margin_per_100": round(actual_per_100, 2),
            "expected_net_margin_per_100": round(expected_per_100, 2),
            "relative_plus_minus": round(rel_pm, 2),
        }

    return relative_pm_results


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: Stint Decomposition & EPM / RAPM")
    logger.info("==================================================")

    for season in SEASONS:
        pbp_files = glob.glob(os.path.join("data", "raw", "pbp", season, "*.json"))
        if not pbp_files:
            continue

        logger.info(f"--- Extracting Stints for Season: {season} ({len(pbp_files)} games) ---")

        bio_file = os.path.join("data", "raw", "player_bios", f"{season}.json")
        bio_map: Dict[Tuple[int, str], int] = {}
        if os.path.exists(bio_file):
            for b in load_json(bio_file):
                pid = int(b["PLAYER_ID"])
                tid = int(b.get("TEAM_ID", 0))
                pname = clean_name(b["PLAYER_NAME"])
                last_name = clean_name(b["PLAYER_NAME"].split()[-1])
                bio_map[(tid, pname)] = pid
                bio_map[(tid, last_name)] = pid

        all_stints = []
        for filepath in pbp_files:
            events = load_json(filepath)
            gid = os.path.splitext(os.path.basename(filepath))[0]
            tracker = StintTracker(gid, events, bio_map)
            all_stints.extend(tracker.extract_stints())

        logger.info(f"Season {season}: Extracted {len(all_stints):,} on-court stints.")

        # 1. Solve RAPM (OEPM, DEPM, Net EPM)
        rapm_results = solve_rapm(all_stints)

        # 2. Compute Relative Plus-Minus (Actual vs Expected)
        rel_pm_results = compute_relative_plus_minus(all_stints, rapm_results)

        # Combine
        combined_player_epm = {}
        for pid, rapm in rapm_results.items():
            rpm = rel_pm_results.get(pid, {})
            combined_player_epm[str(pid)] = {
                "player_id": pid,
                "epm_ratings": {
                    "offensive_epm": rapm["offensive_epm"],
                    "defensive_epm": rapm["defensive_epm"],
                    "net_epm": rapm["net_epm"],
                },
                "relative_plus_minus": {
                    "stint_possessions": rpm.get("stint_possessions_evaluated"),
                    "actual_net_margin_per_100": rpm.get("actual_net_margin_per_100"),
                    "expected_net_margin_per_100": rpm.get("expected_net_margin_per_100"),
                    "relative_plus_minus": rpm.get("relative_plus_minus"),
                },
            }

        out_path = os.path.join("data", "processed", "features", f"effective_plus_minus_{season}.json")
        payload = {
            "season": season,
            "stints_evaluated": len(all_stints),
            "players_evaluated": len(combined_player_epm),
            "players": combined_player_epm,
        }
        write_json(out_path, payload)
        logger.info(f"Saved {len(combined_player_epm)} player EPM profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Effective Plus-Minus modeling complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()