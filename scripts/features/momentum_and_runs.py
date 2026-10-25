"""
scripts/features/momentum_and_runs.py
NBA Analytics Platform - PBP Scoring Runs, Momentum & Drought Engine

Computes from play-by-play timelines:
1. Run Generation Rate (8-0+, 10-0+, 12-0+ runs per game)
2. Run Concession Rate & Net Run Margin
3. Scoring Drought Frequency (intervals of 3+ minutes without scoring)
4. Double-Digit Lead Preservation % & Deficit Comeback Rate
5. Season Highs: Largest Comeback Win & Largest Blown Lead
"""

import glob
import json
import logging
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("MomentumAndRuns")

SEASONS = ["2026-27", "2025-26"]


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
    if not clock_str or not isinstance(clock_str, str):
        return 0.0
    m = re.search(r"PT(\d+)M([\d\.]+)S", clock_str)
    if m:
        return float(m.group(1)) * 60.0 + float(m.group(2))
    return 0.0


# ---------------------------------------------------------------------------
# Game Momentum Analyzer
# ---------------------------------------------------------------------------
def analyze_game_momentum(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyzes a single game timeline for scoring runs, droughts, and lead swings."""
    team_ids = list({e["team_id"] for e in events if e.get("team_id") and e["team_id"] > 0})
    if len(team_ids) < 2:
        return {}

    home_tid, away_tid = team_ids[0], team_ids[1]

    # Track scores chronologically
    score_events = []
    prev_h = 0
    prev_a = 0

    for e in events:
        sh = e.get("score_home")
        sa = e.get("score_away")
        period = int(e.get("period", 1))
        clock_sec = parse_clock_seconds(e.get("clock"))

        # Total elapsed game seconds
        if period <= 4:
            elapsed = ((period - 1) * 720.0) + (720.0 - clock_sec)
        else:
            elapsed = 2880.0 + ((period - 5) * 300.0) + (300.0 - clock_sec)

        if sh and sh.isdigit() and sa and sa.isdigit():
            cur_h = int(sh)
            cur_a = int(sa)
            if cur_h > prev_h or cur_a > prev_a:
                pts_h = cur_h - prev_h
                pts_a = cur_a - prev_a
                score_events.append({
                    "elapsed": elapsed,
                    "cur_h": cur_h,
                    "cur_a": cur_a,
                    "margin_h": cur_h - cur_a,
                    "scoring_team": home_tid if pts_h > 0 else away_tid,
                    "pts": pts_h if pts_h > 0 else pts_a,
                })
                prev_h = cur_h
                prev_a = cur_a

    if not score_events:
        return {}

    # 1. Lead Tracking
    margins_h = [ev["margin_h"] for ev in score_events]
    max_lead_h = max(margins_h)
    max_lead_a = -min(margins_h)

    final_h = score_events[-1]["cur_h"]
    final_a = score_events[-1]["cur_a"]
    home_won = final_h > final_a

    # 2. Unanswered Scoring Runs (8-0+, 10-0+, 12-0+)
    runs = {home_tid: {"8_0": 0, "10_0": 0, "12_0": 0}, away_tid: {"8_0": 0, "10_0": 0, "12_0": 0}}

    current_streak_team = None
    current_streak_pts = 0

    for ev in score_events:
        s_team = ev["scoring_team"]
        pts = ev["pts"]

        if s_team == current_streak_team:
            current_streak_pts += pts
        else:
            # Evaluate ended streak
            if current_streak_team and current_streak_pts >= 8:
                runs[current_streak_team]["8_0"] += 1
                if current_streak_pts >= 10:
                    runs[current_streak_team]["10_0"] += 1
                if current_streak_pts >= 12:
                    runs[current_streak_team]["12_0"] += 1

            current_streak_team = s_team
            current_streak_pts = pts

    # Final streak check
    if current_streak_team and current_streak_pts >= 8:
        runs[current_streak_team]["8_0"] += 1
        if current_streak_pts >= 10:
            runs[current_streak_team]["10_0"] += 1
        if current_streak_pts >= 12:
            runs[current_streak_team]["12_0"] += 1

    # 3. Scoring Droughts (Intervals >= 180 seconds between baskets)
    droughts = {home_tid: 0, away_tid: 0}
    prev_basket_time = {home_tid: 0.0, away_tid: 0.0}

    for ev in score_events:
        s_team = ev["scoring_team"]
        t = ev["elapsed"]
        gap = t - prev_basket_time[s_team]
        if gap >= 180.0 and prev_basket_time[s_team] > 0.0:
            droughts[s_team] += 1
        prev_basket_time[s_team] = t

    return {
        "home_tid": home_tid,
        "away_tid": away_tid,
        "home_won": home_won,
        "max_lead_h": max_lead_h,
        "max_lead_a": max_lead_a,
        "runs": runs,
        "droughts": droughts,
    }


# ---------------------------------------------------------------------------
# Season Aggregator
# ---------------------------------------------------------------------------
def process_season_momentum(season: str) -> Dict[str, Any]:
    pbp_files = glob.glob(os.path.join("data", "raw", "pbp", season, "*.json"))
    if not pbp_files:
        return {}

    team_stats = defaultdict(lambda: {
        "games": 0,
        "runs_gen_8": 0,
        "runs_gen_10": 0,
        "runs_gen_12": 0,
        "runs_con_8": 0,
        "droughts_count": 0,
        "lead_10_chances": 0,
        "lead_10_preserved": 0,
        "trail_10_chances": 0,
        "trail_10_comebacks": 0,
        "largest_lead_held": 0,
        "largest_comeback_win": 0,
        "largest_blown_lead": 0,
    })

    for filepath in pbp_files:
        events = load_json(filepath)
        res = analyze_game_momentum(events)
        if not res:
            continue

        h_tid = res["home_tid"]
        a_tid = res["away_tid"]
        h_won = res["home_won"]
        max_h = res["max_lead_h"]
        max_a = res["max_lead_a"]
        runs = res["runs"]
        droughts = res["droughts"]

        # Update Home
        th = team_stats[h_tid]
        th["games"] += 1
        th["runs_gen_8"] += runs[h_tid]["8_0"]
        th["runs_gen_10"] += runs[h_tid]["10_0"]
        th["runs_gen_12"] += runs[h_tid]["12_0"]
        th["runs_con_8"] += runs[a_tid]["8_0"]
        th["droughts_count"] += droughts[h_tid]
        th["largest_lead_held"] = max(th["largest_lead_held"], max_h)

        if max_h >= 10:
            th["lead_10_chances"] += 1
            if h_won:
                th["lead_10_preserved"] += 1
            else:
                th["largest_blown_lead"] = max(th["largest_blown_lead"], max_h)

        if max_a >= 10:
            th["trail_10_chances"] += 1
            if h_won:
                th["trail_10_comebacks"] += 1
                th["largest_comeback_win"] = max(th["largest_comeback_win"], max_a)

        # Update Away
        ta = team_stats[a_tid]
        ta["games"] += 1
        ta["runs_gen_8"] += runs[a_tid]["8_0"]
        ta["runs_gen_10"] += runs[a_tid]["10_0"]
        ta["runs_gen_12"] += runs[a_tid]["12_0"]
        ta["runs_con_8"] += runs[h_tid]["8_0"]
        ta["droughts_count"] += droughts[a_tid]
        ta["largest_lead_held"] = max(ta["largest_lead_held"], max_a)

        if max_a >= 10:
            ta["lead_10_chances"] += 1
            if not h_won:
                ta["lead_10_preserved"] += 1
            else:
                ta["largest_blown_lead"] = max(ta["largest_blown_lead"], max_a)

        if max_h >= 10:
            ta["trail_10_chances"] += 1
            if not h_won:
                ta["trail_10_comebacks"] += 1
                ta["largest_comeback_win"] = max(ta["largest_comeback_win"], max_h)

    # Compile Final Rates
    compiled_teams = {}
    for tid, st in team_stats.items():
        g = st["games"]
        if g == 0:
            continue

        gen_rate = st["runs_gen_8"] / g
        con_rate = st["runs_con_8"] / g
        net_run_margin = gen_rate - con_rate

        pres_rate = (st["lead_10_preserved"] / st["lead_10_chances"]) if st["lead_10_chances"] > 0 else 1.0
        comeback_rate = (st["trail_10_comebacks"] / st["trail_10_chances"]) if st["trail_10_chances"] > 0 else 0.0

        compiled_teams[str(tid)] = {
            "team_id": tid,
            "games_evaluated": g,
            "scoring_runs": {
                "runs_8_0_per_game": round(gen_rate, 2),
                "runs_10_0_per_game": round(st["runs_gen_10"] / g, 2),
                "runs_12_0_per_game": round(st["runs_gen_12"] / g, 2),
                "runs_conceded_per_game": round(con_rate, 2),
                "net_run_margin_per_game": round(net_run_margin, 2),
            },
            "scoring_droughts": {
                "droughts_3min_per_game": round(st["droughts_count"] / g, 2),
            },
            "lead_volatility": {
                "double_digit_lead_preservation_pct": round(pres_rate * 100.0, 1),
                "double_digit_deficit_comeback_pct": round(comeback_rate * 100.0, 1),
                "largest_comeback_win": st["largest_comeback_win"],
                "largest_blown_lead": st["largest_blown_lead"],
            },
        }

    return compiled_teams


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: PBP Momentum, Runs & Droughts")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Computing Momentum Profiles for Season: {season} ---")
        teams = process_season_momentum(season)
        if not teams:
            continue

        payload = {
            "season": season,
            "team_count": len(teams),
            "teams": teams,
        }

        out_path = os.path.join("data", "processed", "features", f"momentum_and_runs_{season}.json")
        write_json(out_path, payload)
        logger.info(f"Saved {len(teams)} team momentum profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Momentum & run modeling complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()