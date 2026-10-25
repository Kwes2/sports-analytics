"""
scripts/testing/test_metric_stickiness.py
NBA Analytics Platform - Metric Reliability & Stickiness Tester

Calculates the Pearson Correlation Coefficient (r) between a 
rolling 5-game average (Games 1-5) and the subsequent game (Game 6).
This proves which metrics measure repeatable skill (Signal) vs random variance (Noise).

Runs exclusively on the complete 2025-26 season to maximize statistical sample size.
"""

import glob
import json
import logging
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("StickinessTest")

SEASON = "2025-26"
WINDOW_SIZE = 5
MIN_PLAYER_MINUTES = 10.0  # Exclude garbage-time games from correlation math

SELF_CREATION_KEYWORDS = [
    "pullup", "pull-up", "step back", "stepback", "fadeaway",
    "driving", "floating", "floater", "turnaround", "hook shot",
    "running pull", "running jump shot", "running floater"
]

def load_json(filepath: str) -> Any:
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def is_self_created(action_type: str, zone_basic: str) -> bool:
    act_lower = action_type.lower()
    for kw in SELF_CREATION_KEYWORDS:
        if kw in act_lower:
            return True
    if "corner 3" in zone_basic.lower():
        return False
    if "layup" in act_lower and "driving" not in act_lower:
        return False
    if "jump shot" not in act_lower:
        return True
    return False

def parse_clock_seconds(clock_str: str) -> float:
    if not clock_str:
        return 0.0
    m = re.search(r"PT(\d+)M([\d\.]+)S", clock_str)
    if m:
        return float(m.group(1)) * 60.0 + float(m.group(2))
    return 0.0

