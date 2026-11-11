"""
fetch_and_compute.py - Core data compilation pipeline. Crawls ESPN, populates 
SQLite database, calculates advanced metrics, RAPM, and exports structured JSONs.
Calculates exact assisted/unassisted splits from assisted_baskets.
"""

import json
from pathlib import Path

from crawler import (
    crawl_team_rosters,
    crawl_full_season_schedule,
    crawl_game_summaries,
    crawl_team_standings,
    parse_score
)
from shots import (
    ZONES,
    GRANULAR_ZONES,
    init_zone_dict,
    init_granular_dict,
    process_game_shots,
    compute_shot_quality_metrics,
    compute_three_point_zone_splits,
    classify_shot_distance,
    classify_shot_granular
)
from stats import (
    process_boxscore_players,
    extract_detailed_assists_from_plays,
    compute_assist_connection_metrics,
    compute_player_advanced_metrics,
    compute_team_standings,
    compute_team_advanced_metrics,
    compute_player_situational_splits,
    compute_team_situational_splits,
    compute_on_off_metrics,
    compute_xprf_metrics
)
from percentiles import (
    compute_percentile,
    build_stat_pools,
    build_shot_pools,
    compute_player_rankings_and_percentiles
)
from stints import StintTracker
from baselines import BaselineEngine
from influence import InfluenceEngine
from db import init_db, bulk_insert, optimize_db, DB_PATH
from stat_metadata import STAT_METADATA, get_stat_meta, export_metadata_json

