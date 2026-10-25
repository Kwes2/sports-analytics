"""
scripts/ingest_hustle_and_lineups.py
NBA Analytics Platform - Hustle & Lineup Ingestion Engine

Fetches:
1. Official NBA Hustle Stats (leaguehustlestatsplayer & leaguehustlestatsteam)
   - Deflections, Charges Drawn, Screen Assists, Box Outs, Loose Balls
2. 5-Man Lineup Combinations (leaguedashlineups)
   - On-court Net Ratings, Pace, and Minutes per lineup
"""

import json
import logging
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("HustleLineupIngest")

SEASONS: List[str] = ["2025-26", "2026-27"]
NBA_BASE_URL: str = "https://stats.nba.com/stats"

BASE_HEADERS: Dict[str, str] = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
    "Referer": "https://www.nba.com/stats/players/hustle",
    "Origin": "https://www.nba.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


def polite_delay(min_sec: float = 1.25, max_sec: float = 1.65) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp_path, path)


def request_with_retry(
    session: requests.Session,
    url: str,
    params: Dict[str, str],
    max_retries: int = 4,
    backoff_factor: float = 2.0,
    timeout: int = 35,
) -> Optional[Dict[str, Any]]:
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, params=params, headers=BASE_HEADERS, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            elif response.status_code in [429, 503, 504]:
                wait_time = (backoff_factor ** attempt) + random.uniform(1.0, 2.0)
                logger.warning(
                    f"HTTP {response.status_code}. Throttling for {wait_time:.2f}s (Attempt {attempt}/{max_retries})."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"HTTP {response.status_code} for URL {url}")
                return None
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as err:
            wait_time = (backoff_factor ** attempt) + random.uniform(1.0, 2.0)
            logger.warning(f"Network error: {err}. Retrying in {wait_time:.2f}s...")
            time.sleep(wait_time)

    return None


def parse_result_set(data: Dict[str, Any], result_set_index: int = 0) -> List[Dict[str, Any]]:
    try:
        result_sets = data.get("resultSets", [])
        if not result_sets:
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
def fetch_hustle_stats(session: requests.Session, season: str, player_or_team: str) -> None:
    entity_label = "player" if player_or_team == "P" else "team"
    endpoint = "leaguehustlestatsplayer" if player_or_team == "P" else "leaguehustlestatsteam"
    out_path = os.path.join("data", "raw", "hustle", f"{entity_label}_{season}.json")

    if os.path.exists(out_path):
        logger.info(f"Hustle {entity_label} stats for {season} already cached. Skipping.")
        return

    logger.info(f"Fetching hustle {entity_label} stats for season {season}...")
    url = f"{NBA_BASE_URL}/{endpoint}"
    params = {
        "College": "",
        "Conference": "",
        "Country": "",
        "DateFrom": "",
        "DateTo": "",
        "Division": "",
        "DraftPick": "",
        "DraftYear": "",
        "GameScope": "",
        "Height": "",
        "LastNGames": "0",
        "LeagueID": "00",
        "Location": "",
        "Month": "0",
        "OpponentTeamID": "0",
        "Outcome": "",
        "PORound": "0",
        "PaceAdjust": "N",
        "PerMode": "Totals",
        "Period": "0",
        "PlayerExperience": "",
        "PlayerPosition": "",
        "PlusMinus": "N",
        "Rank": "N",
        "Season": season,
        "SeasonSegment": "",
        "SeasonType": "Regular Season",
        "TeamID": "0",
        "VsConference": "",
        "VsDivision": "",
        "Weight": "",
    }

    raw_data = request_with_retry(session, url, params)
    polite_delay()

    if raw_data:
        records = parse_result_set(raw_data, result_set_index=0)
        write_json(out_path, records)
        logger.info(f"Successfully saved {len(records)} hustle {entity_label} records to {out_path}")
    else:
        logger.error(f"Could not retrieve hustle {entity_label} stats for {season}.")


def fetch_lineup_stats(session: requests.Session, season: str) -> None:
    out_path = os.path.join("data", "raw", "lineups", f"lineups_5man_{season}.json")
    if os.path.exists(out_path):
        logger.info(f"5-man lineup stats for {season} already cached. Skipping.")
        return

    logger.info(f"Fetching 5-man lineup combinations for season {season}...")
    url = f"{NBA_BASE_URL}/leaguedashlineups"
    params = {
        "Conference": "",
        "DateFrom": "",
        "DateTo": "",
        "Division": "",
        "GameID": "",
        "GameSegment": "",
        "GroupQuantity": "5",
        "LastNGames": "0",
        "LeagueID": "00",
        "Location": "",
        "MeasureType": "Base",
        "Month": "0",
        "OpponentTeamID": "0",
        "Outcome": "",
        "PORound": "0",
        "PaceAdjust": "N",
        "PerMode": "Totals",
        "Period": "0",
        "PlusMinus": "N",
        "Rank": "N",
        "Season": season,
        "SeasonSegment": "",
        "SeasonType": "Regular Season",
        "ShotClockRange": "",
        "TeamID": "0",
        "VsConference": "",
        "VsDivision": "",
    }

    raw_data = request_with_retry(session, url, params)
    polite_delay()

    if raw_data:
        records = parse_result_set(raw_data, result_set_index=0)
        write_json(out_path, records)
        logger.info(f"Successfully saved {len(records)} 5-man lineup records to {out_path}")
    else:
        logger.error(f"Could not retrieve 5-man lineups for {season}.")


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    start_time = time.time()
    logger.info("==================================================")
    logger.info("Starting Ingestion: Hustle Stats & 5-Man Lineups")
    logger.info(f"Target Seasons: {SEASONS}")
    logger.info("==================================================")

    session = requests.Session()

    for season in SEASONS:
        logger.info(f"--- Processing Season: {season} ---")
        fetch_hustle_stats(session, season=season, player_or_team="P")
        fetch_hustle_stats(session, season=season, player_or_team="T")
        fetch_lineup_stats(session, season=season)

    elapsed = time.time() - start_time
    logger.info("==================================================")
    logger.info(f"Hustle & Lineups ingestion complete in {elapsed:.2f}s.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()