# ---------------------------------------------------------------------------
# Data Assemblers
# ---------------------------------------------------------------------------
def assemble_game_level_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Builds a massive game-by-game dataframe for every player and team."""
    logger.info("1. Loading Box Scores...")
    df_players = pd.DataFrame(load_json(os.path.join("data", "raw", "game_logs", f"player_{SEASON}.json")))
    df_teams = pd.DataFrame(load_json(os.path.join("data", "raw", "game_logs", f"team_{SEASON}.json")))

    if df_players.empty or df_teams.empty:
        logger.error("Missing raw logs. Run ingestion first.")
        sys.exit(1)

    # --- TEAM PAIRING (For Opponent Stats) ---
    team_pairs = pd.merge(df_teams, df_teams, on="GAME_ID", suffixes=("", "_OPP"))
    df_t = team_pairs[team_pairs["TEAM_ID"] != team_pairs["TEAM_ID_OPP"]].copy()

    # Base Team Possessions
    df_t["POSS"] = 0.96 * (df_t["FGA"] + 0.44 * df_t["FTA"] - df_t["OREB"] + df_t["TOV"])
    df_t["OPP_POSS"] = 0.96 * (df_t["FGA_OPP"] + 0.44 * df_t["FTA_OPP"] - df_t["OREB_OPP"] + df_t["TOV_OPP"])

    # --- SPATIAL SHOTS PARSING ---
    logger.info("2. Parsing 200,000+ Spatial Shots for Game-Level Action Types...")
    shot_files = glob.glob(os.path.join("data", "raw", "shots", SEASON, "*.json"))
    player_game_shots = defaultdict(lambda: {"rim_fga": 0, "sc_fga": 0, "total_fga": 0})
    
    for f in shot_files:
        for s in load_json(f):
            gid = str(s.get("GAME_ID"))
            pid = s.get("PLAYER_ID")
            if not gid or not pid: continue
            
            zb = s.get("SHOT_ZONE_BASIC", "")
            act = str(s.get("ACTION_TYPE", ""))
            
            player_game_shots[(gid, pid)]["total_fga"] += 1
            if zb == "Restricted Area":
                player_game_shots[(gid, pid)]["rim_fga"] += 1
            if is_self_created(act, zb):
                player_game_shots[(gid, pid)]["sc_fga"] += 1

    # --- PBP MOMENTUM PARSING ---
    logger.info("3. Parsing Play-by-Play for Game-Level Momentum/Runs...")
    pbp_files = glob.glob(os.path.join("data", "raw", "pbp", SEASON, "*.json"))
    team_game_pbp = defaultdict(lambda: {"runs_8_0": 0, "droughts_3min": 0})

    for f in pbp_files:
        events = load_json(f)
        gid = os.path.splitext(os.path.basename(f))[0]
        tids = list({e["team_id"] for e in events if e.get("team_id") and e["team_id"] > 0})
        if len(tids) < 2: continue
        
        score_events = []
        prev_h, prev_a = 0, 0
        h_tid, a_tid = tids[0], tids[1]

        for e in events:
            sh = e.get("score_home")
            sa = e.get("score_away")
            clock_sec = parse_clock_seconds(e.get("clock"))
            period = int(e.get("period", 1))
            elapsed = ((period - 1) * 720.0) + (720.0 - clock_sec) if period <= 4 else 2880.0 + ((period - 5) * 300.0) + (300.0 - clock_sec)
            
            if sh and sh.isdigit() and sa and sa.isdigit():
                cur_h, cur_a = int(sh), int(sa)
                if cur_h > prev_h or cur_a > prev_a:
                    pts_h = cur_h - prev_h
                    pts_a = cur_a - prev_a
                    score_events.append({
                        "elapsed": elapsed,
                        "team": h_tid if pts_h > 0 else a_tid,
                        "pts": pts_h if pts_h > 0 else pts_a
                    })
                    prev_h, prev_a = cur_h, cur_a

        # Calculate Runs & Droughts
        streak_team = None
        streak_pts = 0
        prev_time = {h_tid: 0.0, a_tid: 0.0}

        for ev in score_events:
            st = ev["team"]
            pts = ev["pts"]
            
            # Drought check
            if ev["elapsed"] - prev_time[st] >= 180.0 and prev_time[st] > 0:
                team_game_pbp[(gid, st)]["droughts_3min"] += 1
            prev_time[st] = ev["elapsed"]

            # Run check
            if st == streak_team:
                streak_pts += pts
            else:
                if streak_team and streak_pts >= 8:
                    team_game_pbp[(gid, streak_team)]["runs_8_0"] += 1
                streak_team = st
                streak_pts = pts
        
        if streak_team and streak_pts >= 8:
            team_game_pbp[(gid, streak_team)]["runs_8_0"] += 1

    # --- TEAM METRICS CALCULATION ---
    logger.info("4. Calculating Game-by-Game Metrics...")
    df_t["GAME_DATE_DT"] = pd.to_datetime(df_t["GAME_DATE"])
    
    df_t["PACE"] = (df_t["POSS"] / (df_t["MIN"] / 5.0)) * 48.0
    df_t["ORTG"] = (df_t["PTS"] / df_t["POSS"]) * 100.0
    df_t["DRTG"] = (df_t["PTS_OPP"] / df_t["OPP_POSS"]) * 100.0
    df_t["NETRTG"] = df_t["ORTG"] - df_t["DRTG"]
    df_t["EFG_PCT"] = (df_t["FGM"] + 0.5 * df_t["FG3M"]) / df_t["FGA"]
    df_t["OPP_EFG_PCT"] = (df_t["FGM_OPP"] + 0.5 * df_t["FG3M_OPP"]) / df_t["FGA_OPP"]
    df_t["ORB_PCT"] = df_t["OREB"] / (df_t["OREB"] + df_t["DREB_OPP"])
    df_t["TOV_PCT"] = df_t["TOV"] / (df_t["FGA"] + 0.44 * df_t["FTA"] + df_t["TOV"])
    
    # Map PBP Team Stats
    df_t["RUNS_8_0"] = df_t.apply(lambda r: team_game_pbp.get((r["GAME_ID"], r["TEAM_ID"]), {}).get("runs_8_0", 0), axis=1)
    df_t["DROUGHTS"] = df_t.apply(lambda r: team_game_pbp.get((r["GAME_ID"], r["TEAM_ID"]), {}).get("droughts_3min", 0), axis=1)

    df_t.replace([np.inf, -np.inf], np.nan, inplace=True)

    # --- PLAYER METRICS CALCULATION ---
    df_p = df_players[df_players["MIN"] >= MIN_PLAYER_MINUTES].copy()
    df_p["GAME_DATE_DT"] = pd.to_datetime(df_p["GAME_DATE"])

    # Build maps for Oliver formulas
    tm_stats = df_t.set_index(["GAME_ID", "TEAM_ID"]).to_dict(orient="index")

    records = []
    for _, r in df_p.iterrows():
        gid = r["GAME_ID"]
        tid = r["TEAM_ID"]
        pid = r["PLAYER_ID"]
        tm = tm_stats.get((gid, tid))
        if not tm: continue

        p_min = float(r["MIN"])
        tm_min_per_player = tm["MIN"] / 5.0
        p_poss = tm["POSS"] * (p_min / tm_min_per_player)
        poss_factor = 100.0 / p_poss if p_poss > 0 else 0

        # Usage
        usg_denom = p_min * (tm["FGA"] + 0.44 * tm["FTA"] + tm["TOV"])
        usg_num = (r["FGA"] + 0.44 * r["FTA"] + r["TOV"]) * tm_min_per_player
        usg = (100.0 * usg_num / usg_denom) if usg_denom > 0 else np.nan

        # TS & eFG
        ts_denom = 2.0 * (r["FGA"] + 0.44 * r["FTA"])
        ts = r["PTS"] / ts_denom if ts_denom > 0 else np.nan
        efg = (r["FGM"] + 0.5 * r["FG3M"]) / r["FGA"] if r["FGA"] > 0 else np.nan

        # Oliver Floor Rates
        ast_denom = ((p_min / tm_min_per_player) * tm["FGM"]) - r["FGM"]
        ast_pct = (100.0 * r["AST"] / ast_denom) if ast_denom > 0 else 0.0

        orb_denom = p_min * (tm["OREB"] + tm["DREB_OPP"])
        orb_pct = (100.0 * (r["OREB"] * tm_min_per_player) / orb_denom) if orb_denom > 0 else 0.0

        dreb_denom = p_min * (tm["DREB"] + tm["OREB_OPP"])
        dreb_pct = (100.0 * (r["DREB"] * tm_min_per_player) / dreb_denom) if dreb_denom > 0 else 0.0

        # Spatial
        shots = player_game_shots.get((gid, pid), {"rim_fga": 0, "sc_fga": 0, "total_fga": 0})
        fga = shots["total_fga"]
        rim_rate = shots["rim_fga"] / fga if fga > 0 else np.nan
        sc_rate = shots["sc_fga"] / fga if fga > 0 else np.nan

        records.append({
            "PLAYER_ID": pid,
            "PLAYER_NAME": r["PLAYER_NAME"],
            "GAME_DATE_DT": r["GAME_DATE_DT"],
            "USG_PCT": usg,
            "TS_PCT": ts,
            "EFG_PCT": efg,
            "AST_PCT": ast_pct,
            "ORB_PCT": orb_pct,
            "DREB_PCT": dreb_pct,
            "PTS_100": r["PTS"] * poss_factor,
            "AST_100": r["AST"] * poss_factor,
            "STOCK_100": (r["STL"] + r["BLK"]) * poss_factor,
            "RIM_PRESSURE": rim_rate,
            "SELF_CREATION": sc_rate,
            "PASS_SHOT_RATIO": r["AST"] / r["FGA"] if r["FGA"] > 0 else np.nan,
            "FOUL_DRAWING": r["FTA"] / r["PF"] if r["PF"] > 0 else r["FTA"]
        })

    df_p_calc = pd.DataFrame(records).replace([np.inf, -np.inf], np.nan)
    return df_t, df_p_calc

# ---------------------------------------------------------------------------
# Stickiness Correlation Engine
# ---------------------------------------------------------------------------
def run_stickiness_test(df: pd.DataFrame, entity_col: str, metrics: List[str]) -> List[Dict[str, Any]]:
    df = df.sort_values([entity_col, "GAME_DATE_DT"]).copy()
    results = []

    for metric in metrics:
        if metric not in df.columns: continue
        
        # Calculate Rolling 5-Game Mean, Shifted by 1 (Predicting the NEXT game)
        df[f"{metric}_rolling5"] = df.groupby(entity_col)[metric].transform(
            lambda x: x.rolling(window=WINDOW_SIZE, min_periods=WINDOW_SIZE).mean().shift(1)
        )
        
        # Drop rows where we don't have both the prediction and the actual result
        valid_subset = df.dropna(subset=[metric, f"{metric}_rolling5"])
        n_sample = len(valid_subset)
        
        if n_sample > 100:
            r = np.corrcoef(valid_subset[metric], valid_subset[f"{metric}_rolling5"])[0, 1]
            results.append({
                "Metric": metric,
                "Pearson_R": round(r, 4),
                "Sample_Size": n_sample
            })
            
    return sorted(results, key=lambda x: x["Pearson_R"], reverse=True)


def main():
    logger.info("==================================================")
    logger.info("NBA METRIC STICKINESS & RELIABILITY TESTER")
    logger.info(f"Targeting Season: {SEASON} (Rolling Window: {WINDOW_SIZE} Games)")
    logger.info("==================================================")

    df_teams, df_players = assemble_game_level_data()

    team_metrics = ["PACE", "ORTG", "DRTG", "NETRTG", "EFG_PCT", "OPP_EFG_PCT", "ORB_PCT", "TOV_PCT", "RUNS_8_0", "DROUGHTS"]
    player_metrics = [
        "USG_PCT", "TS_PCT", "EFG_PCT", "AST_PCT", "ORB_PCT", "DREB_PCT", 
        "PTS_100", "AST_100", "STOCK_100", "RIM_PRESSURE", "SELF_CREATION",
        "PASS_SHOT_RATIO", "FOUL_DRAWING"
    ]

    logger.info("\n--- Calculating Player Metric Stickiness ---")
    player_results = run_stickiness_test(df_players, "PLAYER_ID", player_metrics)
    
    print("\n[PLAYER METRICS: SIGNAL VS NOISE]")
    print(f"{'Metric':<20} | {'Pearson (r)':<12} | {'Sample Size':<12} | {'Verdict'}")
    print("-" * 65)
    for res in player_results:
        r = res['Pearson_R']
        if r >= 0.50: verdict = "🔥 HIGH SIGNAL (Sticky/Role)"
        elif r >= 0.25: verdict = "📊 MODERATE (Volume/Habit)"
        else: verdict = "🎲 HIGH NOISE (Variance/Luck)"
        print(f"{res['Metric']:<20} | {r:<12.4f} | {res['Sample_Size']:<12} | {verdict}")

    logger.info("\n--- Calculating Team Metric Stickiness ---")
    team_results = run_stickiness_test(df_teams, "TEAM_ID", team_metrics)

    print("\n[TEAM METRICS: SIGNAL VS NOISE]")
    print(f"{'Metric':<20} | {'Pearson (r)':<12} | {'Sample Size':<12} | {'Verdict'}")
    print("-" * 65)
    for res in team_results:
        r = res['Pearson_R']
        if r >= 0.50: verdict = "🔥 HIGH SIGNAL (System/Style)"
        elif r >= 0.25: verdict = "📊 MODERATE (Execution)"
        else: verdict = "🎲 HIGH NOISE (Variance/Luck)"
        print(f"{res['Metric']:<20} | {r:<12.4f} | {res['Sample_Size']:<12} | {verdict}")

    print("\n==================================================")
    print("Testing Complete.")
    print("==================================================")

if __name__ == "__main__":
    main()