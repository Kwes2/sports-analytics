"""
scripts/ingest_pbp.py
NBA Analytics Platform - Modern Play-by-Play (PBP) Ingestion Engine

Fetches play-by-play event streams using modern NBA feeds:
1. Primary: cdn.nba.com static JSON (zero rate-limit, high speed)
2. Fallback: stats.nba.com/stats/playbyplayv3

Captures exact scorer-to-assister links (assistPersonId) and stint transitions.
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
logger = logging.getLogger("PBPIngest")

SEASONS: List[str] = ["2026-27", "2025-26"]

CDN_PBP_URL = "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"
STATS_V3_URL = "https://stats.nba.com/stats/playbyplayv3"

BASE_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
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


def polite_delay(min_sec: float = 0.5, max_sec: float = 0.8) -> None:
    # CDN requests require much less delay
    time.sleep(random.uniform(min_sec, max_sec))


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp_path, path)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_cdn_actions(actions: List[Dict[str, Any]], game_id: str) -> List[Dict[str, Any]]:
    """Normalizes CDN play-by-play action items into compact records."""
    normalized = []
    for a in actions:
        normalized.append({
            "game_id": game_id,
            "action_number": a.get("actionNumber"),
            "clock": a.get("clock"),
            "period": a.get("period"),
            "team_id": a.get("teamId"),
            "team_abbrev": a.get("teamTricode"),
            "person_id": a.get("personId"),
            "player_name": a.get("playerName"),
            "action_type": a.get("actionType"),
            "sub_type": a.get("subType"),
            "shot_result": a.get("shotResult"),
            "points_total": a.get("pointsTotal", 0),
            "assist_person_id": a.get("assistPersonId"),
            "assist_player_name": a.get("assistPlayerNameInitial"),
            "assist_total": a.get("assistTotal"),
            "score_home": a.get("scoreHome"),
            "score_away": a.get("scoreAway"),
            "description": a.get("description"),
        })
    return normalized


def fetch_from_cdn(session: requests.Session, game_id: str) -> Optional[List[Dict[str, Any]]]:
    """Queries public CDN endpoint."""
    url = CDN_PBP_URL.format(game_id=game_id)
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            actions = data.get("game", {}).get("actions", [])
            if actions:
                return normalize_cdn_actions(actions, game_id)
    except Exception:
        pass
    return None


def fetch_from_v3(session: requests.Session, game_id: str) -> Optional[List[Dict[str, Any]]]:
    """Fallback query to stats.nba.com playbyplayv3."""
    params = {"GameID": game_id, "StartPeriod": "0", "EndPeriod": "0"}
    headers = BASE_HEADERS.copy()
    headers["Referer"] = f"https://www.nba.com/game/{game_id}"

    try:
        resp = session.get(STATS_V3_URL, params=params, headers=headers, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            actions = data.get("game", {}).get("actions", [])
            if actions:
                return normalize_cdn_actions(actions, game_id)
    except Exception:
        pass
    return None


def get_game_ids_for_season(season: str) -> List[str]:
    team_log_file = os.path.join("data", "raw", "game_logs", f"team_{season}.json")
    if not os.path.exists(team_log_file):
        logger.error(f"Missing {team_log_file}")
        return []

    logs = load_json(team_log_file)
    game_dict = {}
    for entry in logs:
        gid = str(entry.get("GAME_ID"))
        gdate = str(entry.get("GAME_DATE"))
        if gid:
            game_dict[gid] = gdate

    sorted_games = sorted(game_dict.items(), key=lambda x: x[1])
    return [g[0] for g in sorted_games]


def ingest_season_pbp(session: requests.Session, season: str) -> None:
    game_ids = get_game_ids_for_season(season)
    total_games = len(game_ids)
    logger.info(f"Season {season}: Identified {total_games} games to evaluate.")

    downloaded = 0
    skipped = 0
    failed = 0

    for idx, gid in enumerate(game_ids, start=1):
        out_path = os.path.join("data", "raw", "pbp", season, f"{gid}.json")
        if os.path.exists(out_path):
            skipped += 1
            continue

        # 1. Try CDN first (fastest, no rate limits)
        records = fetch_from_cdn(session, gid)
        source = "CDN"

        # 2. Fallback to v3
        if not records:
            records = fetch_from_v3(session, gid)
            source = "STATS_V3"
            time.sleep(1.0)  # slightly longer delay for stats.nba.com
        else:
            polite_delay()

        if records:
            write_json(out_path, records)
            downloaded += 1
            logger.info(
                f"[{idx}/{total_games}] Season {season} - Saved {len(records)} events for Game {gid} "
                f"via {source} (Downloaded: {downloaded}, Cached: {skipped})"
            )
        else:
            failed += 1
            logger.warning(f"Failed to ingest PBP for Game {gid}")

    logger.info(
        f"Season {season} Complete: {downloaded} new games downloaded, {skipped} already cached, {failed} failed."
    )


def main() -> None:
    start_time = time.time()
    logger.info("==================================================")
    logger.info("Starting Modern Play-by-Play (PBP) Ingestion Engine")
    logger.info(f"Target Seasons in Order: {SEASONS}")
    logger.info("==================================================")

    session = requests.Session()

    for season in SEASONS:
        logger.info(f"--- Ingesting Play-by-Play for Season: {season} ---")
        ingest_season_pbp(session, season)

    elapsed = time.time() - start_time
    logger.info("==================================================")
    logger.info(f"PBP Ingestion run complete in {elapsed:.2f}s.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()