"""
scripts/build_baselines.py
NBA Analytics Platform - Dynamic Rolling Baseline Engine

Computes empirical spatial shot baselines and possession benchmarks
over the rolling most recent 1,000 NBA regular season games.
"""

import glob
import json
import logging
import os
import sys
from typing import Any, Dict, List, Set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger("NBABaselines")

TARGET_GAMES_WINDOW = 1000

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def load_json(filepath: str) -> Any:
    """Load JSON from disk."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath: str, data: Any) -> None:
    """Safely write JSON to disk atomically."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, filepath)


# ---------------------------------------------------------------------------
# Game Identification Engine
# ---------------------------------------------------------------------------
def get_rolling_game_ids(target_count: int = TARGET_GAMES_WINDOW) -> Set[str]:
    """
    Scans team game logs across 2025-26 and 2026-27, orders all games
    by GAME_DATE descending, and returns the set of the most recent unique GAME_IDs.
    """
    team_log_files = [
        os.path.join("data", "raw", "game_logs", "team_2026-27.json"),
        os.path.join("data", "raw", "game_logs", "team_2025-26.json"),
    ]

    all_team_logs = []
    for filepath in team_log_files:
        if os.path.exists(filepath):
            logs = load_json(filepath)
            all_team_logs.extend(logs)
            logger.info(f"Loaded {len(logs)} logs from {filepath}")
        else:
            logger.warning(f"File not found: {filepath}")

    if not all_team_logs:
        raise RuntimeError("No team game logs found. Run Step 1 ingestion first.")

    # Deduplicate games: map GAME_ID -> GAME_DATE
    games_map: Dict[str, str] = {}
    for entry in all_team_logs:
        game_id = str(entry.get("GAME_ID"))
        game_date = str(entry.get("GAME_DATE"))
        if game_id and game_date:
            games_map[game_id] = game_date

    # Sort descending by date
    sorted_games = sorted(games_map.items(), key=lambda item: item[1], reverse=True)
    selected_games = sorted_games[:target_count]
    selected_ids = {g[0] for g in selected_games}

    newest_date = selected_games[0][1] if selected_games else "N/A"
    oldest_date = selected_games[-1][1] if selected_games else "N/A"

    logger.info(
        f"Selected {len(selected_ids)} unique games spanning from {oldest_date} to {newest_date}."
    )
    return selected_ids


# ---------------------------------------------------------------------------
# Possession & Four Factors Aggregator
# ---------------------------------------------------------------------------
def compute_possession_baselines(target_game_ids: Set[str]) -> Dict[str, Any]:
    """
    Computes total possessions, pace, points per possession, and Four Factors
    across both teams for the target 1,000 games.
    """
    team_log_files = [
        os.path.join("data", "raw", "game_logs", "team_2026-27.json"),
        os.path.join("data", "raw", "game_logs", "team_2025-26.json"),
    ]

    tot_pts = 0
    tot_fga = 0
    tot_fgm = 0
    tot_fg3m = 0
    tot_fta = 0
    tot_oreb = 0
    tot_dreb = 0
    tot_tov = 0
    tot_min = 0
    games_counted = set()

    for filepath in team_log_files:
        if not os.path.exists(filepath):
            continue
        for row in load_json(filepath):
            gid = str(row.get("GAME_ID"))
            if gid in target_game_ids:
                games_counted.add(gid)
                tot_pts += row.get("PTS", 0) or 0
                tot_fga += row.get("FGA", 0) or 0
                tot_fgm += row.get("FGM", 0) or 0
                tot_fg3m += row.get("FG3M", 0) or 0
                tot_fta += row.get("FTA", 0) or 0
                tot_oreb += row.get("OREB", 0) or 0
                tot_dreb += row.get("DREB", 0) or 0
                tot_tov += row.get("TOV", 0) or 0
                tot_min += row.get("MIN", 0) or 0

    # Dean Oliver possession formula:
    # Possessions = 0.96 * (FGA + 0.44 * FTA - OREB + TOV)
    total_possessions = 0.96 * (tot_fga + 0.44 * tot_fta - tot_oreb + tot_tov)

    # 48 minutes per team = 96 player-minutes per regulation game
    # tot_min tracks aggregate minutes across both teams (normally 480 per non-OT game)
    pace_per_48 = ((total_possessions / 2.0) / (tot_min / 10.0)) * 48.0 if tot_min > 0 else 0.0
    pts_per_100_poss = (tot_pts / total_possessions) * 100 if total_possessions > 0 else 0.0
    efg_pct = (tot_fgm + 0.5 * tot_fg3m) / tot_fga if tot_fga > 0 else 0.0
    tov_pct = (tot_tov / (tot_fga + 0.44 * tot_fta + tot_tov)) if (tot_fga + 0.44 * tot_fta + tot_tov) > 0 else 0.0
    orb_pct = tot_oreb / (tot_oreb + tot_dreb) if (tot_oreb + tot_dreb) > 0 else 0.0
    ft_rate = tot_fta / tot_fga if tot_fga > 0 else 0.0

    return {
        "games_evaluated": len(games_counted),
        "total_possessions": round(total_possessions, 1),
        "pace_per_48": round(pace_per_48, 2),
        "offensive_rating_baseline": round(pts_per_100_poss, 2),
        "four_factors": {
            "effective_fg_pct": round(efg_pct, 4),
            "turnover_pct": round(tov_pct, 4),
            "offensive_rebound_pct": round(orb_pct, 4),
            "free_throw_rate": round(ft_rate, 4),
        },
    }


