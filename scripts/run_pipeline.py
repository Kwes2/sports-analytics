"""
scripts/run_pipeline.py
NBA Analytics Platform - Master Orchestrator CLI

Options:
python scripts/run_pipeline.py --sync         # Pulls new games, missing PBPs, and recalculates everything
python scripts/run_pipeline.py                # Recalculates all features from current cache (fast, 25s)
python scripts/run_pipeline.py --only-synthesis # Recalculates percentiles & final store only (2s)
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from typing import List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Pipeline")


def run_stage(description: str, script_path: str) -> bool:
    if not os.path.exists(script_path):
        logger.error(f"Cannot find script: {script_path}")
        return False

    logger.info("==================================================")
    logger.info(f"▶ EXECUTING: {description}")
    logger.info(f"  Target: {script_path}")
    logger.info("==================================================")

    start_time = time.time()
    result = subprocess.run([sys.executable, script_path], check=False)
    elapsed = time.time() - start_time

    if result.returncode == 0:
        logger.info(f"✔ COMPLETED: {description} ({elapsed:.2f}s)\n")
        return True
    else:
        logger.error(f"✖ FAILED: {description} (Exit code: {result.returncode})\n")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="NBA Analytics Pipeline Orchestrator")
    parser.add_argument("--sync", action="store_true", help="Sync active season data (pull new games & missing PBP)")
    parser.add_argument("--only-synthesis", action="store_true", help="Re-run only Stage 3: Synthesis & Percentiles")

    args = parser.parse_args()

    pipeline_start = time.time()
    logger.info("==================================================")
    logger.info("NBA ANALYTICS PLATFORM - PIPELINE ORCHESTRATOR")
    logger.info("==================================================")

    stages_to_run: List[Tuple[str, str]] = []

    if args.only_synthesis:
        stages_to_run = [
            ("Stage 2L: ML Archetypes & Player Similarities", "scripts/features/archetypes.py"),
            ("Stage 3: Tiered Analytics Store & Partitioning", "scripts/build_analytics_store.py"),
            ("Stage 4: Head-to-Head Matchup Simulations", "scripts/features/matchup_simulator.py"),
        ]
    else:
        # Step 0: Sync active season if requested (or on scheduled runs)
        if args.sync:
            stages_to_run.append(
                ("Stage 0: Sync Active Season & Fetch Missing PBP", "scripts/sync_active_season.py")
            )

        # Step 1: Rolling 1,000-Game Baselines (shifts automatically when new games arrive)
        stages_to_run.append(
            ("Stage 1: Rolling 1,000-Game Baselines", "scripts/build_baselines.py")
        )

        # Step 2: All 11 Feature Modules
        stages_to_run.extend([
            ("Stage 2A: Shot Features", "scripts/features/shot_features.py"),
            ("Stage 2B: Team Defense & Opponent 4-Factors", "scripts/features/team_defense.py"),
            ("Stage 2C: Player Volatility & Rest Context", "scripts/features/player_context.py"),
            ("Stage 2D: 1,000-Centered Team Elo Engine", "scripts/features/team_elo.py"),
            ("Stage 2E: Playmaking & Oliver Floor Share", "scripts/features/playmaking_and_roles.py"),
            ("Stage 2F: Spatial Hot/Cold & Defensive Leaks", "scripts/features/spatial_hot_cold.py"),
            ("Stage 2G: Game Flow, Momentum & Rest Advantage", "scripts/features/game_flow.py"),
            ("Stage 2H: PBP Directed Assist Network", "scripts/features/assist_network.py"),
            ("Stage 2I: Stint Decomposition & EPM / RAPM", "scripts/features/effective_plus_minus.py"),
            ("Stage 2J: PBP Momentum, Runs & Droughts", "scripts/features/momentum_and_runs.py"),
            ("Stage 2K: Hustle Tracking & 5-Man Lineups", "scripts/features/hustle_and_lineups.py"),
            ("Stage 2L: ML Archetypes & Player Similarities", "scripts/features/archetypes.py"),
            ("Stage 3: Tiered Analytics Store & Partitioning", "scripts/build_analytics_store.py"),
            ("Stage 4: Head-to-Head Matchup Simulations", "scripts/features/matchup_simulator.py"),
        ])

    logger.info(f"Pipeline queued with {len(stages_to_run)} stages.")

    for desc, script in stages_to_run:
        success = run_stage(desc, script)
        if not success:
            logger.error("Pipeline aborted due to stage failure.")
            sys.exit(1)

    total_elapsed = time.time() - pipeline_start
    logger.info("==================================================")
    logger.info(f"ALL {len(stages_to_run)} STAGES COMPLETED SUCCESSFULLY in {total_elapsed:.2f}s")
    logger.info("Production datasets ready in: data/analytics/")
    logger.info("==================================================")


if __name__ == "__main__":
    main()