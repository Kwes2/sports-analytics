import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "nba.db"


def get_db_connection(db_path=DB_PATH):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=DB_PATH):
    """Creates the normalized atomic tables and performance indexes."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # 1. Games Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            season_year INTEGER,
            date TEXT,
            home_team_id TEXT,
            away_team_id TEXT,
            home_team_name TEXT,
            away_team_name TEXT,
            home_score INTEGER,
            away_score INTEGER,
            venue TEXT
        );
    """)

    # 2. Player Game Logs Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            player_name TEXT,
            team_id TEXT,
            team_abbrev TEXT,
            pos TEXT,
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
            dreb INTEGER,
            gmsc REAL,
            ts_pct REAL
        );
    """)

    # 3. Individual Shot Coordinates Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            date TEXT,
            shooter_id TEXT,
            team_id TEXT,
            x REAL,
            y REAL,
            val INTEGER,
            made INTEGER,
            zone TEXT,
            granular_zone TEXT
        );
    """)

    # 4. Assisted Baskets Table
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

    # 5. Stints Table (5-on-5 on-court Lineup intervals)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            date TEXT,
            home_team_id TEXT,
            away_team_id TEXT,
            home_lineup TEXT,
            away_lineup TEXT,
            home_pts INTEGER,
            away_pts INTEGER,
            poss REAL
        );
    """)

    # High-Performance Indexes for Sub-100ms Range Filtering
    cur.execute("CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_date ON player_game_logs(date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_player ON player_game_logs(player_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_shots_date ON shots(date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_shots_shooter ON shots(shooter_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_assists_date ON assisted_baskets(date);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_assists_passer ON assisted_baskets(passer_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_assists_scorer ON assisted_baskets(scorer_id);")
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