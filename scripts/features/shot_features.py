"""
scripts/features/shot_features.py
NBA Analytics Platform - Shot Creation & Spatial Science Engine

Analyzes play-by-play shot actions to compute:
1. Self-Creation Rate (SCR%) and Creation Efficiency Tax
2. Self-Created vs. Assisted/Off-Ball SMOE
3. Rim Pressure Rate (RPR) and Rim Finishing Premium
4. High-Leverage / Clutch Shot-Making (Q4/OT with <= 5:00 remaining)
5. Comprehensive Zone Profiles
"""

import glob
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger("ShotFeatures")

SEASONS = ["2025-26", "2026-27"]

# Keywords indicating self-created off-the-dribble shot creation
SELF_CREATION_KEYWORDS = [
    "pullup", "pull-up", "step back", "stepback", "fadeaway",
    "driving", "floating", "floater", "turnaround", "hook shot",
    "running pull", "running jump shot", "running floater"
]

# Keywords indicating assisted, cutting, or off-ball finishing
OFF_BALL_KEYWORDS = [
    "catch and shoot", "catch & shoot", "cutting", "cut",
    "dunk shot", "tip shot", "alley oop", "putback"
]

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


def classify_action(action_type: str, shot_zone_basic: str) -> str:
    """
    Classifies a shot as 'self_created' or 'assisted_off_ball'
    using action description semantics and spatial heuristics.
    """
    act_lower = action_type.lower()

    for kw in SELF_CREATION_KEYWORDS:
        if kw in act_lower:
            return "self_created"

    for kw in OFF_BALL_KEYWORDS:
        if kw in act_lower:
            return "assisted_off_ball"

    # Default heuristic: corner 3s without a pull-up keyword are catch-and-shoot
    if "Corner 3" in shot_zone_basic:
        return "assisted_off_ball"

    # Standard "Jump Shot" or driving layup without explicit pullup keyword
    if "layup" in act_lower and "driving" not in act_lower:
        return "assisted_off_ball"

    return "self_created" if "jump shot" not in act_lower else "assisted_off_ball"


def is_clutch_situation(period: int, minutes_remaining: int, seconds_remaining: int) -> bool:
    """
    Clutch Definition: 4th Quarter or Overtime, with 5:00 or less remaining.
    """
    if period >= 4:
        total_seconds = (minutes_remaining * 60) + seconds_remaining
        return total_seconds <= 300
    return False


