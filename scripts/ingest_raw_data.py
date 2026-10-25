"""
scripts/ingest_raw_data.py
NBA Analytics Platform - Raw Data Ingestion Engine

Pulls complete player/team game logs and 30-team spatial shot coordinates
for the 2025-26 and 2026-27 seasons from the NBA Stats API.
"""

import json
import logging
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional
import requests

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("NBAIngest")

# ---------------------------------------------------------------------------
# Constants & Endpoints
# ---------------------------------------------------------------------------
SEASONS: List[str] = ["2025-26", "2026-27"]

NBA_BASE_URL: str = "https://stats.nba.com/stats"
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
]

BASE_HEADERS: Dict[str, str] = {
    "Host": "stats.nba.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# The 30 Active NBA Team IDs
NBA_TEAMS: Dict[int, str] = {
    1610612737: "ATL", 1610612738: "BOS", 1610612751: "BKN", 1610612766: "CHA",
    1610612741: "CHI", 1610612739: "CLE", 1610612742: "DAL", 1610612743: "DEN",
    1610612765: "DET", 1610612744: "GSW", 1610612745: "HOU", 1610612754: "IND",
    1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM", 1610612748: "MIA",
    1610612749: "MIL", 1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
    1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHX",
    1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612761: "TOR",
    1610612762: "UTA", 1610612764: "WAS"
}

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def polite_delay(min_sec: float = 1.25, max_sec: float = 1.65) -> None:
    """Pause execution with jitter to respect API thresholds."""
    sleep_time = random.uniform(min_sec, max_sec)
    time.sleep(sleep_time)


def get_headers() -> Dict[str, str]:
    """Generate request headers with randomized User-Agent."""
    headers = BASE_HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    return headers


def ensure_directory(path: str) -> None:
    """Ensure directory exists on disk."""
    os.makedirs(path, exist_ok=True)


def write_json(path: str, data: Any) -> None:
    """Write compact JSON file safely using atomic flush."""
    ensure_directory(os.path.dirname(path))
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp_path, path)


def request_with_retry(
    url: str,
    params: Dict[str, str],
    max_retries: int = 5,
    backoff_factor: float = 2.0
) -> Optional[Dict[str, Any]]:
    """Execute GET request with exponential backoff and rate limit resilience."""
    for attempt in range(1, max_retries + 1):
        try:
            headers = get_headers()
            response = requests.get(url, params=params, headers=headers, timeout=25)

            if response.status_code == 200:
                return response.json()
            elif response.status_code in [429, 503, 504]:
                wait_time = (backoff_factor ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(
                    f"HTTP {response.status_code} received. Throttling for {wait_time:.2f}s (Attempt {attempt}/{max_retries})."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"HTTP {response.status_code} for URL {url} with params {params}")
                return None
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as err:
            wait_time = (backoff_factor ** attempt) + random.uniform(0.5, 1.5)
            logger.warning(f"Network error: {err}. Retrying in {wait_time:.2f}s...")
            time.sleep(wait_time)

    logger.error(f"Failed to fetch data after {max_retries} attempts.")
    return None


def parse_result_set(data: Dict[str, Any], result_set_index: int = 0) -> List[Dict[str, Any]]:
    """Convert NBA API tabular format (headers + rowSet) into list of dicts."""
    try:
        result_sets = data.get("resultSets", [])
        if not result_sets:
            # Fallback for single resultSet objects
            single_set = data.get("resultSet", {})
            headers = single_set.get("headers", [])
            row_set = single_set.get("rowSet", [])
        else:
            headers = result_sets[result_set_index].get("headers", [])
            row_set = result_sets[result_set_index].get("rowSet", [])

        return [dict(zip(headers, row)) for row in row_set]
    except Exception as e:
        logger.error(f"Error parsing result set: {e}")
        return []

# ---------------------------------------------------------------------------
# Ingestion Tasks
# ---------------------------------------------------------------------------
def fetch_game_logs(season: str, player_or_team: str) -> None:
    """
    Fetch complete league game logs for players or teams.
    player_or_team: 'P' for Players, 'T' for Teams.
    """
    entity_label = "player" if player_or_team == "P" else "team"
    out_path = os.path.join("data", "raw", "game_logs", f"{entity_label}_{season}.json")

    logger.info(f"Fetching {entity_label} game logs for season {season}...")
    url = f"{NBA_BASE_URL}/leaguegamelog"
    params = {
        "Counter": "1000",
        "DateFrom": "",
        "DateTo": "",
        "Direction": "DESC",
        "LeagueID": "00",
        "PlayerOrTeam": player_or_team,
        "Season": season,
        "SeasonType": "Regular Season",
        "Sorter": "DATE",
    }

    raw_data = request_with_retry(url, params)
    polite_delay()

    if raw_data:
        records = parse_result_set(raw_data, result_set_index=0)
        write_json(out_path, records)
        logger.info(f"Successfully saved {len(records)} {entity_label} logs to {out_path}")
    else:
        logger.error(f"Could not retrieve {entity_label} game logs for {season}.")


def fetch_team_shot_charts(season: str) -> None:
    """
    Fetch spatial shot charts for all 30 teams for a given season.
    Each team is stored in its own partitioned JSON file.
    """
    url = f"{NBA_BASE_URL}/shotchartdetail"
    total_teams = len(NBA_TEAMS)

    for index, (team_id, abbrev) in enumerate(NBA_TEAMS.items(), start=1):
        out_path = os.path.join("data", "raw", "shots", season, f"{team_id}.json")

        if os.path.exists(out_path):
            logger.info(f"[{index}/{total_teams}] Season {season} - {abbrev} ({team_id}) already cached. Skipping.")
            continue

        logger.info(f"[{index}/{total_teams}] Season {season} - Ingesting shots for {abbrev} (ID: {team_id})...")

        params = {
            "LeagueID": "00",
            "Season": season,
            "SeasonType": "Regular Season",
            "TeamID": str(team_id),
            "PlayerID": "0",
            "Outcome": "",
            "Location": "",
            "Month": "0",
            "SeasonSegment": "",
            "DateFrom": "",
            "DateTo": "",
            "OpponentTeamID": "0",
            "VsConference": "",
            "VsDivision": "",
            "Position": "",
            "RookieYear": "",
            "GameSegment": "",
            "Period": "0",
            "LastNGames": "0",
            "ContextMeasure": "FGA",
        }

        raw_data = request_with_retry(url, params)
        polite_delay()

        if raw_data:
            shots = parse_result_set(raw_data, result_set_index=0)
            write_json(out_path, shots)
            logger.info(f"Saved {len(shots)} shots for {abbrev} to {out_path}")
        else:
            logger.error(f"Failed to retrieve shot chart for {abbrev} ({season}).")

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    start_time = time.time()
    logger.info("==================================================")
    logger.info("Starting NBA Analytics Data Ingestion")
    logger.info(f"Target Seasons: {SEASONS}")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Processing Season: {season} ---")
        # 1. Player Game Logs
        fetch_game_logs(season=season, player_or_team="P")

        # 2. Team Game Logs
        fetch_game_logs(season=season, player_or_team="T")

        # 3. Spatial Shot Charts for all 30 Teams
        fetch_team_shot_charts(season=season)

    elapsed = time.time() - start_time
    logger.info("==================================================")
    logger.info(f"Ingestion complete. Total elapsed time: {elapsed:.2f} seconds.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()