# ---------------------------------------------------------------------------
# Spatial Shot Chart Zone Aggregator
# ---------------------------------------------------------------------------
def compute_spatial_baselines(target_game_ids: Set[str]) -> Dict[str, Any]:
    """
    Parses all team shot files for 2025-26 and 2026-27, filters shots belonging
    to the target 1,000 games, and calculates zone efficiency and expected points.
    """
    shot_files = glob.glob(os.path.join("data", "raw", "shots", "*", "*.json"))
    logger.info(f"Scanning {len(shot_files)} team shot chart files...")

    # Data structure for zone accumulation
    zones: Dict[str, Dict[str, int]] = {
        "Restricted Area": {"fga": 0, "fgm": 0, "fg3m": 0, "pts": 0},
        "In The Paint (Non-RA)": {"fga": 0, "fgm": 0, "fg3m": 0, "pts": 0},
        "Mid-Range": {"fga": 0, "fgm": 0, "fg3m": 0, "pts": 0},
        "Left Corner 3": {"fga": 0, "fgm": 0, "fg3m": 0, "pts": 0},
        "Right Corner 3": {"fga": 0, "fgm": 0, "fg3m": 0, "pts": 0},
        "Above the Break 3": {"fga": 0, "fgm": 0, "fg3m": 0, "pts": 0},
        "Backcourt": {"fga": 0, "fgm": 0, "fg3m": 0, "pts": 0},
    }

    # Distance bins (feet)
    distance_bins: Dict[str, Dict[str, int]] = {
        "0-4": {"fga": 0, "fgm": 0, "pts": 0},
        "5-9": {"fga": 0, "fgm": 0, "pts": 0},
        "10-14": {"fga": 0, "fgm": 0, "pts": 0},
        "15-19": {"fga": 0, "fgm": 0, "pts": 0},
        "20-24": {"fga": 0, "fgm": 0, "pts": 0},
        "25-29": {"fga": 0, "fgm": 0, "pts": 0},
        "30+": {"fga": 0, "fgm": 0, "pts": 0},
    }

    total_shots_parsed = 0
    shots_in_window = 0

    for filepath in shot_files:
        team_shots = load_json(filepath)
        for shot in team_shots:
            total_shots_parsed += 1
            gid = str(shot.get("GAME_ID"))
            if gid not in target_game_ids:
                continue

            shots_in_window += 1
            zone_basic = shot.get("SHOT_ZONE_BASIC", "Mid-Range")
            is_made = int(shot.get("SHOT_MADE_FLAG", 0))
            shot_type = str(shot.get("SHOT_TYPE", ""))
            shot_dist = int(shot.get("SHOT_DISTANCE", 0))

            is_3pt = 1 if "3PT" in shot_type else 0
            shot_pts = (3 if is_3pt else 2) if is_made else 0

            # Normalize Zone Category
            if zone_basic not in zones:
                zone_basic = "Mid-Range"

            zones[zone_basic]["fga"] += 1
            zones[zone_basic]["fgm"] += is_made
            zones[zone_basic]["fg3m"] += (1 if is_3pt and is_made else 0)
            zones[zone_basic]["pts"] += shot_pts

            # Bin Distance
            if shot_dist <= 4:
                dist_key = "0-4"
            elif shot_dist <= 9:
                dist_key = "5-9"
            elif shot_dist <= 14:
                dist_key = "10-14"
            elif shot_dist <= 19:
                dist_key = "15-19"
            elif shot_dist <= 24:
                dist_key = "20-24"
            elif shot_dist <= 29:
                dist_key = "25-29"
            else:
                dist_key = "30+"

            distance_bins[dist_key]["fga"] += 1
            distance_bins[dist_key]["fgm"] += is_made
            distance_bins[dist_key]["pts"] += shot_pts

    logger.info(
        f"Filtered {shots_in_window:,} window shots from {total_shots_parsed:,} total raw shots."
    )

    # Compute final metrics per zone
    zone_results = {}
    for zone_name, stats in zones.items():
        fga = stats["fga"]
        fgm = stats["fgm"]
        fg3m = stats["fg3m"]
        pts = stats["pts"]

        freq = (fga / shots_in_window) if shots_in_window > 0 else 0.0
        fg_pct = (fgm / fga) if fga > 0 else 0.0
        efg_pct = (fgm + 0.5 * fg3m) / fga if fga > 0 else 0.0
        xpps = (pts / fga) if fga > 0 else 0.0

        zone_results[zone_name] = {
            "attempts": fga,
            "made": fgm,
            "frequency": round(freq, 4),
            "fg_pct": round(fg_pct, 4),
            "efg_pct": round(efg_pct, 4),
            "xpps": round(xpps, 4),  # Expected Points Per Shot
        }

    # Compute distance bin results
    dist_results = {}
    for dist_label, stats in distance_bins.items():
        fga = stats["fga"]
        fgm = stats["fgm"]
        pts = stats["pts"]
        fg_pct = (fgm / fga) if fga > 0 else 0.0
        xpps = (pts / fga) if fga > 0 else 0.0

        dist_results[dist_label] = {
            "attempts": fga,
            "made": fgm,
            "frequency": round((fga / shots_in_window) if shots_in_window > 0 else 0.0, 4),
            "fg_pct": round(fg_pct, 4),
            "xpps": round(xpps, 4),
        }

    return {
        "sample_shots_evaluated": shots_in_window,
        "zones": zone_results,
        "distance_bins": dist_results,
    }


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info(f"Computing Rolling {TARGET_GAMES_WINDOW}-Game League Baselines")
    logger.info("==================================================")

    # 1. Identify the 1,000 most recent unique games
    target_game_ids = get_rolling_game_ids(TARGET_GAMES_WINDOW)

    # 2. Possession & Four Factors baselines
    possession_model = compute_possession_baselines(target_game_ids)

    # 3. Spatial Shot baselines
    spatial_model = compute_spatial_baselines(target_game_ids)

    # Combine into unified artifact
    league_baselines = {
        "metadata": {
            "window_size_games": TARGET_GAMES_WINDOW,
            "actual_games_found": len(target_game_ids),
        },
        "possession_benchmarks": possession_model,
        "spatial_shooting_benchmarks": spatial_model,
    }

    output_path = os.path.join("data", "processed", "league_baselines.json")
    write_json(output_path, league_baselines)

    logger.info("==================================================")
    logger.info(f"Baselines successfully exported to: {output_path}")
    logger.info(f"Pace Baseline: {possession_model['pace_per_48']} poss/48m")
    logger.info(f"Offensive Rating Baseline: {possession_model['offensive_rating_baseline']} pts/100 poss")
    logger.info(f"Restricted Area xPPS: {spatial_model['zones']['Restricted Area']['xpps']}")
    logger.info(f"Above Break 3 xPPS: {spatial_model['zones']['Above the Break 3']['xpps']}")
    logger.info("==================================================")


if __name__ == "__main__":
    main()