# ---------------------------------------------------------------------------
# Core Aggregator
# ---------------------------------------------------------------------------
class ShotFeatureAccumulator:
    """Accumulates raw shot occurrences into empirical profiles."""

    def __init__(self, entity_id: int, name: str = "", team_id: int = 0):
        self.entity_id = entity_id
        self.name = name
        self.team_id = team_id

        self.total_fga = 0
        self.total_fgm = 0
        self.total_pts = 0
        self.total_xpts = 0.0

        # Self-Creation Breakdown
        self.sc_fga = 0
        self.sc_fgm = 0
        self.sc_pts = 0
        self.sc_xpts = 0.0

        # Assisted / Off-Ball Breakdown
        self.ast_fga = 0
        self.ast_fgm = 0
        self.ast_pts = 0
        self.ast_xpts = 0.0

        # Rim Tracking (Restricted Area)
        self.rim_fga = 0
        self.rim_fgm = 0

        # Clutch Tracking
        self.clutch_fga = 0
        self.clutch_fgm = 0
        self.clutch_pts = 0
        self.clutch_xpts = 0.0

        # Spatial Distribution & Hex Density Bins
        self.zones_fga = defaultdict(int)
        self.zones_fgm = defaultdict(int)
        self.spatial_bins = defaultdict(lambda: {"fga": 0, "fgm": 0, "fg3m": 0, "pts": 0})

    def record_shot(
        self,
        is_made: int,
        is_3pt: int,
        zone_basic: str,
        action_type: str,
        period: int,
        min_rem: int,
        sec_rem: int,
        zone_xpps: float,
        loc_x: Optional[float] = None,
        loc_y: Optional[float] = None,
    ) -> None:
        pts = (3 if is_3pt else 2) if is_made else 0
        xpts = zone_xpps

        self.total_fga += 1
        self.total_fgm += is_made
        self.total_pts += pts
        self.total_xpts += xpts

        self.zones_fga[zone_basic] += 1
        self.zones_fgm[zone_basic] += is_made

        # 2D Hex Density Binning (~2 ft grid cells)
        if loc_x is not None and loc_y is not None:
            bx = int(round(float(loc_x) / 20.0) * 20)
            by = int(round(float(loc_y) / 20.0) * 20)
            self.spatial_bins[(bx, by)]["fga"] += 1
            self.spatial_bins[(bx, by)]["fgm"] += is_made
            self.spatial_bins[(bx, by)]["fg3m"] += (1 if is_3pt and is_made else 0)
            self.spatial_bins[(bx, by)]["pts"] += pts

        # Rim
        if zone_basic == "Restricted Area":
            self.rim_fga += 1
            self.rim_fgm += is_made

        # Action Type Classification
        shot_class = classify_action(action_type, zone_basic)
        if shot_class == "self_created":
            self.sc_fga += 1
            self.sc_fgm += is_made
            self.sc_pts += pts
            self.sc_xpts += xpts
        else:
            self.ast_fga += 1
            self.ast_fgm += is_made
            self.ast_pts += pts
            self.ast_xpts += xpts

        # Clutch
        if is_clutch_situation(period, min_rem, sec_rem):
            self.clutch_fga += 1
            self.clutch_fgm += is_made
            self.clutch_pts += pts
            self.clutch_xpts += xpts

    def compile(self, baseline_rim_fg_pct: float) -> Dict[str, Any]:
        """Calculates final rates, premiums, and SMOE differentials."""
        fga = self.total_fga
        if fga == 0:
            return {}

        total_smoe = self.total_pts - self.total_xpts
        total_efg = self.total_pts / (2.0 * fga)
        shot_quality_xefg = self.total_xpts / (2.0 * fga)

        # Self-Creation Metrics
        sc_efg = (self.sc_pts / (2.0 * self.sc_fga)) if self.sc_fga > 0 else None
        ast_efg = (self.ast_pts / (2.0 * self.ast_fga)) if self.ast_fga > 0 else None
        sc_smoe_100 = (
            round(((self.sc_pts - self.sc_xpts) / self.sc_fga) * 100.0, 2)
            if self.sc_fga > 0
            else None
        )
        ast_smoe_100 = (
            round(((self.ast_pts - self.ast_xpts) / self.ast_fga) * 100.0, 2)
            if self.ast_fga > 0
            else None
        )

        creation_tax = (
            round(ast_efg - sc_efg, 4)
            if (ast_efg is not None and sc_efg is not None)
            else None
        )

        # Rim Pressure & Finishing
        rim_rate = round(self.rim_fga / fga, 4)
        rim_fg_pct = round(self.rim_fgm / self.rim_fga, 4) if self.rim_fga > 0 else None
        rim_finishing_premium = (
            round(rim_fg_pct - baseline_rim_fg_pct, 4)
            if rim_fg_pct is not None
            else None
        )

        # Clutch
        clutch_smoe = (
            round(self.clutch_pts - self.clutch_xpts, 2)
            if self.clutch_fga > 0
            else None
        )
        clutch_smoe_100 = (
            round(((self.clutch_pts - self.clutch_xpts) / self.clutch_fga) * 100.0, 2)
            if self.clutch_fga > 0
            else None
        )
        clutch_efg = (
            round(self.clutch_pts / (2.0 * self.clutch_fga), 4)
            if self.clutch_fga > 0
            else None
        )

        # Spatial Distribution & Zone FG%
        zone_profile = {}
        for z_name, z_count in self.zones_fga.items():
            z_made = self.zones_fgm[z_name]
            zone_profile[z_name] = {
                "attempts": z_count,
                "frequency": round(z_count / fga, 4),
                "fg_pct": round(z_made / z_count, 4) if z_count > 0 else 0.0,
            }

        # Compile density bins
        density_bins = [
            {
                "x": bx,
                "y": by,
                "fga": stats["fga"],
                "fgm": stats["fgm"],
                "fg_pct": round(stats["fgm"] / stats["fga"], 3),
                "efg_pct": round((stats["fgm"] + 0.5 * stats["fg3m"]) / stats["fga"], 3),
            }
            for (bx, by), stats in sorted(self.spatial_bins.items(), key=lambda item: item[1]["fga"], reverse=True)
        ]

        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "team_id": self.team_id,
            "density_bins": density_bins,
            "total_fga": fga,
            "actual_efg": round(total_efg, 4),
            "shot_quality_xefg": round(shot_quality_xefg, 4),
            "smoe_total": round(total_smoe, 2),
            "smoe_per_100": round((total_smoe / fga) * 100.0, 2),
            "creation_profile": {
                "self_created_fga": self.sc_fga,
                "self_creation_rate": round(self.sc_fga / fga, 4),
                "self_created_efg": round(sc_efg, 4) if sc_efg is not None else None,
                "self_created_smoe_per_100": sc_smoe_100,
                "assisted_fga": self.ast_fga,
                "assisted_efg": round(ast_efg, 4) if ast_efg is not None else None,
                "assisted_smoe_per_100": ast_smoe_100,
                "creation_efficiency_tax": creation_tax,
            },
            "rim_pressure": {
                "rim_attempts": self.rim_fga,
                "rim_pressure_rate": rim_rate,
                "rim_fg_pct": rim_fg_pct,
                "rim_finishing_premium": rim_finishing_premium,
            },
            "clutch_profile": {
                "clutch_fga": self.clutch_fga,
                "clutch_fgm": self.clutch_fgm,
                "clutch_efg": clutch_efg,
                "clutch_smoe_total": clutch_smoe,
                "clutch_smoe_per_100": clutch_smoe_100,
            },
            "zone_profile": zone_profile,
        }