DATA_DIR = Path(__file__).parent / "data"
BOX_DIR = DATA_DIR / "boxscores"
PLAYER_DIR = DATA_DIR / "players"
TEAM_DIR = DATA_DIR / "teams"
WINDOWS_DIR = DATA_DIR / "windows"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BOX_DIR.mkdir(parents=True, exist_ok=True)
PLAYER_DIR.mkdir(parents=True, exist_ok=True)
TEAM_DIR.mkdir(parents=True, exist_ok=True)
WINDOWS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("Initializing SQLite Database (nba.db)...")
    init_db(DB_PATH)

    print("Exporting centralized stat definitions metadata...")
    export_metadata_json(DATA_DIR / "stat_definitions.json")

    position_map = crawl_team_rosters()
    completed_games, upcoming_games, completed_ids = crawl_full_season_schedule(seasons=[2026, 2027])

    with open(DATA_DIR / "completed_games.json", "w") as f:
        json.dump({
            "meta_keys": ["date", "box_score", "venue", "home_team", "away_team"],
            "rows": completed_games
        }, f, indent=2)

    with open(DATA_DIR / "upcoming_games.json", "w") as f:
        json.dump({
            "meta_keys": ["date", "time", "venue", "home_team", "away_team"],
            "rows": upcoming_games
        }, f, indent=2)

    standings_raw = crawl_team_standings()
    team_rows = compute_team_standings(standings_raw)
    team_scoring_map = {t["team_id"]: t["pts_pg"] for t in team_rows}
    team_scoring_by_name = {t["team"]: t["pts_pg"] for t in team_rows}

    summaries = crawl_game_summaries(completed_ids)

    players = {}
    player_names_map = {}
    team_season_shots = {}
    team_game_stats_ledger = {}
    all_season_assisted_plays = []
    league_granular_shots = init_granular_dict()

    db_games_rows = []
    db_player_logs_rows = []
    db_shots_rows = []
    db_assisted_rows = []
    db_stints_rows = []
    db_players_lookup = {}

    merged_pair_ledger = {}
    player_game_stints_history = {}
    all_games_stints = []
    all_game_performances = []

    for event_id, data in summaries.items():
        boxscore_data = data.get("boxscore", {})
        game_players = boxscore_data.get("players", [])
        plays = data.get("plays", [])
        header_info = data.get("header", {})
        comp = header_info.get("competitions", [{}])[0]

        venue_str = comp.get("venue", {}).get("fullName", "Unknown Venue")
        date_str = comp.get("date", "")[:10]
        season_year = 2026 if "2025" in date_str or ("2026" in date_str and int(date_str[5:7]) < 7) else 2027
        season_type = 2

        competitors = comp.get("competitors", [])
        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})

        home_name = home_comp.get("team", {}).get("displayName", "Home")
        away_name = away_comp.get("team", {}).get("displayName", "Away")
        home_abbrev = home_comp.get("team", {}).get("abbreviation", "HOME")
        away_abbrev = away_comp.get("team", {}).get("abbreviation", "AWAY")
        home_id = str(home_comp.get("team", {}).get("id", "home"))
        away_id = str(away_comp.get("team", {}).get("id", "away"))

        home_score = parse_score(home_comp.get("score"))
        away_score = parse_score(away_comp.get("score"))

        db_games_rows.append((
            event_id, season_year, season_type,
            date_str, home_id, away_id, home_name, away_name, home_score, away_score
        ))

        team_shots, game_player_shots, game_player_granular = process_game_shots(plays, home_id, away_id)
        game_team_rows, player_events = process_boxscore_players(
            game_players, home_abbrev, away_abbrev, home_score, away_score, date_str, position_map
        )

        game_assists = extract_detailed_assists_from_plays(plays)
        all_season_assisted_plays.extend(game_assists)

        for ga in game_assists:
            db_assisted_rows.append((
                event_id, season_year, season_type, date_str, ga["team_id"], ga["passer_id"], ga["scorer_id"], ga["val"], ga["zone"]
            ))

        home_starters = [r["player_id"] for r in game_team_rows.get(home_id, {}).get("starters", [])]
        away_starters = [r["player_id"] for r in game_team_rows.get(away_id, {}).get("starters", [])]
        if home_starters and away_starters:
            stint_tracker = StintTracker(home_starters, away_starters, home_id, away_id)
            game_player_stints = {}
            game_stints_collector = []
            
            for play in plays:
                stint_tracker.process_play(play, merged_pair_ledger, game_player_stints, game_stints_collector, event_id, date_str)
            stint_tracker.commit_stint(merged_pair_ledger, game_player_stints, game_stints_collector, event_id, date_str)

            for s in game_stints_collector:
                db_stints_rows.append((
                    s[0], season_year, season_type, s[1], s[2], s[3], s[4], s[5],
                    stint_tracker.home_reb_stint, stint_tracker.away_reb_stint, s[6]
                ))
                all_games_stints.append({
                    "home_lineup": json.loads(s[2]),
                    "away_lineup": json.loads(s[3]),
                    "home_pts": s[4],
                    "away_pts": s[5],
                    "poss": s[6]
                })

            for p_id, g_stint in game_player_stints.items():
                if p_id not in player_game_stints_history:
                    player_game_stints_history[p_id] = []
                player_game_stints_history[p_id].append(g_stint)

        for play in plays:
            coord = play.get("coordinate")
            text = play.get("text", "")
            is_shooting = play.get("scoringPlay", False)

            if coord and ("x" in coord and "y" in coord) and (is_shooting or "shot" in text.lower() or "jumper" in text.lower() or "layup" in text.lower() or "dunk" in text.lower()):
                cx, cy = coord["x"], coord["y"]
                is_three = ("three point" in text.lower() or "3pt" in text.lower())
                z = classify_shot_distance(cx, cy)
                gz = classify_shot_granular(cx, cy, is_three)
                sh_id = str(play.get("participants", [{}])[0].get("athlete", {}).get("id", ""))
                is_made = 1 if (play.get("scoringPlay") and "missed" not in text.lower()) else 0
                val = 3 if is_three else 2

                if sh_id:
                    db_shots_rows.append((event_id, season_year, season_type, date_str, sh_id, val, is_made, z, gz))

        for tid in [home_id, away_id]:
            if tid not in team_season_shots:
                team_season_shots[tid] = init_zone_dict()
            for z in ZONES:
                team_season_shots[tid][z]["fga"] += team_shots[tid][z]["fga"]
                team_season_shots[tid][z]["fgm"] += team_shots[tid][z]["fgm"]

        def sum_team_stat(t_id, key):
            rows = game_team_rows.get(t_id, {}).get("all_rows", [])
            return sum(r.get(key, 0) for r in rows)

        h_fga, h_fgm, h_fg3m, h_fta, h_to, h_oreb, h_dreb = (
            sum_team_stat(home_id, "fga"), sum_team_stat(home_id, "fgm"), sum_team_stat(home_id, "fg3m"),
            sum_team_stat(home_id, "fta"), sum_team_stat(home_id, "to"), sum_team_stat(home_id, "oreb"), sum_team_stat(home_id, "dreb")
        )
        a_fga, a_fgm, a_fg3m, a_fta, a_to, a_oreb, a_dreb = (
            sum_team_stat(away_id, "fga"), sum_team_stat(away_id, "fgm"), sum_team_stat(away_id, "fg3m"),
            sum_team_stat(away_id, "fta"), sum_team_stat(away_id, "to"), sum_team_stat(away_id, "oreb"), sum_team_stat(away_id, "dreb")
        )

        for tid, name, pts, fga, fgm, fg3m, fta, to, oreb, dreb, opp_pts, o_fga, o_fgm, o_fg3m, o_fta, o_to, o_oreb, o_dreb in [
            (home_id, home_name, home_score, h_fga, h_fgm, h_fg3m, h_fta, h_to, h_oreb, h_dreb, away_score, a_fga, a_fgm, a_fg3m, a_fta, a_to, a_oreb, a_dreb),
            (away_id, away_name, away_score, a_fga, a_fgm, a_fg3m, a_fta, a_to, a_oreb, a_dreb, home_score, h_fga, h_fgm, h_fg3m, h_fta, h_to, h_oreb, h_dreb)
        ]:
            if tid not in team_game_stats_ledger:
                team_game_stats_ledger[tid] = []
            team_game_stats_ledger[tid].append({
                "date": date_str, "pts": pts, "opp_pts": opp_pts, "fga": fga, "fgm": fgm, "fg3m": fg3m,
                "fta": fta, "to": to, "oreb": oreb, "dreb": dreb, "opp_fga": o_fga, "opp_fgm": o_fgm,
                "opp_fg3m": o_fg3m, "opp_fta": o_fta, "opp_to": o_to, "opp_oreb": o_oreb, "opp_dreb": o_dreb
            })

        for aid, s_zones in game_player_shots.items():
            if aid not in players:
                players[aid] = {
                    "player_id": aid, "player": "Unknown", "team": "", "team_id": "", "team_abbrev": "", "pos": "-",
                    "gp": 0, "gs": 0, "tot_min": 0.0, "tot_pts": 0, "tot_reb": 0, "tot_ast": 0, "tot_stl": 0, "tot_blk": 0,
                    "tot_to": 0, "tot_fgm": 0, "tot_fga": 0, "tot_fg3m": 0, "tot_fg3a": 0, "tot_ftm": 0, "tot_fta": 0,
                    "tot_oreb": 0, "tot_dreb": 0, "tot_pf": 0, "tot_plus_minus": 0, "game_logs": [],
                    "zone_shots": init_zone_dict(), "granular_shots": init_granular_dict()
                }
            for z in ZONES:
                players[aid]["zone_shots"][z]["fga"] += s_zones[z]["fga"]
                players[aid]["zone_shots"][z]["fgm"] += s_zones[z]["fgm"]

        for aid, g_zones in game_player_granular.items():
            if aid in players:
                for gz in GRANULAR_ZONES:
                    players[aid]["granular_shots"][gz]["fga"] += g_zones[gz]["fga"]
                    players[aid]["granular_shots"][gz]["fgm"] += g_zones[gz]["fgm"]
                    players[aid]["granular_shots"][gz]["fg3m"] += g_zones[gz]["fg3m"]
                    league_granular_shots[gz]["fga"] += g_zones[gz]["fga"]
                    league_granular_shots[gz]["fgm"] += g_zones[gz]["fgm"]
                    league_granular_shots[gz]["fg3m"] += g_zones[gz]["fg3m"]

        for aid, ev in player_events.items():
            player_names_map[aid] = ev["player"]
            db_players_lookup[aid] = (aid, ev["player"], ev["team_id"], ev["team_abbrev"], ev["pos"])

            if aid not in players:
                players[aid] = {
                    "player_id": aid, "player": ev["player"], "team": ev["team"], "team_id": ev["team_id"],
                    "team_abbrev": ev["team_abbrev"], "pos": ev["pos"], "gp": 0, "gs": 0, "tot_min": 0.0, "tot_pts": 0,
                    "tot_reb": 0, "tot_ast": 0, "tot_stl": 0, "tot_blk": 0, "tot_to": 0, "tot_fgm": 0, "tot_fga": 0,
                    "tot_fg3m": 0, "tot_fg3a": 0, "tot_ftm": 0, "tot_fta": 0, "tot_oreb": 0, "tot_dreb": 0, "tot_pf": 0,
                    "tot_plus_minus": 0, "game_logs": [], "zone_shots": init_zone_dict(), "granular_shots": init_granular_dict()
                }

            p = players[aid]
            p["player"] = ev["player"]
            p["team"] = ev["team"]
            p["team_id"] = ev["team_id"]
            p["team_abbrev"] = ev["team_abbrev"]
            p["pos"] = ev["pos"]
            p["gp"] += 1
            if ev["is_starter"]:
                p["gs"] += 1
            p["tot_min"] += ev["minutes"]
            p["tot_pts"] += ev["pts"]
            p["tot_reb"] += ev["reb"]
            p["tot_ast"] += ev["ast"]
            p["tot_stl"] += ev["stl"]
            p["tot_blk"] += ev["blk"]
            p["tot_to"] += ev["to"]
            p["tot_fgm"] += ev["fgm"]
            p["tot_fga"] += ev["fga"]
            p["tot_fg3m"] += ev["fg3m"]
            p["tot_fg3a"] += ev["fg3a"]
            p["tot_ftm"] += ev["ftm"]
            p["tot_fta"] += ev["fta"]
            p["tot_oreb"] += ev["oreb"]
            p["tot_dreb"] += ev["dreb"]
            p["tot_pf"] += ev["pf"]
            p["tot_plus_minus"] += ev["plus_minus"]
            p["game_logs"].append(ev["log"])

            is_w = ev["log"]["result"].startswith("W")
            is_ot = ("OT" in ev["log"]["result"])
            res_token = ("OT-W" if is_w else "OT-L") if is_ot else ("W" if is_w else "L")

            all_game_performances.append({
                "player_id": aid,
                "player": ev["player"],
                "team": ev["team_abbrev"],
                "team_id": ev["team_id"],
                "pos": ev["pos"],
                "starter": 1 if ev["is_starter"] else 0,
                "date": date_str,
                "opponent": ev["log"]["opponent"],
                "result": res_token,
                "min": int(ev["minutes"]),
                "pts": ev["pts"],
                "reb": ev["reb"],
                "ast": ev["ast"],
                "stl": ev["stl"],
                "blk": ev["blk"],
                "to": ev["to"],
                "pf": ev["pf"],
                "plus_minus": ev["plus_minus"],
                "fgm": ev["fgm"],
                "fga": ev["fga"],
                "fg_pct": round(ev["fgm"] / ev["fga"] * 100, 1) if ev["fga"] > 0 else 0.0,
                "fg3m": ev["fg3m"],
                "fg3a": ev["fg3a"],
                "fg3_pct": round(ev["fg3m"] / ev["fg3a"] * 100, 1) if ev["fg3a"] > 0 else 0.0,
                "ftm": ev["ftm"],
                "fta": ev["fta"],
                "ft_pct": round(ev["ftm"] / ev["fta"] * 100, 1) if ev["fta"] > 0 else 0.0,
                "oreb": ev["oreb"],
                "dreb": ev["dreb"],
                "gmsc": ev["log"]["gmsc"],
                "ts_pct": ev["log"]["ts_pct"],
                "box_score": f"boxscore.html?id={event_id}"
            })

            db_player_logs_rows.append((
                aid, event_id, season_year, season_type, date_str, 1 if ev["is_starter"] else 0, ev["minutes"],
                ev["pts"], ev["reb"], ev["ast"], ev["stl"], ev["blk"], ev["to"], ev["pf"], ev["plus_minus"],
                ev["fgm"], ev["fga"], ev["fg3m"], ev["fg3a"], ev["ftm"], ev["fta"], ev["oreb"], ev["dreb"]
            ))

        game_four_factors = [
            {"team": home_name, **compute_team_advanced_metrics(home_name, [team_game_stats_ledger[home_id][-1]])},
            {"team": away_name, **compute_team_advanced_metrics(away_name, [team_game_stats_ledger[away_id][-1]])}
        ]

        pbp_rows = []
        for play in plays:
            txt = play.get("text", "")
            if txt:
                pbp_rows.append({
                    "period": play.get("period", {}).get("displayValue", f"Q{play.get('period', {}).get('number', 1)}"),
                    "clock": play.get("clock", {}).get("displayValue", "00:00"),
                    "team": home_abbrev if str(play.get("team", {}).get("id")) == home_id else away_abbrev,
                    "event": txt
                })

        box_teams = []
        for t_id, t_info in game_team_rows.items():
            splits = team_shots.get(t_id, init_zone_dict())
            tot_fga = sum(splits[z]["fga"] for z in ZONES)
            split_rows = []
            for z in ZONES:
                fgm = splits[z]["fgm"]
                fga = splits[z]["fga"]
                pct = round(fgm / fga * 100, 1) if fga > 0 else 0.0
                share = round(fga / tot_fga * 100, 1) if tot_fga > 0 else 0.0
                split_rows.append({"zone": z, "fgm": fgm, "fga": fga, "fg_pct": pct, "shot_share": share})

            box_teams.append({
                "team_name": t_info["team_name"],
                "team_id": t_id,
                "team_abbrev": t_info["team_abbrev"],
                "starters": t_info["starters"],
                "bench": t_info["bench"],
                "shooting_splits": {"meta_keys": ["zone"], "rows": split_rows},
                "meta_keys": ["player", "starter", "pos"],
                "rows": t_info["all_rows"]
            })

        with open(BOX_DIR / f"{event_id}.json", "w") as f:
            json.dump({
                "game_id": event_id, "date": date_str, "venue": venue_str,
                "home_team": home_name, "home_score": home_score, "home_team_id": home_id,
                "away_team": away_name, "away_score": away_score, "away_team_id": away_id,
                "four_factors": {"meta_keys": ["team"], "rows": game_four_factors},
                "play_by_play": {"meta_keys": ["period", "clock", "team"], "rows": pbp_rows},
                "teams": box_teams
            }, f, indent=2)

    print("Writing optimized atomic tables to SQLite Database (nba.db)...")
    bulk_insert(DB_PATH, "players", [
        "player_id", "player_name", "team_id", "team_abbrev", "pos"
    ], list(db_players_lookup.values()))

    bulk_insert(DB_PATH, "games", [
        "game_id", "season_year", "season_type", "date", "home_team_id", "away_team_id",
        "home_team_name", "away_team_name", "home_score", "away_score"
    ], db_games_rows)

    bulk_insert(DB_PATH, "player_game_logs", [
        "player_id", "game_id", "season_year", "season_type", "date", "is_starter", "minutes", "pts", "reb", "ast", "stl", "blk", "to_val", "pf",
        "plus_minus", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb"
    ], db_player_logs_rows)

    bulk_insert(DB_PATH, "shots", [
        "game_id", "season_year", "season_type", "date", "shooter_id", "val", "made", "zone", "granular_zone"
    ], db_shots_rows)

    bulk_insert(DB_PATH, "assisted_baskets", [
        "game_id", "season_year", "season_type", "date", "team_id", "passer_id", "scorer_id", "val", "zone"
    ], db_assisted_rows)

    bulk_insert(DB_PATH, "stints", [
        "game_id", "season_year", "season_type", "date", "home_lineup", "away_lineup", "home_pts", "away_pts", "home_reb", "away_reb", "poss"
    ], db_stints_rows)

    optimize_db(DB_PATH)

    all_game_performances.sort(key=lambda x: (x["date"], x["pts"]), reverse=True)
    with open(DATA_DIR / "game_performances.json", "w") as f:
        json.dump({
            "meta_keys": ["date", "player", "starter", "team", "opponent", "result"],
            "rows": all_game_performances[:1500]
        }, f, indent=2)

    league_granular_efg = {}
    for gz in GRANULAR_ZONES:
        fga = league_granular_shots[gz]["fga"]
        fgm = league_granular_shots[gz]["fgm"]
        fg3m = league_granular_shots[gz]["fg3m"]
        if fga > 0:
            league_granular_efg[gz] = round((fgm + 0.5 * fg3m) / fga * 100, 1)
        else:
            league_granular_efg[gz] = 50.0

    team_total_rebs = {}
    for tid, g_list in team_game_stats_ledger.items():
        team_total_rebs[tid] = sum((g.get("oreb", 0) + g.get("dreb", 0)) for g in g_list)

    # Build Assist Network Maps
    passer_finisher_map = {}
    finisher_passer_map = {}
    all_passer_events_map = {}

    for ev in all_season_assisted_plays:
        p_id = ev["passer_id"]
        s_id = ev["scorer_id"]

        if p_id not in all_passer_events_map:
            all_passer_events_map[p_id] = []
        all_passer_events_map[p_id].append(ev)

        if p_id not in passer_finisher_map:
            passer_finisher_map[p_id] = {}
        if s_id not in passer_finisher_map[p_id]:
            passer_finisher_map[p_id][s_id] = []
        passer_finisher_map[p_id][s_id].append(ev)

        if s_id not in finisher_passer_map:
            finisher_passer_map[s_id] = {}
        if p_id not in finisher_passer_map[s_id]:
            finisher_passer_map[s_id][p_id] = []
        finisher_passer_map[s_id][p_id].append(ev)

    active_players = {}
    for aid, p in players.items():
        if p["gp"] == 0:
            continue
        gp = p["gp"]
        gs = p["gs"]
        min_pg = round(p["tot_min"] / gp, 1) if gp > 0 else 0.0
        pts_pg = round(p["tot_pts"] / gp, 1) if gp > 0 else 0.0
        reb_pg = round(p["tot_reb"] / gp, 1) if gp > 0 else 0.0
        ast_pg = round(p["tot_ast"] / gp, 1) if gp > 0 else 0.0
        stl_pg = round(p["tot_stl"] / gp, 1) if gp > 0 else 0.0
        blk_pg = round(p["tot_blk"] / gp, 1) if gp > 0 else 0.0
        to_pg = round(p["tot_to"] / gp, 1) if gp > 0 else 0.0
        pf_pg = round(p["tot_pf"] / gp, 1) if gp > 0 else 0.0
        plus_minus_pg = round(p["tot_plus_minus"] / gp, 1) if gp > 0 else 0.0

        fgm_pg = round(p["tot_fgm"] / gp, 1)
        fga_pg = round(p["tot_fga"] / gp, 1)
        fg_pct = round((p["tot_fgm"] / p["tot_fga"]) * 100, 1) if p["tot_fga"] > 0 else 0.0

        fg3m_pg = round(p["tot_fg3m"] / gp, 1)
        fg3a_pg = round(p["tot_fg3a"] / gp, 1)
        fg3_pct = round((p["tot_fg3m"] / p["tot_fg3a"]) * 100, 1) if p["tot_fg3a"] > 0 else 0.0

        ftm_pg = round(p["tot_ftm"] / gp, 1)
        fta_pg = round(p["tot_fta"] / gp, 1)
        ft_pct = round((p["tot_ftm"] / p["tot_fta"]) * 100, 1) if p["tot_fta"] > 0 else 0.0

        oreb_pg = round(p["tot_oreb"] / gp, 1)
        dreb_pg = round(p["tot_dreb"] / gp, 1)

        p["game_logs"].sort(key=lambda x: x["date"], reverse=True)
        
        adv = compute_player_advanced_metrics(p)
        
        # 1. Authentic Team Rebound Share %
        t_id = str(p.get("team_id"))
        t_tot_reb = team_total_rebs.get(t_id, 0)
        team_reb_share = round((p["tot_reb"] / t_tot_reb * 100.0), 1) if t_tot_reb > 0 else 0.0

        # 2. Authentic On-Court Available Rebound %
        p_stints = player_game_stints_history.get(aid, [])
        total_avail_on_court = sum((st.get("team_reb", 0) + st.get("opp_reb", 0)) for st in p_stints)
        if total_avail_on_court > 0:
            on_court_reb_pct = round((p["tot_reb"] / total_avail_on_court * 100.0), 1)
        else:
            avail_fallback = (p["tot_min"] / 48.0) * 87.5
            on_court_reb_pct = round((p["tot_reb"] / avail_fallback * 100.0), 1) if avail_fallback > 0 else 0.0

        adv["team_reb_share"] = team_reb_share
        adv["on_court_reb_pct"] = on_court_reb_pct

        # 3. Authentic Assisted vs Unassisted Shot Splits from assisted_baskets
        received_assists = []
        for passer_ev_list in finisher_passer_map.get(aid, {}).values():
            received_assists.extend(passer_ev_list)

        tot_assisted_makes = len(received_assists)
        tot_assisted_3s = sum(1 for ev in received_assists if ev.get("val") == 3)

        tot_fgm = p["tot_fgm"]
        tot_fg3m = p.get("tot_fg3m", 0)

        ast_fg_pct = round(tot_assisted_makes / tot_fgm * 100.0, 1) if tot_fgm > 0 else 0.0
        unast_fg_pct = round(max(0.0, 100.0 - ast_fg_pct), 1)

        ast_3p_pct = round(tot_assisted_3s / tot_fg3m * 100.0, 1) if tot_fg3m > 0 else 0.0
        unast_3p_pct = round(max(0.0, 100.0 - ast_3p_pct), 1)

        ast_splits = {
            "ast_fg_pct": ast_fg_pct,
            "unast_fg_pct": unast_fg_pct,
            "ast_3p_pct": ast_3p_pct,
            "unast_3p_pct": unast_3p_pct
        }

        sq_metrics = compute_shot_quality_metrics(
            p["granular_shots"], league_granular_efg, p["tot_fta"], p["tot_fga"]
        )
        three_splits = compute_three_point_zone_splits(p["granular_shots"], gp)

        p_on_court = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
        for st in p_stints:
            p_on_court["pts_for"] += st.get("pts_for", 0)
            p_on_court["pts_against"] += st.get("pts_against", 0)
            p_on_court["poss"] += st.get("poss", 0.0)

        t_totals = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
        for g_stints in team_game_stats_ledger.get(t_id, []):
            t_totals["pts_for"] += g_stints["pts"]
            t_totals["pts_against"] += g_stints["opp_pts"]
            t_poss = 0.96 * (g_stints["fga"] + g_stints["to"] + 0.44 * g_stints["fta"] - g_stints["oreb"])
            t_totals["poss"] += t_poss

        on_off = compute_on_off_metrics(p_on_court, t_totals)

        active_players[aid] = {
            "player_id": aid, "name": p["player"], "team": p["team"], "team_id": p["team_id"],
            "team_abbrev": p["team_abbrev"], "pos": p["pos"],
            "averages": {
                "gp": gp, "gs": gs, "min_pg": min_pg, "pts_pg": pts_pg, "reb_pg": reb_pg, "ast_pg": ast_pg,
                "stl_pg": stl_pg, "blk_pg": blk_pg, "to_pg": to_pg, "pf_pg": pf_pg, "plus_minus_pg": plus_minus_pg,
                "fgm_pg": fgm_pg, "fga_pg": fga_pg, "fg_pct": fg_pct,
                "fg3m_pg": fg3m_pg, "fg3a_pg": fg3a_pg, "fg3_pct": fg3_pct,
                "ftm_pg": ftm_pg, "fta_pg": fta_pg, "ft_pct": ft_pct,
                "oreb_pg": oreb_pg, "dreb_pg": dreb_pg
            },
            "advanced": {**adv, **sq_metrics, **three_splits, **ast_splits},
            "on_off": on_off,
            "zone_shots": p["zone_shots"],
            "game_logs": p["game_logs"]
        }

    print("Evaluating simultaneous Decomposed RAPM across all line-up stints...")
    baseline_engine = BaselineEngine(active_players, player_game_stints_history, team_game_stats_ledger)
    influence_engine = InfluenceEngine(active_players, baseline_engine, merged_pair_ledger, all_games_stints=all_games_stints)
    player_influence_map = influence_engine.attr

    league_zone_totals = init_zone_dict()
    for p in active_players.values():
        for z in ZONES:
            league_zone_totals[z]["fgm"] += p["zone_shots"][z]["fgm"]
            league_zone_totals[z]["fga"] += p["zone_shots"][z]["fga"]

    league_avg_fg = {
        z: round(league_zone_totals[z]["fgm"] / league_zone_totals[z]["fga"] * 100, 1) if league_zone_totals[z]["fga"] > 0 else 0.0
        for z in ZONES
    }

    for aid, p in active_players.items():
        p_events = all_passer_events_map.get(aid, [])
        gp = p["averages"]["gp"]
        metrics = compute_assist_connection_metrics(p_events, league_avg_fg, active_players)

        if metrics:
            pts_created_pg = round(metrics["pts_created"] / gp, 1) if gp > 0 else 0.0
            points_added_pg = round(metrics["points_added"] / gp, 2) if gp > 0 else 0.0
            tot_a = metrics["assists"]
            rim_pct = round(metrics["rim_ast"] / tot_a * 100, 1) if tot_a > 0 else 0.0
            three_pct = round(metrics["three_pt_ast"] / tot_a * 100, 1) if tot_a > 0 else 0.0

            p["passing_profile"] = {
                "ast_recorded": tot_a,
                "pts_created_pg": pts_created_pg,
                "pts_per_ast": metrics["pts_per_ast"],
                "xpts_per_ast": metrics["xpts_per_ast"],
                "paoe": metrics["paoe"],
                "points_added_pg": points_added_pg,
                "rim_ast_pct": rim_pct,
                "three_ast_pct": three_pct
            }
        else:
            p["passing_profile"] = {
                "ast_recorded": 0, "pts_created_pg": 0.0, "pts_per_ast": 0.0,
                "xpts_per_ast": 0.0, "paoe": 0.0, "points_added_pg": 0.0,
                "rim_ast_pct": 0.0, "three_ast_pct": 0.0
            }

        pts_pg = p["averages"]["pts_pg"]
        pts_created_pg = p["passing_profile"]["pts_created_pg"]
        prf_pg = round(pts_pg + pts_created_pg, 1)
        team_pts_pg = team_scoring_map.get(p["team_id"]) or team_scoring_by_name.get(p["team"], 115.0)
        pct_team_prf = round(prf_pg / team_pts_pg * 100, 1) if team_pts_pg > 0 else 0.0

        p["prf_metrics"] = {
            "prf_pg": prf_pg,
            "pct_team_prf": pct_team_prf
        }

        fga = p["averages"]["fga_pg"] * gp
        fg3a = p["averages"]["fg3a_pg"] * gp
        fta = p["averages"]["fta_pg"] * gp
        tot_xpts = p["passing_profile"]["xpts_per_ast"] * p["passing_profile"]["ast_recorded"]
        xprf_data = compute_xprf_metrics(
            fga=fga,
            xfg_pct=p["advanced"].get("xefg_pct", 50.0),
            fg3a=fg3a,
            x3p_pct=36.0,
            fta=fta,
            xft_pct=78.0,
            expected_assist_pts=tot_xpts,
            actual_prf_pg=prf_pg,
            gp=gp
        )
        p["prf_metrics"].update(xprf_data)

        p["influence_metrics"] = player_influence_map.get(aid, {
            "orapm": 0.0, "drapm": 0.0, "net_rapm": 0.0
        })

        tot_fga = sum(p["zone_shots"][z]["fga"] for z in ZONES)
        zone_summary = {}
        for z, label in [("0-4 ft", "rim"), ("4-14 ft", "mid"), ("14+ ft", "three")]:
            fgm = p["zone_shots"][z]["fgm"]
            fga = p["zone_shots"][z]["fga"]
            pct = round(fgm / fga * 100, 1) if fga > 0 else 0.0
            share = round(fga / tot_fga * 100, 1) if tot_fga > 0 else 0.0
            zone_summary[f"{label}_fga_pg"] = round(fga / gp, 1) if gp > 0 else 0.0
            zone_summary[f"{label}_fg_pct"] = pct
            zone_summary[f"{label}_share"] = share

        p["zone_summary"] = zone_summary

    stat_keys = list(STAT_METADATA.keys())
    league_pools, pos_pools = build_stat_pools(active_players, stat_keys)
    vol_pools, eff_pools = build_shot_pools(active_players, ZONES)

    all_player_stats_rows = []

    for aid, p in active_players.items():
        pos = p["pos"]
        combined = {
            **p["averages"],
            **p["advanced"],
            **p["on_off"],
            **p["passing_profile"],
            **p["prf_metrics"],
            **p["influence_metrics"],
            **p["zone_summary"]
        }

        rankings_data = compute_player_rankings_and_percentiles(
            combined, league_pools, pos_pools, pos, stat_keys
        )

        categorized_tables = {
            "Basic": [],
            "Advanced": [],
            "Shooting": [],
            "Passing": [],
            "Ratings": [],
            "Miscellaneous": []
        }

        for k, v in combined.items():
            meta = get_stat_meta(k)
            cat = meta.get("category", "Miscellaneous")
            if cat not in categorized_tables:
                cat = "Miscellaneous"

            r_info = rankings_data.get(k, {
                "value": v, "league_rank": "-", "league_percentile": 50.0,
                "pos_rank": "-", "pos_percentile": 50.0
            })

            categorized_tables[cat].append({
                "stat_key": k,
                "stat_name": meta["name"],
                "value": v,
                "tooltip": meta.get("tooltip", ""),
                "league_rank": r_info["league_rank"],
                "league_percentile": r_info["league_percentile"],
                "pos_rank": r_info["pos_rank"],
                "pos_percentile": r_info["pos_percentile"]
            })

        sections = []
        for cat_name, rows in categorized_tables.items():
            if rows:
                sections.append({
                    "type": "long_form_stats",
                    "title": f"{cat_name} Statistics",
                    "category": cat_name,
                    "data": {
                        "meta_keys": ["stat_name"],
                        "rows": rows
                    }
                })

        tot_fga = sum(p["zone_shots"][z]["fga"] for z in ZONES)
        shooting_splits_rows = []
        for z in ZONES:
            fgm = p["zone_shots"][z]["fgm"]
            fga = p["zone_shots"][z]["fga"]
            pct = round(fgm / fga * 100, 1) if fga > 0 else 0.0
            share = round(fga / tot_fga * 100, 1) if tot_fga > 0 else 0.0
            eff_pctile = compute_percentile(pct, eff_pools[z]) if fga >= 2 else 50.0

            shooting_splits_rows.append({
                "zone": z, "fgm": fgm, "fga": fga, "fg_pct": pct, "shot_share": share,
                "league_avg_fg": league_avg_fg[z], "eff_percentile": eff_pctile
            })

        sections.append({
            "type": "shot_chart",
            "title": "Shooting Splits (Distance Zones)",
            "data": {"meta_keys": ["zone"], "rows": shooting_splits_rows}
        })

        sections.append({
            "type": "table",
            "title": "Situational Splits",
            "data": {"meta_keys": ["split"], "rows": compute_player_situational_splits(p["game_logs"])}
        })

        sections.append({
            "type": "table",
            "title": "Season Game Logs",
            "data": {"meta_keys": ["date", "starter", "opponent", "result"], "rows": p["game_logs"]}
        })

        player_payload = {
            "player_id": aid,
            "name": p["name"],
            "team": p["team"],
            "team_id": p["team_id"],
            "position": p["pos"],
            "sections": sections
        }

        with open(PLAYER_DIR / f"{aid}.json", "w") as f:
            json.dump(player_payload, f, indent=2)

        flattened_player = {
            "player_id": aid,
            "player": p["name"],
            "team": p["team_abbrev"],
            "team_id": p["team_id"],
            "pos": p["pos"],
            **combined
        }
        all_player_stats_rows.append(flattened_player)

    all_player_stats_rows.sort(key=lambda x: x.get("pts_pg", 0), reverse=True)
    with open(DATA_DIR / "player_stats.json", "w") as f:
        json.dump({"meta_keys": ["player", "team", "pos"], "rows": all_player_stats_rows}, f, indent=2)

    for t_row in team_rows:
        t_id = t_row["team_id"]
        t_name = t_row["team"]

        team_roster = [
            {
                "player_id": p["player_id"],
                "player": p["name"],
                "pos": p["pos"],
                "gp": p["averages"]["gp"],
                "gs": p["averages"]["gs"],
                "min_pg": p["averages"]["min_pg"],
                "pts_pg": p["averages"]["pts_pg"],
                "reb_pg": p["averages"]["reb_pg"],
                "ast_pg": p["averages"]["ast_pg"],
                "net_rapm": p["influence_metrics"]["net_rapm"],
                "team_diff_net_rtg": p["on_off"]["team_diff_net_rtg"],
                "bpm": p["advanced"]["bpm"],
                "ts_pct": p["advanced"]["ts_pct"],
                "usg_pct": p["advanced"]["usg_pct"]
            }
            for p in active_players.values() if p["team_id"] == t_id or p["team"] == t_name
        ]
        team_roster.sort(key=lambda x: x["min_pg"], reverse=True)

        team_splits = compute_team_situational_splits(t_name, completed_games)
        team_four_factors = compute_team_advanced_metrics(t_name, team_game_stats_ledger.get(t_id, []))

        t_shots = team_season_shots.get(t_id, init_zone_dict())
        tot_t_fga = sum(t_shots[z]["fga"] for z in ZONES)
        t_shooting_rows = []
        for z in ZONES:
            fgm = t_shots[z]["fgm"]
            fga = t_shots[z]["fga"]
            pct = round(fgm / fga * 100, 1) if fga > 0 else 0.0
            share = round(fga / tot_t_fga * 100, 1) if tot_t_fga > 0 else 0.0
            eff_pctile = compute_percentile(pct, eff_pools[z]) if fga >= 2 else 50.0
            t_shooting_rows.append({
                "zone": z, "fgm": fgm, "fga": fga, "fg_pct": pct, "shot_share": share,
                "eff_percentile": eff_pctile
            })

        team_assisted_events = [e for e in all_season_assisted_plays if e["team_id"] == t_id]
        tot_team_assists = len(team_assisted_events)

        duo_events = {}
        for e in team_assisted_events:
            pair = (e["passer_id"], e["scorer_id"])
            if pair not in duo_events:
                duo_events[pair] = []
            duo_events[pair].append(e)

        assist_network_rows = []
        for (passer_id, scorer_id), ev_list in duo_events.items():
            metrics = compute_assist_connection_metrics(ev_list, league_avg_fg, active_players)
            p_name = player_names_map.get(passer_id, f"Player {passer_id}")
            s_name = player_names_map.get(scorer_id, f"Player {scorer_id}")
            t_share = round(metrics["assists"] / tot_team_assists * 100, 1) if tot_team_assists > 0 else 0.0

            assist_network_rows.append({
                "passer": p_name,
                "passer_id": passer_id,
                "finisher": s_name,
                "finisher_id": scorer_id,
                **metrics,
                "team_ast_share": t_share
            })

        assist_network_rows.sort(key=lambda x: x["assists"], reverse=True)

        t_game_logs = []
        for g in completed_games:
            if g["home_team"] == t_name:
                res = f"{'W' if g['home_score'] > g['away_score'] else 'L'} {g['home_score']}-{g['away_score']}"
                t_game_logs.append({
                    "date": g["date"], "box_score": g["box_score"], "opponent": f"vs {g['away_team']}",
                    "result": res, "pts_for": g["home_score"], "pts_against": g["away_score"], "margin": g["margin"]
                })
            elif g["away_team"] == t_name:
                res = f"{'W' if g['away_score'] > g['home_score'] else 'L'} {g['away_score']}-{g['home_score']}"
                t_game_logs.append({
                    "date": g["date"], "box_score": g["box_score"], "opponent": f"@ {g['home_team']}",
                    "result": res, "pts_for": g["away_score"], "pts_against": g["home_score"], "margin": -g["margin"]
                })

        t_upcoming = [
            {
                "date": g["date"], "time": g["time"], "venue": g["venue"],
                "opponent": f"@ {g['home_team']}" if g["away_team"] == t_name else f"vs {g['away_team']}"
            }
            for g in upcoming_games if g["home_team"] == t_name or g["away_team"] == t_name
        ]

        team_payload = {
            "team_id": t_id,
            "team_name": t_name,
            "record": f"{t_row['w']}-{t_row['l']}",
            "win_pct": t_row["win_pct"],
            "diff": t_row["diff"],
            "sections": [
                {
                    "type": "table",
                    "title": "Active Roster & Statistics",
                    "data": {"meta_keys": ["player", "pos"], "rows": team_roster}
                },
                {
                    "type": "table",
                    "title": "Pace & Four Factors",
                    "data": {"meta_keys": ["pace"], "rows": [team_four_factors]}
                },
                {
                    "type": "table",
                    "title": "Top Assist Connections & Expected Points",
                    "data": {"meta_keys": ["passer", "finisher"], "rows": assist_network_rows[:15]}
                },
                {
                    "type": "table",
                    "title": "Team Situational Splits",
                    "data": {"meta_keys": ["split"], "rows": team_splits}
                },
                {
                    "type": "shot_chart",
                    "title": "Season Shooting Splits",
                    "data": {"meta_keys": ["zone"], "rows": t_shooting_rows}
                },
                {
                    "type": "table",
                    "title": "Season Game Logs & Results",
                    "data": {"meta_keys": ["date", "box_score", "opponent", "result"], "rows": t_game_logs}
                },
                {
                    "type": "table",
                    "title": "Upcoming Schedule",
                    "data": {"meta_keys": ["date", "time", "opponent", "venue"], "rows": t_upcoming[:15]}
                }
            ]
        }

        with open(TEAM_DIR / f"{t_id}.json", "w") as f:
            json.dump(team_payload, f, indent=2)

    enriched_standings = []
    for t in team_rows:
        adv = compute_team_advanced_metrics(t["team"], team_game_stats_ledger.get(t["team_id"], []))
        enriched_standings.append({
            "team_id": t["team_id"],
            "team": t["team"],
            "gp": t["gp"],
            "w": t["w"],
            "l": t["l"],
            "win_pct": t["win_pct"],
            "pace": adv.get("pace", 0.0),
            "ortg": adv.get("ortg", 0.0),
            "drtg": adv.get("drtg", 0.0),
            "net_rtg": adv.get("net_rtg", 0.0),
            "pts_pg": t["pts_pg"],
            "opp_pts_pg": t["opp_pts_pg"],
            "diff": t["diff"]
        })

    with open(DATA_DIR / "team_stats.json", "w") as f:
        json.dump({"meta_keys": ["team"], "rows": enriched_standings}, f, indent=2)

    print("Pipeline Complete: Full DB and JSON compiled with authentic rebound rates and assisted shot splits.")


if __name__ == "__main__":
    main()