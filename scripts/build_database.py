"""
scripts/build_database.py
NBA Analytics Platform - Multi-Decade SQLite Database Engine

Compiles all raw logs, shot charts, assist networks, EPM ratings, 
and tiered analytics stores into a single, high-performance SQLite database:
data/nba_analytics.db
"""

import glob
import json
import logging
import os
import sys
import sqlite3
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("DBBuilder")

DB_PATH = os.path.join("data", "nba_analytics.db")
SEASONS = ["2026-27", "2025-26"]


def load_json(filepath: str) -> Any:
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def init_database(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    # 1. Teams Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER,
            season TEXT,
            team_name TEXT,
            team_abbrev TEXT,
            conference TEXT,
            division TEXT,
            games_played INTEGER,
            pace REAL,
            offensive_rating REAL,
            defensive_rating REAL,
            net_rating REAL,
            overall_elo REAL,
            offensive_elo REAL,
            defensive_elo REAL,
            PRIMARY KEY (team_id, season)
        )
    """)

    # 2. Players Table (Master Index + Profiles)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER,
            season TEXT,
            player_name TEXT,
            team_id INTEGER,
            team_abbrev TEXT,
            position TEXT,
            archetype TEXT,
            games_played INTEGER,
            minutes_per_game REAL,
            usage_pct REAL,
            true_shooting_pct REAL,
            pts_per_100 REAL,
            ast_per_100 REAL,
            reb_per_100 REAL,
            net_epm REAL,
            offensive_epm REAL,
            defensive_epm REAL,
            headshot_url TEXT,
            full_profile_json TEXT,
            PRIMARY KEY (player_id, season)
        )
    """)

    # 3. Game Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_logs (
            game_id TEXT,
            season TEXT,
            team_id INTEGER,
            player_id INTEGER,
            player_name TEXT,
            matchup TEXT,
            game_date TEXT,
            min REAL,
            pts INTEGER,
            fga INTEGER,
            fgm INTEGER,
            fg3a INTEGER,
            fg3m INTEGER,
            fta INTEGER,
            ftm INTEGER,
            oreb INTEGER,
            dreb INTEGER,
            reb INTEGER,
            ast INTEGER,
            stl INTEGER,
            blk INTEGER,
            tov INTEGER,
            plus_minus INTEGER,
            PRIMARY KEY (game_id, player_id)
        )
    """)

    # 4. Assist Network Table (Directed Edges)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assist_network (
            season TEXT,
            team_id INTEGER,
            passer_id INTEGER,
            passer_name TEXT,
            scorer_id INTEGER,
            scorer_name TEXT,
            assists_count INTEGER,
            points_created INTEGER,
            three_pt_assists INTEGER,
            rim_assists INTEGER,
            PRIMARY KEY (season, team_id, passer_id, scorer_id)
        )
    """)

    # Indexes for lightning-fast queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_season ON players(season)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_abbrev)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gamelogs_player ON game_logs(player_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assists_season ON assist_network(season, team_id)")

    conn.commit()


