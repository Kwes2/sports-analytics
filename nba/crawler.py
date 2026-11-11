"""
crawler.py - Scrapes ESPN NBA schedules, summaries, play-by-play, and rosters.
Accurately detects Overtime (OT) games, periods, scores, and competition types.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import requests
from db import get_existing_completed_game_ids

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def parse_score(score_field):
    if isinstance(score_field, dict):
        val = score_field.get("value", score_field.get("displayValue", 0))
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0
    elif isinstance(score_field, (int, float)):
        return int(score_field)
    elif isinstance(score_field, str) and score_field.replace(".", "", 1).isdigit():
        return int(float(score_field))
    return 0


def determine_season_type(event, comp):
    """
    Identifies competition type:
    2 = Regular Season
    3 = Playoffs / Postseason
    5 = Play-In Tournament
    1 = Preseason / Summer (returns None to discard)
    """
    desc = comp.get("status", {}).get("type", {}).get("description", "").lower()
    name = event.get("name", "").lower()

    if "preseason" in desc or "preseason" in name or "summer" in desc or "summer" in name:
        return None

    date_str = event.get("date", "")[:10]
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            # Discard July, August, September, and early October (preseason)
            if dt.month in [7, 8, 9] or (dt.month == 10 and dt.day < 18):
                return None
            # Playoffs generally run mid-April to June
            if dt.month in [5, 6] or (dt.month == 4 and dt.day >= 18):
                return 3
        except Exception:
            pass

    if "playoff" in desc or "postseason" in name or "playoff" in name:
        return 3
    if "play-in" in desc or "play-in" in name:
        return 5

    return 2


def fetch_team_schedule(team_id, season=2027):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/schedule?season={season}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return r.json().get("events", [])
    except Exception:
        pass
    return []


def fetch_game_summary(event_id):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return event_id, r.json()
    except Exception:
        pass
    return event_id, None


def fetch_single_roster(team_id):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return r.json().get("athletes", [])
    except Exception:
        pass
    return []


def crawl_team_rosters():
    print("Crawling rosters for exact 5-position designations (PG, SG, SF, PF, C)...")
    team_ids = list(range(1, 31))

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_single_roster, team_ids))

    position_map = {}
    for team_athletes in results:
        for athlete_entry in team_athletes:
            items = athlete_entry.get("items", [athlete_entry]) if "items" in athlete_entry else [athlete_entry]
            for ath in items:
                aid = ath.get("id")
                pos_abbrev = ath.get("position", {}).get("abbreviation")
                if aid and pos_abbrev:
                    position_map[str(aid)] = pos_abbrev

    print(f"Roster Positions Loaded: {len(position_map)} players mapped.")
    return position_map


def crawl_full_season_schedule(seasons=[2026, 2027]):
    all_events = {}
    team_ids = list(range(1, 31))

    for season in seasons:
        print(f"Crawling schedule index for Season {season}...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(lambda tid: fetch_team_schedule(tid, season=season), team_ids))

        for team_events in results:
            for event in team_events:
                event_id = event.get("id")
                if event_id and event_id not in all_events:
                    event["_crawl_season"] = season
                    all_events[event_id] = event

    completed_games = []
    upcoming_games = []
    completed_ids = []

    for event_id, event in all_events.items():
        comps = event.get("competitions", [])
        if not comps:
            continue
        comp = comps[0]

        season_type = determine_season_type(event, comp)
        if season_type is None:
            continue

        status_obj = comp.get("status") or event.get("status", {})
        type_obj = status_obj.get("type", {})
        is_completed = (
            type_obj.get("completed", False)
            or type_obj.get("state") == "post"
            or "final" in type_obj.get("description", "").lower()
            or "final" in type_obj.get("name", "").lower()
        )

        # Overtime Detection (Period > 4 or 'OT' in detail text)
        period = int(status_obj.get("period", 4) or 4)
        detail_txt = (type_obj.get("detail", "") or type_obj.get("shortDetail", "") or "").lower()
        is_ot = (period > 4) or ("ot" in detail_txt) or ("final/ot" in detail_txt)

        venue_obj = comp.get("venue", {})
        venue_name = venue_obj.get("fullName", "Unknown Venue")
        city = venue_obj.get("address", {}).get("city", "")
        venue_str = f"{venue_name} ({city})" if city else venue_name
        date_str = event.get("date", "")[:10]
        season_year = event.get("_crawl_season", 2027)

        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)

        if not home or not away:
            continue

        home_team = home.get("team", {}).get("displayName", "Unknown")
        away_team = away.get("team", {}).get("displayName", "Unknown")
        home_team_id = str(home.get("team", {}).get("id", ""))
        away_team_id = str(away.get("team", {}).get("id", ""))

        if is_completed:
            home_score = parse_score(home.get("score"))
            away_score = parse_score(away.get("score"))
            margin = home_score - away_score

            completed_games.append({
                "game_id": event_id,
                "season_year": season_year,
                "season_type": season_type,
                "date": date_str,
                "box_score": f"boxscore.html?id={event_id}",
                "venue": venue_str,
                "home_team": home_team,
                "home_team_id": home_team_id,
                "away_team": away_team,
                "away_team_id": away_team_id,
                "home_score": home_score,
                "away_score": away_score,
                "margin": margin,
                "total_points": home_score + away_score,
                "is_overtime": is_ot,
                "overtime_periods": max(0, period - 4) if is_ot else 0
            })
            completed_ids.append(event_id)
        else:
            if season_year == 2027:
                time_str = type_obj.get("shortDetail") or event.get("status", {}).get("type", {}).get("shortDetail", "Scheduled")
                upcoming_games.append({
                    "date": date_str,
                    "time": time_str,
                    "venue": venue_str,
                    "home_team": home_team,
                    "away_team": away_team
                })

    completed_games.sort(key=lambda x: x["date"], reverse=True)
    upcoming_games.sort(key=lambda x: x["date"])

    print(f"Legitimate Games Indexed: {len(completed_games)} completed, {len(upcoming_games)} upcoming.")
    return completed_games, upcoming_games, completed_ids


def crawl_game_summaries(event_ids):
    already_saved_ids = get_existing_completed_game_ids()
    new_ids = [eid for eid in event_ids if eid not in already_saved_ids]

    print(f"Cache check: {len(already_saved_ids)} games already saved in database.")
    print(f"New games to download: {len(new_ids)}")

    if not new_ids:
        print("All games up to date! Zero network downloads needed.")
        return {}

    with ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(fetch_game_summary, new_ids))

    return {eid: data for eid, data in results if data is not None}


def crawl_team_standings():
    url = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
    try:
        return requests.get(url, headers=HEADERS, timeout=8).json()
    except Exception:
        return {}