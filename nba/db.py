import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "nba.db"


def get_db_connection(db_path=DB_PATH):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_existing_completed_game_ids(db_path=DB_PATH):
    """Returns a set of all game IDs already fully processed in SQLite."""
    if not Path(db_path).exists():
        return set()
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT game_id FROM games")
        ids = set(str(row["game_id"]) for row in cur.fetchall())
    except Exception:
        ids = set()
    conn.close()
    return ids


def init_db(db_path=DB_PATH):
    """Creates normalized atomic tables with explicit season_year and season_type columns."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # 1. Players Lookup Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            player_name TEXT,
            team_id TEXT,
            team_abbrev TEXT,
            pos TEXT
        );
    """)

    # 2. Games Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            season_year INTEGER,
            season_type INTEGER,
            date TEXT,
            home_team_id TEXT,
            away_team_id TEXT,
            home_team_name TEXT,
            away_team_name TEXT,
            home_score INTEGER,
            away_score INTEGER
        );
    """)

    # 3. Player Game Logs Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            game_id TEXT,
            season_year INTEGER,
            season_type INTEGER,
            date TEXT,
            is_starter INTEGER,
            minutes REAL,
            pts INTEGER,
            reb INTEGER,
            ast INTEGER,
            stl INTEGER,
            blk INTEGER,
            to_val INTEGER,
            pf INTEGER,
            plus_minus INTEGER,
            fgm INTEGER,
            fga INTEGER,
            fg3m INTEGER,
            fg3a INTEGER,
            ftm INTEGER,
            fta INTEGER,
            oreb INTEGER,
            dreb INTEGER
        );
    """)

    # 4. Shots Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            season_year INTEGER,
            season_type INTEGER,
            date TEXT,
            shooter_id TEXT,
            val INTEGER,
            made INTEGER,
            zone TEXT,
            granular_zone TEXT
        );
    """)

    # 5. Assisted Baskets Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assisted_baskets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            season_year INTEGER,
            season_type INTEGER,
            date TEXT,
            team_id TEXT,
            passer_id TEXT,
            scorer_id TEXT,
            val INTEGER,
            zone TEXT
        );
    """)

    # 6. Stints Table (Lineup interactions)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            season_year INTEGER,
            season_type INTEGER,
            date TEXT,
            home_lineup TEXT,
            away_lineup TEXT,
            home_pts INTEGER,
            away_pts INTEGER,
            poss REAL
        );
    """)

    # High-Speed Composite Indexes for Window/Preset Queries
    cur.execute("CREATE INDEX IF NOT EXISTS idx_games_filter ON games(season_year, season_type, date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_filter ON player_game_logs(season_year, season_type, date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_player ON player_game_logs(player_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_shots_filter ON shots(season_year, season_type, date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_assists_filter ON assisted_baskets(season_year, season_type, date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stints_filter ON stints(season_year, season_type, date);")

    conn.commit()
    conn.close()


def bulk_insert(db_path, table_name, columns, rows):
    if not rows:
        return
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    placeholders = ", ".join(["?"] * len(columns))
    col_str = ", ".join(columns)
    sql = f"INSERT OR REPLACE INTO {table_name} ({col_str}) VALUES ({placeholders})"

    cur.executemany(sql, rows)
    conn.commit()
    conn.close()


def optimize_db(db_path=DB_PATH):
    print("Compacting SQLite database (VACUUM & OPTIMIZE)...")
    conn = sqlite3.connect(str(db_path))
    conn.execute("VACUUM;")
    conn.execute("PRAGMA optimize;")
    conn.close()