def migrate_season_data(conn: sqlite3.Connection, season: str) -> None:
    cursor = conn.cursor()
    logger.info(f"Migrating season {season} into SQLite database...")

    # --- 1. Migrate Teams ---
    teams_file = os.path.join("data", "analytics", f"teams_{season}.json")
    if os.path.exists(teams_file):
        teams = load_json(teams_file)
        for t in teams:
            cursor.execute("""
                INSERT OR REPLACE INTO teams (
                    team_id, season, team_name, team_abbrev, conference, division,
                    games_played, pace, offensive_rating, defensive_rating, net_rating,
                    overall_elo, offensive_elo, defensive_elo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t["team_id"], season, t["team_name"], t["team_abbrev"],
                t.get("conference", "East"), t.get("division", "Atlantic"),
                t["games_played"], t["pace"],
                t["ratings"]["offensive_rating"], t["ratings"]["defensive_rating"], t["ratings"]["net_rating"],
                t["elo_ratings"]["overall_elo"], t["elo_ratings"]["offensive_elo"], t["elo_ratings"]["defensive_elo"]
            ))

    # --- 2. Migrate Players ---
    players_file = os.path.join("data", "analytics", f"players_{season}.json")
    if os.path.exists(players_file):
        players = load_json(players_file)
        for p in players:
            epm = p.get("effective_plus_minus", {})
            arch = p.get("archetype") or {}
            cursor.execute("""
                INSERT OR REPLACE INTO players (
                    player_id, season, player_name, team_id, team_abbrev, position,
                    archetype, games_played, minutes_per_game, usage_pct, true_shooting_pct,
                    pts_per_100, ast_per_100, reb_per_100, net_epm, offensive_epm, defensive_epm,
                    headshot_url, full_profile_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["player_id"], season, p["player_name"], p["team_id"], p["team_abbrev"],
                p["position"], arch.get("offensive_role"), p["games_played"], p["minutes_per_game"],
                p["usage_pct"], p["true_shooting_pct"],
                p["per_100_possessions"]["points"], p["per_100_possessions"]["assists"], p["per_100_possessions"]["rebounds"],
                epm.get("net_epm"), epm.get("offensive_epm"), epm.get("defensive_epm"),
                p["headshot_url"], json.dumps(p)
            ))

    # --- 3. Migrate Game Logs ---
    player_logs_file = os.path.join("data", "raw", "game_logs", f"player_{season}.json")
    if os.path.exists(player_logs_file):
        logs = load_json(player_logs_file)
        for r in logs:
            cursor.execute("""
                INSERT OR IGNORE INTO game_logs (
                    game_id, season, team_id, player_id, player_name, matchup, game_date,
                    min, pts, fga, fgm, fg3a, fg3m, fta, ftm, oreb, dreb, reb, ast, stl, blk, tov, plus_minus
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(r.get("GAME_ID")), season, r.get("TEAM_ID"), r.get("PLAYER_ID"), r.get("PLAYER_NAME"),
                r.get("MATCHUP"), r.get("GAME_DATE"), r.get("MIN", 0), r.get("PTS", 0),
                r.get("FGA", 0), r.get("FGM", 0), r.get("FG3A", 0), r.get("FG3M", 0),
                r.get("FTA", 0), r.get("FTM", 0), r.get("OREB", 0), r.get("DREB", 0),
                r.get("REB", 0), r.get("AST", 0), r.get("STL", 0), r.get("BLK", 0),
                r.get("TOV", 0), r.get("PLUS_MINUS", 0)
            ))

    # --- 4. Migrate Assist Networks ---
    ast_file = os.path.join("data", "processed", "features", f"assist_network_{season}.json")
    if os.path.exists(ast_file):
        ast_data = load_json(ast_file).get("teams", {})
        for tid_str, t_obj in ast_data.items():
            tid = int(tid_str)
            for duo in t_obj.get("top_synergy_duos", []):
                cursor.execute("""
                    INSERT OR REPLACE INTO assist_network (
                        season, team_id, passer_id, passer_name, scorer_id, scorer_name,
                        assists_count, points_created, three_pt_assists, rim_assists
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    season, tid, duo["passer_id"], duo["passer_name"],
                    duo["scorer_id"], duo["scorer_name"], duo["assists_count"],
                    duo["points_created"], duo["three_pt_assists"], duo["rim_assists"]
                ))

    conn.commit()
    logger.info(f"Season {season} migration complete.")


def main() -> None:
    logger.info("==================================================")
    logger.info("BUILDING MASTER SQLITE DATABASE")
    logger.info(f"Target Database Path: {DB_PATH}")
    logger.info("==================================================")

    # Remove old DB if rebuilding fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    init_database(conn)

    for season in SEASONS:
        migrate_season_data(conn, season)

    conn.close()

    db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    logger.info("==================================================")
    logger.info(f"Database build complete successfully!")
    logger.info(f"Master Database Size: {db_size_mb:.2f} MB")
    logger.info("==================================================px")


if __name__ == "__main__":
    main()