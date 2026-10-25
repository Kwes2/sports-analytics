"""
scripts/ingest_auxiliary_data.py
NBA Analytics Platform - Auxiliary Ingestion Engine (Resilient)

Fetches:
1. Player Bio & Position Data (leaguedashplayerbiostats)
2. Passer-to-Receiver Tracking Matrices (teamdashptpass)
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
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger("AuxiliaryIngest")

SEASONS: List[str] = ["2025-26", "2026-27"]
NBA_BASE_URL: str = "https://stats.nba.com/stats"

NBA_TEAMS: Dict[int, str] = {
    1610612737: "ATL", 1610612738: "BOS", 1610612751: "BKN", 1610612766: "CHA",
    1610612741: "CHI", 1610612739: "CLE", 1610612742: "DAL", 1610612743: "DEN",
    1610612765: "DET", 1610612744: "GSW", 1610612745: "HOU", 1610612754: "IND",
    1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM", 1610612748: "MIA",
    1610612749: "MIL", 1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
    1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHX",
    1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612761: "TOR",
    1610612762: "UTA", 1610612764: "WAS",
}

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def polite_delay(min_sec: float = 1.25, max_sec: float = 1.65) -> None:
    time.sleep(random.uniform(min_sec, max_sec))


def build_headers(team_id: Optional[int] = None) -> Dict[str, str]:
    referer = (
        f"https://www.nba.com/stats/team/{team_id}/passes-dash"
        if team_id
        else "https://www.nba.com/stats/players/bio-stats"
    )
    return {
        "Host": "stats.nba.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
        "Connection": "keep-alive",
        "Referer": referer,
        "Origin": "https://www.nba.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }


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
    team_id: Optional[int] = None,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    timeout: int = 120,
) -> Optional[Dict[str, Any]]:
    headers = build_headers(team_id)

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            elif response.status_code in [429, 503, 504]:
                wait_time = (backoff_factor ** attempt) + random.uniform(1.0, 2.0)
                logger.warning(
                    f"HTTP {response.status_code}. Throttling for {wait_time:.2f}s (Attempt {attempt}/{max_retries})."
                )
                time.sleep(wait_time)
            elif response.status_code == 500:
                logger.warning(
                    f"HTTP 500 for URL (Attempt {attempt}/{max_retries}). Retrying in 2s..."
                )
                time.sleep(2.0)
            else:
                logger.error(f"HTTP {response.status_code} for URL {url}")
                return None
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as err:
            wait_time = (backoff_factor ** attempt) + random.uniform(1.0, 2.0)
            logger.warning(f"Timeout/Network issue: {err}. Retrying in {wait_time:.2f}s...")
            time.sleep(wait_time)

    logger.error(f"Failed to fetch {url} after {max_retries} attempts.")
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
        logger.error(f"Error parsing result set {result_set_index}: {e}")
        return []


# ---------------------------------------------------------------------------
# Ingestion Tasks
# ---------------------------------------------------------------------------
def fetch_player_bios(session: requests.Session, season: str) -> None:
    out_path = os.path.join("data", "raw", "player_bios", f"{season}.json")
    if os.path.exists(out_path):
        logger.info(f"Player bios for {season} already cached. Skipping.")
        return

    logger.info(f"Fetching player position & bio data for season {season}...")
    url = f"{NBA_BASE_URL}/leaguedashplayerbiostats"
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
        "GameSegment": "",
        "Height": "",
        "LastNGames": "0",
        "LeagueID": "00",
        "Location": "",
        "Month": "0",
        "OpponentTeamID": "0",
        "Outcome": "",
        "PORound": "0",
        "PerMode": "Totals",
        "Period": "0",
        "PlayerExperience": "",
        "PlayerPosition": "",
        "Season": season,
        "SeasonSegment": "",
        "SeasonType": "Regular Season",
        "ShotClockRange": "",
        "StarterBench": "",
        "TeamID": "0",
        "VsConference": "",
        "VsDivision": "",
        "Weight": "",
    }

    raw_data = request_with_retry(session, url, params, team_id=None)
    polite_delay()

    if raw_data:
        records = parse_result_set(raw_data, result_set_index=0)
        write_json(out_path, records)
        logger.info(f"Successfully saved {len(records)} player bios to {out_path}")
    else:
        logger.error(f"Could not retrieve player bios for {season}.")


def fetch_team_passing_networks(session: requests.Session, season: str) -> None:
    """[DEPRECATED] Superseded by scripts/features/assist_network.py via PBP directed graphs."""
    url = f"{NBA_BASE_URL}/teamdashptpass"
    total_teams = len(NBA_TEAMS)

    for idx, (team_id, abbrev) in enumerate(NBA_TEAMS.items(), start=1):
        out_path = os.path.join("data", "raw", "passes", season, f"{team_id}.json")
        if os.path.exists(out_path):
            logger.info(f"[{idx}/{total_teams}] Season {season} - {abbrev} passing network cached. Skipping.")
            continue

        logger.info(f"[{idx}/{total_teams}] Season {season} - Ingesting passing network for {abbrev}...")
        params = {
            "DateFrom": "",
            "DateTo": "",
            "GameSegment": "",
            "LastNGames": "0",
            "LeagueID": "00",
            "Location": "",
            "Month": "0",
            "OpponentTeamID": "0",
            "Outcome": "",
            "PerMode": "Totals",
            "Period": "0",
            "Season": season,
            "SeasonSegment": "",
            "SeasonType": "Regular Season",
            "TeamID": str(team_id),
            "VsConference": "",
            "VsDivision": "",
        }

        raw_data = request_with_retry(
            session, url, params, team_id=team_id, timeout=120
        )
        polite_delay()

        if raw_data:
            passes_made = parse_result_set(raw_data, result_set_index=0)
            passes_received = parse_result_set(raw_data, result_set_index=1)
            payload = {
                "team_id": team_id,
                "team_abbrev": abbrev,
                "season": season,
                "passes_made": passes_made,
                "passes_received": passes_received,
            }
            write_json(out_path, payload)
            logger.info(f"Saved {len(passes_made)} pass connections for {abbrev} to {out_path}")
        else:
            logger.warning(f"Skipping {abbrev} ({season}) due to API response failure.")


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    start_time = time.time()
    logger.info("==================================================")
    logger.info("Starting Auxiliary Data Ingestion (Bios & Pass Networks)")
    logger.info(f"Target Seasons: {SEASONS}")
    logger.info("==================================================")

    session = requests.Session()

    # 1. First fetch all player positions for both seasons
    for season in SEASONS:
        fetch_player_bios(session, season=season)

    # 2. Passing networks: Note: teamdashptpass is deprecated and frequently throttled/500s.
    # Note: Passer-to-scorer synergy and assist networks are now derived directly from high-resolution
    # PBP feeds by scripts/features/assist_network.py, rendering teamdashptpass obsolete.

    elapsed = time.time() - start_time
    logger.info("==================================================")
    logger.info(f"Auxiliary ingestion complete in {elapsed:.2f}s.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()