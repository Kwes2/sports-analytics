"""
scripts/sync_active_season.py
NBA Analytics Platform - Active Season Incremental Synchronizer

1. Refreshes active season game logs and cumulative team shot charts.
2. Refreshes active season hustle and 5-man lineups.
3. Identifies and downloads ONLY missing play-by-play (PBP) game files via CDN.
4. Returns whether new games were detected.
"""

import glob
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

logger = logging.getLogger("ActiveSync")

ACTIVE_SEASON = "2026-27"
NBA_BASE_URL = "https://stats.nba.com/stats"
CDN_PBP_URL = "https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"

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

NBA_TEAMS = [
    1610612737, 1610612738, 1610612751, 1610612766, 1610612741, 1610612739,
    1610612742, 1610612743, 1610612765, 1610612744, 1610612745, 1610612754,
    1610612746, 1610612747, 1610612763, 1610612748, 1610612749, 1610612750,
    1610612740, 1610612752, 1610612760, 1610612753, 1610612755, 1610612756,
    1610612757, 1610612758, 1610612759, 1610612761, 1610612762, 1610612764,
]


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp_path, path)


def load_json(path: str) -> Any:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def polite_delay(min_s: float = 0.5, max_s: float = 0.9) -> None:
    time.sleep(random.uniform(min_s, max_s))


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
    except Exception:
        return []


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

# ---------------------------------------------------------------------------
# Sync Tasks
# ---------------------------------------------------------------------------
def sync_game_logs(session: requests.Session) -> tuple[int, int]:
    """Refreshes team and player game logs for the active season."""
    logger.info("Syncing active season game logs...")
    url = f"{NBA_BASE_URL}/leaguegamelog"

    # Team Logs
    t_params = {
        "Counter": "1000", "Direction": "DESC", "LeagueID": "00",
        "PlayerOrTeam": "T", "Season": ACTIVE_SEASON, "SeasonType": "Regular Season", "Sorter": "DATE"
    }
    r_t = session.get(url, params=t_params, headers=BASE_HEADERS, timeout=25)
    t_records = parse_result_set(r_t.json()) if r_t.status_code == 200 else []
    if t_records:
        write_json(os.path.join("data", "raw", "game_logs", f"team_{ACTIVE_SEASON}.json"), t_records)

    polite_delay()

    # Player Logs
    p_params = {
        "Counter": "1000", "Direction": "DESC", "LeagueID": "00",
        "PlayerOrTeam": "P", "Season": ACTIVE_SEASON, "SeasonType": "Regular Season", "Sorter": "DATE"
    }
    r_p = session.get(url, params=p_params, headers=BASE_HEADERS, timeout=25)
    p_records = parse_result_set(r_p.json()) if r_p.status_code == 200 else []
    if p_records:
        write_json(os.path.join("data", "raw", "game_logs", f"player_{ACTIVE_SEASON}.json"), p_records)

    logger.info(f"Active logs updated: {len(t_records)} team rows, {len(p_records)} player rows.")
    return len(t_records), len(p_records)


def sync_active_shots(session: requests.Session) -> None:
    """Overwrites active season team shot charts with latest games."""
    logger.info("Syncing active season spatial shot charts for all 30 teams...")
    url = f"{NBA_BASE_URL}/shotchartdetail"

    for idx, tid in enumerate(NBA_TEAMS, start=1):
        out_path = os.path.join("data", "raw", "shots", ACTIVE_SEASON, f"{tid}.json")
        params = {
            "LeagueID": "00", "Season": ACTIVE_SEASON, "SeasonType": "Regular Season",
            "TeamID": str(tid), "PlayerID": "0", "ContextMeasure": "FGA",
        }
        try:
            resp = session.get(url, params=params, headers=BASE_HEADERS, timeout=25)
            if resp.status_code == 200:
                shots = parse_result_set(resp.json(), 0)
                write_json(out_path, shots)
        except Exception as e:
            logger.warning(f"Failed to update shots for Team {tid}: {e}")
        polite_delay(0.4, 0.7)

    logger.info("Team shot charts updated.")


