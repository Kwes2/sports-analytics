"""
scripts/features/spatial_hot_cold.py
NBA Analytics Platform - Spatial Hot/Cold & Defensive Leak Engine

Computes:
1. Player Hot/Cold Zone Matrix (Delta FG% vs 1,000-game rolling baseline)
2. Player Corner 3 Specialist Premium
3. Team Defensive Hot/Cold Allowed Matrix
4. Team Opponent Paint Funnel Rate & Rim Denial Efficiency
"""

import glob
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("SpatialHotCold")

SEASONS = ["2025-26", "2026-27"]
MIN_ZONE_ATTEMPTS = 5
HOT_THRESHOLD = 0.04
COLD_THRESHOLD = -0.04

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
# Core Spatial Processing
# ---------------------------------------------------------------------------
def process_spatial_hot_cold(
    season: str,
    baseline_zones: Dict[str, Dict[str, Any]],
    baseline_rim_freq: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    shot_files = glob.glob(os.path.join("data", "raw", "shots", season, "*.json"))
    team_log_file = os.path.join("data", "raw", "game_logs", f"team_{season}.json")

    if not shot_files or not os.path.exists(team_log_file):
        logger.error(f"Missing shot files or team logs for {season}.")
        return {}, {}

    # 1. Map GAME_ID -> {offense_team_id: defense_team_id}
    df_teams = pd.DataFrame(load_json(team_log_file))
    team_pairs = pd.merge(df_teams, df_teams, on="GAME_ID", suffixes=("", "_OPP"))
    paired = team_pairs[team_pairs["TEAM_ID"] != team_pairs["TEAM_ID_OPP"]]
    game_defender_map = defaultdict(dict)
    for _, r in paired.iterrows():
        game_defender_map[str(r["GAME_ID"])][int(r["TEAM_ID"])] = int(r["TEAM_ID_OPP"])

    # 2. Aggregators
    # player_id -> { name, team_id, zones: { zone_name: {fga, fgm, fg3m} } }
    player_shots: Dict[int, Dict[str, Any]] = defaultdict(
        lambda: {"name": "", "team_id": 0, "zones": defaultdict(lambda: {"fga": 0, "fgm": 0, "fg3m": 0})}
    )
    # team_id -> { name, zones_defended: { zone_name: {fga, fgm, fg3m} } }
    team_def_shots: Dict[int, Dict[str, Any]] = defaultdict(
        lambda: {"zones_defended": defaultdict(lambda: {"fga": 0, "fgm": 0, "fg3m": 0})}
    )

    for filepath in shot_files:
        shots = load_json(filepath)
        for s in shots:
            pid = s.get("PLAYER_ID")
            off_tid = int(s.get("TEAM_ID", 0))
            gid = str(s.get("GAME_ID"))
            def_tid = game_defender_map.get(gid, {}).get(off_tid)

            pname = s.get("PLAYER_NAME", "Unknown")
            is_made = int(s.get("SHOT_MADE_FLAG", 0))
            shot_type = str(s.get("SHOT_TYPE", ""))
            zone_basic = s.get("SHOT_ZONE_BASIC", "Mid-Range")
            is_3pt = 1 if "3PT" in shot_type else 0

            # Player
            player_shots[pid]["name"] = pname
            player_shots[pid]["team_id"] = off_tid
            player_shots[pid]["zones"][zone_basic]["fga"] += 1
            player_shots[pid]["zones"][zone_basic]["fgm"] += is_made
            player_shots[pid]["zones"][zone_basic]["fg3m"] += (1 if is_3pt and is_made else 0)

            # Team Defense
            if def_tid:
                team_def_shots[def_tid]["zones_defended"][zone_basic]["fga"] += 1
                team_def_shots[def_tid]["zones_defended"][zone_basic]["fgm"] += is_made
                team_def_shots[def_tid]["zones_defended"][zone_basic]["fg3m"] += (1 if is_3pt and is_made else 0)

    # 3. Format Player Spatial Results
    player_results = {}
    for pid, data in player_shots.items():
        zone_analysis = {}
        total_corner3_fga = 0
        total_corner3_fgm = 0
        total_above_break_fga = 0
        total_above_break_fgm = 0

        for zone_name, b_meta in baseline_zones.items():
            z_stats = data["zones"].get(zone_name, {"fga": 0, "fgm": 0, "fg3m": 0})
            fga = z_stats["fga"]
            fgm = z_stats["fgm"]
            base_fg_pct = b_meta.get("fg_pct", 0.0)

            if "Corner 3" in zone_name:
                total_corner3_fga += fga
                total_corner3_fgm += fgm
            elif "Above the Break" in zone_name:
                total_above_break_fga += fga
                total_above_break_fgm += fgm

            if fga >= MIN_ZONE_ATTEMPTS:
                player_fg_pct = fgm / fga
                delta = player_fg_pct - base_fg_pct
                if delta >= HOT_THRESHOLD:
                    status = "HOT"
                elif delta <= COLD_THRESHOLD:
                    status = "COLD"
                else:
                    status = "NEUTRAL"
            else:
                player_fg_pct = (fgm / fga) if fga > 0 else None
                delta = None
                status = "INSUFFICIENT_VOLUME"

            zone_analysis[zone_name] = {
                "attempts": fga,
                "made": fgm,
                "fg_pct": round(player_fg_pct, 4) if player_fg_pct is not None else None,
                "baseline_fg_pct": round(base_fg_pct, 4),
                "delta_fg_pct": round(delta, 4) if delta is not None else None,
                "status": status,
            }

        # Corner 3 Specialist Premium
        corner3_efg = (total_corner3_fgm * 1.5) / total_corner3_fga if total_corner3_fga > 0 else None
        above_break_efg = (total_above_break_fgm * 1.5) / total_above_break_fga if total_above_break_fga > 0 else None
        corner3_premium = (
            round(corner3_efg - above_break_efg, 4)
            if (corner3_efg is not None and above_break_efg is not None)
            else None
        )

        player_results[str(pid)] = {
            "player_id": pid,
            "player_name": data["name"],
            "team_id": data["team_id"],
            "hot_cold_zones": zone_analysis,
            "corner_3_specialist_premium": corner3_premium,
        }

    # 4. Format Team Defensive Suppression Results
    team_results = {}
    for tid, data in team_def_shots.items():
        z_def = data["zones_defended"]
        total_def_shots = sum(z["fga"] for z in z_def.values())

        if total_def_shots == 0:
            continue

        zone_def_analysis = {}
        for zone_name, b_meta in baseline_zones.items():
            stats = z_def.get(zone_name, {"fga": 0, "fgm": 0})
            fga = stats["fga"]
            fgm = stats["fgm"]
            base_fg_pct = b_meta.get("fg_pct", 0.0)

            opp_fg_pct = (fgm / fga) if fga > 0 else 0.0
            delta = opp_fg_pct - base_fg_pct

            # For defense: allowing below baseline is LEAK_CONTAINED, above is DEFENSIVE_LEAK
            if delta >= HOT_THRESHOLD:
                def_status = "DEFENSIVE_LEAK"
            elif delta <= COLD_THRESHOLD:
                def_status = "LEAK_CONTAINED"
            else:
                def_status = "NEUTRAL"

            zone_def_analysis[zone_name] = {
                "opp_attempts": fga,
                "opp_made": fgm,
                "opp_fg_pct": round(opp_fg_pct, 4),
                "baseline_fg_pct": round(base_fg_pct, 4),
                "delta_allowed": round(delta, 4),
                "status": def_status,
            }

        # Paint Funnel Rate: Paint Non-RA / (Rim + Paint Non-RA)
        ra_fga = z_def.get("Restricted Area", {}).get("fga", 0)
        paint_non_ra_fga = z_def.get("In The Paint (Non-RA)", {}).get("fga", 0)
        paint_denom = ra_fga + paint_non_ra_fga
        funnel_rate = (paint_non_ra_fga / paint_denom) if paint_denom > 0 else 0.0

        # Rim Denial Efficiency: Baseline Rim Freq - Opp Rim Freq Allowed
        opp_rim_freq = (ra_fga / total_def_shots) if total_def_shots > 0 else 0.0
        rim_denial = baseline_rim_freq - opp_rim_freq

        team_results[str(tid)] = {
            "team_id": tid,
            "total_shots_defended": total_def_shots,
            "defensive_hot_cold_allowed": zone_def_analysis,
            "opponent_paint_funnel_rate": round(funnel_rate, 4),
            "rim_denial_efficiency": round(rim_denial, 4),
        }

    return player_results, team_results


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: Spatial Hot/Cold & Defensive Leaks")
    logger.info("==================================================")

    baseline_path = os.path.join("data", "processed", "league_baselines.json")
    if not os.path.exists(baseline_path):
        raise FileNotFoundError("Run build_baselines.py first.")

    baselines = load_json(baseline_path)
    baseline_zones = baselines.get("spatial_shooting_benchmarks", {}).get("zones", {})
    baseline_rim_freq = baseline_zones.get("Restricted Area", {}).get("frequency", 0.30)

    for season in SEASONS:
        logger.info(f"--- Processing Spatial Hot/Cold for Season: {season} ---")
        players, teams = process_spatial_hot_cold(season, baseline_zones, baseline_rim_freq)

        payload = {
            "season": season,
            "player_count": len(players),
            "team_count": len(teams),
            "players": players,
            "teams": teams,
        }

        out_path = os.path.join("data", "processed", "features", f"spatial_hot_cold_{season}.json")
        write_json(out_path, payload)
        logger.info(f"Saved {len(players)} player & {len(teams)} team spatial profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Spatial hot/cold feature generation complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()