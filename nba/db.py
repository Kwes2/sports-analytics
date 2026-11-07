import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "nba.db"


def get_db_connection(db_path=DB_PATH):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=DB_PATH):
    """Creates normalized atomic tables and lean date indexes."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # 1. Players Lookup Table (Stores names once to save 15+ MB)
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
            date TEXT,
            home_team_id TEXT,
            away_team_id TEXT,
            home_score INTEGER,
            away_score INTEGER
        );
    """)

    # 3. Lean Player Game Logs Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            game_id TEXT,
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

    # 4. Lean Shots Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            date TEXT,
            shooter_id TEXT,
            val INTEGER,
            made INTEGER,
            zone TEXT,
            granular_zone TEXT
        );
    """)

    # 5. Lean Assisted Baskets Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assisted_baskets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            date TEXT,
            team_id TEXT,
            passer_id TEXT,
            scorer_id TEXT,
            val INTEGER,
            zone TEXT
        );
    """)

    # 6. Stints Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            date TEXT,
            home_lineup TEXT,
            away_lineup TEXT,
            home_pts INTEGER,
            away_pts INTEGER,
            poss REAL
        );
    """)

    # Strictly necessary date indexes for on-the-fly range filtering
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_date ON player_game_logs(date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_shots_date ON shots(date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_assists_date ON assisted_baskets(date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stints_date ON stints(date);")

    conn.commit()
    conn.close()


def bulk_insert(db_path, table_name, columns, rows):
    """High-speed bulk insertion inside a single transaction."""
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
    """Compacts the SQLite database and strips all unallocated disk pages."""
    print("Compacting SQLite database (VACUUM)...")
    conn = sqlite3.connect(str(db_path))
    conn.execute("VACUUM;")
    conn.execute("PRAGMA optimize;")
    conn.close()