def sync_missing_pbp(session: requests.Session) -> int:
    """Finds all GAME_IDs in team logs that lack a PBP file and fetches them."""
    team_log_file = os.path.join("data", "raw", "game_logs", f"team_{ACTIVE_SEASON}.json")
    team_logs = load_json(team_log_file)
    all_game_ids = list({str(r["GAME_ID"]) for r in team_logs if r.get("GAME_ID")})

    existing_pbp = {
        os.path.splitext(os.path.basename(f))[0]
        for f in glob.glob(os.path.join("data", "raw", "pbp", ACTIVE_SEASON, "*.json"))
    }

    missing_games = [gid for gid in all_game_ids if gid not in existing_pbp]
    logger.info(f"PBP Check: {len(existing_pbp)} cached, {len(missing_games)} missing to download.")

    downloaded = 0
    for gid in missing_games:
        out_path = os.path.join("data", "raw", "pbp", ACTIVE_SEASON, f"{gid}.json")
        cdn_url = CDN_PBP_URL.format(game_id=gid)
        try:
            resp = session.get(cdn_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                actions = data.get("game", {}).get("actions", [])
                if actions:
                    normalized = normalize_cdn_actions(actions, gid)
                    write_json(out_path, normalized)
                    downloaded += 1
                    logger.info(f"Downloaded new PBP for Game {gid} ({len(normalized)} events).")
        except Exception as e:
            logger.warning(f"Could not fetch PBP for Game {gid}: {e}")
        polite_delay(0.3, 0.5)

    return downloaded


def sync_hustle_and_lineups(session: requests.Session) -> None:
    """Updates daily active hustle and lineup stats."""
    logger.info("Syncing active season hustle and 5-man lineups...")
    # Hustle Player
    url_hp = f"{NBA_BASE_URL}/leaguehustlestatsplayer"
    params_hp = {"LeagueID": "00", "PerMode": "Totals", "Season": ACTIVE_SEASON, "SeasonType": "Regular Season"}
    try:
        r = session.get(url_hp, params=params_hp, headers=BASE_HEADERS, timeout=25)
        if r.status_code == 200:
            write_json(os.path.join("data", "raw", "hustle", f"player_{ACTIVE_SEASON}.json"), parse_result_set(r.json()))
    except Exception:
        pass

    polite_delay()

    # Lineups
    url_l = f"{NBA_BASE_URL}/leaguedashlineups"
    params_l = {"GroupQuantity": "5", "LeagueID": "00", "MeasureType": "Base", "PerMode": "Totals", "Season": ACTIVE_SEASON, "SeasonType": "Regular Season"}
    try:
        r = session.get(url_l, params=params_l, headers=BASE_HEADERS, timeout=25)
        if r.status_code == 200:
            write_json(os.path.join("data", "raw", "lineups", f"lineups_5man_{ACTIVE_SEASON}.json"), parse_result_set(r.json()))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    start_time = time.time()
    logger.info("==================================================")
    logger.info("SYNC ENGINE: Checking for New Games & Stats")
    logger.info(f"Active Season: {ACTIVE_SEASON}")
    logger.info("==================================================")

    session = requests.Session()

    # 1. Update Game Logs
    sync_game_logs(session)

    # 2. Update Active Shots
    sync_active_shots(session)

    # 3. Pull Missing PBP
    new_pbp = sync_missing_pbp(session)

    # 4. Update Hustle & Lineups
    sync_hustle_and_lineups(session)

    elapsed = time.time() - start_time
    logger.info("==================================================")
    logger.info(f"Sync completed in {elapsed:.2f}s. New PBP games acquired: {new_pbp}")
    logger.info("==================================================")


if __name__ == "__main__":
    main()