# ---------------------------------------------------------------------------
# Feature Processor
# ---------------------------------------------------------------------------
def process_season_shots(
    season: str,
    zone_xpps_map: Dict[str, float],
    baseline_rim_fg_pct: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Parses all team shot JSONs for the season and returns compiled
    player and team shot feature objects.
    """
    shot_files = glob.glob(os.path.join("data", "raw", "shots", season, "*.json"))
    logger.info(f"Processing {len(shot_files)} shot files for {season}...")

    player_acc: Dict[int, ShotFeatureAccumulator] = {}
    team_acc: Dict[int, ShotFeatureAccumulator] = {}

    for filepath in shot_files:
        team_shots = load_json(filepath)
        for shot in team_shots:
            pid = shot.get("PLAYER_ID")
            tid = shot.get("TEAM_ID")
            pname = shot.get("PLAYER_NAME", "Unknown")
            is_made = int(shot.get("SHOT_MADE_FLAG", 0))
            shot_type = str(shot.get("SHOT_TYPE", ""))
            action_type = str(shot.get("ACTION_TYPE", ""))
            zone_basic = shot.get("SHOT_ZONE_BASIC", "Mid-Range")
            period = int(shot.get("PERIOD", 1))
            min_rem = int(shot.get("MINUTES_REMAINING", 0))
            sec_rem = int(shot.get("SECONDS_REMAINING", 0))

            is_3pt = 1 if "3PT" in shot_type else 0
            xpps = zone_xpps_map.get(zone_basic, 1.0)

            loc_x = shot.get("LOC_X")
            loc_y = shot.get("LOC_Y")

            # Player Accumulator
            if pid not in player_acc:
                player_acc[pid] = ShotFeatureAccumulator(entity_id=pid, name=pname, team_id=tid)
            player_acc[pid].record_shot(
                is_made, is_3pt, zone_basic, action_type, period, min_rem, sec_rem, xpps, loc_x, loc_y
            )

            # Team Accumulator
            if tid not in team_acc:
                team_acc[tid] = ShotFeatureAccumulator(entity_id=tid, name=f"Team {tid}", team_id=tid)
            team_acc[tid].record_shot(
                is_made, is_3pt, zone_basic, action_type, period, min_rem, sec_rem, xpps, loc_x, loc_y
            )

    compiled_players = {
        str(pid): acc.compile(baseline_rim_fg_pct) for pid, acc in player_acc.items()
    }
    compiled_teams = {
        str(tid): acc.compile(baseline_rim_fg_pct) for tid, acc in team_acc.items()
    }

    return compiled_players, compiled_teams


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: Shot Creation & Spatial Engine")
    logger.info("==================================================")

    # 1. Load Baselines
    baseline_path = os.path.join("data", "processed", "league_baselines.json")
    if not os.path.exists(baseline_path):
        raise FileNotFoundError(
            f"Baselines file not found at {baseline_path}. Run build_baselines.py first."
        )

    baselines = load_json(baseline_path)
    zones = baselines.get("spatial_shooting_benchmarks", {}).get("zones", {})
    zone_xpps_map = {z_name: meta["xpps"] for z_name, meta in zones.items()}
    baseline_rim_fg_pct = zones.get("Restricted Area", {}).get("fg_pct", 0.672)

    logger.info(f"Loaded {len(zone_xpps_map)} zone expected points benchmarks.")
    logger.info(f"Restricted Area FG% Benchmark Anchor: {baseline_rim_fg_pct:.4f}")

    for season in SEASONS:
        logger.info(f"--- Generating Shot Features for Season: {season} ---")
        players, teams = process_season_shots(
            season, zone_xpps_map, baseline_rim_fg_pct
        )

        feature_payload = {
            "season": season,
            "anchor_rim_fg_pct": baseline_rim_fg_pct,
            "player_count": len(players),
            "team_count": len(teams),
            "players": players,
            "teams": teams,
        }

        out_path = os.path.join("data", "processed", "features", f"shot_features_{season}.json")
        write_json(out_path, feature_payload)
        logger.info(f"Saved {len(players)} player & {len(teams)} team shot profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Shot feature generation completed successfully.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()