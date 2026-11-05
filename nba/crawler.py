from concurrent.futures import ThreadPoolExecutor
import requests

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


def fetch_team_schedule(team_id):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/schedule"
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


def crawl_full_season_schedule():
    print("Crawling season schedules for all 30 NBA teams...")
    team_ids = list(range(1, 31))

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_team_schedule, team_ids))

    all_events = {}
    for team_events in results:
        for event in team_events:
            event_id = event.get("id")
            if event_id and event_id not in all_events:
                all_events[event_id] = event

    completed_games = []
    upcoming_games = []
    completed_ids = []

    for event_id, event in all_events.items():
        comps = event.get("competitions", [])
        if not comps:
            continue
        comp = comps[0]

        status_obj = comp.get("status") or event.get("status", {})
        type_obj = status_obj.get("type", {})
        is_completed = (
            type_obj.get("completed", False)
            or type_obj.get("state") == "post"
            or "final" in type_obj.get("description", "").lower()
            or "final" in type_obj.get("name", "").lower()
        )

        venue_obj = comp.get("venue", {})
        venue_name = venue_obj.get("fullName", "Unknown Venue")
        city = venue_obj.get("address", {}).get("city", "")
        venue_str = f"{venue_name} ({city})" if city else venue_name
        date_str = event.get("date", "")[:10]

        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)

        if not home or not away:
            continue

        home_team = home.get("team", {}).get("displayName", "Unknown")
        away_team = away.get("team", {}).get("displayName", "Unknown")

        if is_completed:
            home_score = parse_score(home.get("score"))
            away_score = parse_score(away.get("score"))
            margin = home_score - away_score

            completed_games.append({
                "date": date_str,
                "box_score": f"boxscore.html?id={event_id}",
                "venue": venue_str,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "margin": margin,
                "total_points": home_score + away_score
            })
            completed_ids.append(event_id)
        else:
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

    print(f"Schedule Crawled: {len(completed_games)} completed games, {len(upcoming_games)} upcoming.")
    return completed_games, upcoming_games, completed_ids


def crawl_game_summaries(event_ids):
    print(f"Downloading box scores and play-by-play for {len(event_ids)} games concurrently...")
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(fetch_game_summary, event_ids))
    return {eid: data for eid, data in results if data is not None}


def crawl_team_standings():
    url = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
    try:
        return requests.get(url, headers=HEADERS, timeout=8).json()
    except Exception:
        return {}