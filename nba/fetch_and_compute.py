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
    compute_shot_quality_metrics
)
from stats import (
    process_boxscore_players,
    extract_detailed_assists_from_plays,
    compute_assist_connection_metrics,
    compute_player_advanced_metrics,
    compute_team_standings,
    compute_team_advanced_metrics,
    compute_player_situational_splits,
    compute_team_situational_splits
)
from percentiles import (
    compute_percentile,
    build_stat_pools,
    build_shot_pools
)
from stints import StintTracker
from baselines import BaselineEngine
from influence import InfluenceEngine

DATA_DIR = Path(__file__).parent / "data"
BOX_DIR = DATA_DIR / "boxscores"
PLAYER_DIR = DATA_DIR / "players"
TEAM_DIR = DATA_DIR / "teams"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BOX_DIR.mkdir(parents=True, exist_ok=True)
PLAYER_DIR.mkdir(parents=True, exist_ok=True)
TEAM_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # 0. Canonical Positions Mapping
    position_map = crawl_team_rosters()

    # 1. Crawl Schedule (2026 completed season + 2027 active season)
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

    # 2. Crawl Standings
    standings_raw = crawl_team_standings()
    team_rows = compute_team_standings(standings_raw)
    team_scoring_map = {t["team_id"]: t["pts_pg"] for t in team_rows}
    team_scoring_by_name = {t["team"]: t["pts_pg"] for t in team_rows}

    # 3. Crawl Game Summaries
    summaries = crawl_game_summaries(completed_ids)

    players = {}
    player_names_map = {}
    team_season_shots = {}
    team_game_stats_ledger = {}
    all_season_assisted_plays = []
    league_granular_shots = init_granular_dict()

    # Stint-level interaction ledgers
    merged_pair_ledger = {}
    player_game_stints_history = {}  # {aid: [game_stint_summary_1, game_stint_summary_2, ...]}
    saved_boxes = 0

    for event_id, data in summaries.items():
        boxscore_data = data.get("boxscore", {})
        game_players = boxscore_data.get("players", [])
        plays = data.get("plays", [])
        header_info = data.get("header", {})
        comp = header_info.get("competitions", [{}])[0]

        venue_str = comp.get("venue", {}).get("fullName", "Unknown Venue")
        date_str = comp.get("date", "")[:10]

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

        team_shots, game_player_shots, game_player_granular = process_game_shots(plays, home_id, away_id)
        game_team_rows, player_events = process_boxscore_players(
            game_players, home_abbrev, away_abbrev, home_score, away_score, date_str, position_map
        )

        game_assists = extract_detailed_assists_from_plays(plays)
        all_season_assisted_plays.extend(game_assists)

        # Stint tracking with accurate home/away ID matching
        home_starters = [r["player_id"] for r in game_team_rows.get(home_id, {}).get("starters", [])]
        away_starters = [r["player_id"] for r in game_team_rows.get(away_id, {}).get("starters", [])]
        if home_starters and away_starters:
            stint_tracker = StintTracker(home_starters, away_starters, home_id, away_id)
            game_player_stints = {}

            for play in plays:
                stint_tracker.process_play(play, merged_pair_ledger, game_player_stints)
            stint_tracker.commit_stint(merged_pair_ledger, game_player_stints)

            # Record this game's stint total into player's history
            for p_id, g_stint in game_player_stints.items():
                if p_id not in player_game_stints_history:
                    player_game_stints_history[p_id] = []
                player_game_stints_history[p_id].append(g_stint)

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
                "meta_keys": ["player", "pos"],
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
        saved_boxes += 1

    # 4. Compute Granular Shot Baselines
    league_granular_efg = {}
    for gz in GRANULAR_ZONES:
        fga = league_granular_shots[gz]["fga"]
        fgm = league_granular_shots[gz]["fgm"]
        fg3m = league_granular_shots[gz]["fg3m"]
        if fga > 0:
            league_granular_efg[gz] = round((fgm + 0.5 * fg3m) / fga * 100, 1)
        else:
            league_granular_efg[gz] = 50.0

    # 5. Compute Season Averages & Advanced Metrics for Active Players
    active_players = {}
    for aid, p in players.items():
        if p["gp"] == 0:
            continue
        gp = p["gp"]
        gs = p["gs"]
        min_pg = round(p["tot_min"] / gp, 1)
        pts_pg = round(p["tot_pts"] / gp, 1)
        reb_pg = round(p["tot_reb"] / gp, 1)
        ast_pg = round(p["tot_ast"] / gp, 1)
        stl_pg = round(p["tot_stl"] / gp, 1)
        blk_pg = round(p["tot_blk"] / gp, 1)
        to_pg = round(p["tot_to"] / gp, 1)
        pf_pg = round(p["tot_pf"] / gp, 1)
        plus_minus_pg = round(p["tot_plus_minus"] / gp, 1)

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
        sq_metrics = compute_shot_quality_metrics(
            p["granular_shots"], league_granular_efg, p["tot_fta"], p["tot_fga"]
        )
        adv = {**adv, **sq_metrics}

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
            "advanced": adv,
            "zone_shots": p["zone_shots"],
            "game_logs": p["game_logs"]
        }

    # 6. Execute Pure On-Court Baselines & Influence Engines
    print("Computing 30-game individual on-court baselines...")
    baseline_engine = BaselineEngine(active_players, player_game_stints_history, team_game_stats_ledger)

    print("Evaluating individual teammate elevation & opponent suppression...")
    influence_engine = InfluenceEngine(active_players, baseline_engine, merged_pair_ledger)
    player_influence_map = influence_engine.attr

    # 7. League Benchmark Baselines for Simple Distance Zones
    league_zone_totals = init_zone_dict()
    for p in active_players.values():
        for z in ZONES:
            league_zone_totals[z]["fgm"] += p["zone_shots"][z]["fgm"]
            league_zone_totals[z]["fga"] += p["zone_shots"][z]["fga"]

    league_avg_fg = {
        z: round(league_zone_totals[z]["fgm"] / league_zone_totals[z]["fga"] * 100, 1) if league_zone_totals[z]["fga"] > 0 else 0.0
        for z in ZONES
    }

    # 8. Group Assisted Events for Graph Networks
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

    # 9. Compute Passing Profiles, PRF, and Dynamic Feature Dictionaries
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

        # Attach Influence Metrics
        p["influence_metrics"] = player_influence_map.get(aid, {
            "teammate_off_impact": 0.0, "teammate_def_impact": 0.0, "teammate_overall_impact": 0.0,
            "opponent_off_impact": 0.0, "opponent_def_impact": 0.0, "opponent_overall_impact": 0.0,
            "overall_impact": 0.0
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

    # 10. Distribution Pools
    stat_keys = [
        "min_pg", "pts_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg", "to_pg", "fg_pct",
        "ts_pct", "efg_pct", "xefg_pct", "smoe", "mei", "usg_pct", "gmsc_avg",
        "xpts_per_ast", "paoe", "pts_created_pg", "prf_pg", "pct_team_prf",
        "overall_impact", "teammate_overall_impact", "opponent_overall_impact"
    ]

    league_pools = {k: [] for k in stat_keys}
    pos_pools = {}
    for p in active_players.values():
        pos = p["pos"]
        if pos not in pos_pools:
            pos_pools[pos] = {k: [] for k in stat_keys}
        combined = {**p["averages"], **p["advanced"], **p["passing_profile"], **p["prf_metrics"], **p["influence_metrics"]}
        for k in stat_keys:
            val = combined.get(k, 0.0)
            league_pools[k].append(val)
            pos_pools[pos][k].append(val)

    vol_pools, eff_pools = build_shot_pools(active_players, ZONES)

    # 11. Assemble Section-Based Player Profile Payloads & Complete Player Stats Table (Auto-Merged!)
    all_player_stats_rows = []
    for aid, p in active_players.items():
        pos = p["pos"]
        avg = p["averages"]
        adv = p["advanced"]
        pass_prof = p["passing_profile"]
        prf = p["prf_metrics"]
        inf = p["influence_metrics"]

        combined = {**avg, **adv, **pass_prof, **prf, **inf}
        league_percentiles = {k: compute_percentile(combined.get(k, 0), league_pools[k]) for k in stat_keys}
        pos_percentiles = {k: compute_percentile(combined.get(k, 0), pos_pools[pos][k]) for k in stat_keys}

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

        situational_rows = compute_player_situational_splits(p["game_logs"])

        passes_from_rows = []
        finisher_dict = passer_finisher_map.get(aid, {})
        tot_player_assists = sum(len(ev_list) for ev_list in finisher_dict.values())
        for finisher_id, ev_list in finisher_dict.items():
            metrics = compute_assist_connection_metrics(ev_list, league_avg_fg, active_players)
            f_name = player_names_map.get(finisher_id, f"Player {finisher_id}")
            ast_share = round(metrics["assists"] / tot_player_assists * 100, 1) if tot_player_assists > 0 else 0.0
            passes_from_rows.append({
                "finisher": f_name, "finisher_id": finisher_id, **metrics, "ast_share": ast_share
            })
        passes_from_rows.sort(key=lambda x: x["assists"], reverse=True)

        passes_to_rows = []
        passer_dict = finisher_passer_map.get(aid, {})
        tot_player_assisted_baskets = sum(len(ev_list) for ev_list in passer_dict.values())
        for passer_id, ev_list in passer_dict.items():
            metrics = compute_assist_connection_metrics(ev_list, league_avg_fg, active_players)
            p_name = player_names_map.get(passer_id, f"Player {passer_id}")
            baskets_share = round(metrics["assists"] / tot_player_assisted_baskets * 100, 1) if tot_player_assisted_baskets > 0 else 0.0
            passes_to_rows.append({
                "passer": p_name, "passer_id": passer_id, **metrics, "baskets_share": baskets_share
            })
        passes_to_rows.sort(key=lambda x: x["assists"], reverse=True)

        player_payload = {
            "player_id": aid,
            "name": p["name"],
            "team": p["team"],
            "team_id": p["team_id"],
            "position": p["pos"],
            "sections": [
                {
                    "type": "table",
                    "title": "Season Averages & Output",
                    "data": {"meta_keys": ["gp", "gs"], "rows": [{**avg, **prf}]}
                },
                {
                    "type": "table",
                    "title": "Advanced Statistics & Influence",
                    "data": {"meta_keys": ["gp"], "rows": [{**adv, **inf}]}
                },
                {
                    "type": "table",
                    "title": "Playmaking & Passing Quality Profile",
                    "data": {"meta_keys": ["ast_recorded"], "rows": [pass_prof]}
                },
                {
                    "type": "table",
                    "title": "Percentile Ranks (0–100)",
                    "data": {
                        "meta_keys": ["scope"],
                        "rows": [
                            {"scope": "League Percentile", **league_percentiles},
                            {"scope": f"Position Percentile ({pos})", **pos_percentiles}
                        ]
                    }
                },
                {
                    "type": "table",
                    "title": "Situational Splits",
                    "data": {"meta_keys": ["split"], "rows": situational_rows}
                },
                {
                    "type": "table",
                    "title": "Assists Delivered (Passes FROM this Player)",
                    "data": {"meta_keys": ["finisher"], "rows": passes_from_rows}
                },
                {
                    "type": "table",
                    "title": "Assists Received (Passes TO this Player)",
                    "data": {"meta_keys": ["passer"], "rows": passes_to_rows}
                },
                {
                    "type": "shot_chart",
                    "title": "Shooting Splits (Distance Zones)",
                    "data": {"meta_keys": ["zone"], "rows": shooting_splits_rows}
                },
                {
                    "type": "table",
                    "title": "Season Game Logs",
                    "data": {"meta_keys": ["date", "opponent", "result"], "rows": p["game_logs"]}
                }
            ]
        }

        with open(PLAYER_DIR / f"{aid}.json", "w") as f:
            json.dump(player_payload, f, indent=2)

        flattened_player = {
            "player_id": aid,
            "player": p["name"],
            "team": p["team_abbrev"],
            "team_id": p["team_id"],
            "pos": p["pos"],
            **p["averages"],
            **p["prf_metrics"],
            **p["advanced"],
            **p["passing_profile"],
            **p["zone_summary"],
            **p["influence_metrics"]
        }
        all_player_stats_rows.append(flattened_player)

    all_player_stats_rows.sort(key=lambda x: x["pts_pg"], reverse=True)
    with open(DATA_DIR / "player_stats.json", "w") as f:
        json.dump({"meta_keys": ["player", "team", "pos"], "rows": all_player_stats_rows}, f, indent=2)

    # 12. Assemble Team Payloads
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
                "overall_impact": p["influence_metrics"]["overall_impact"],
                "ts_pct": p["advanced"]["ts_pct"],
                "smoe": p["advanced"]["smoe"],
                "mei": p["advanced"]["mei"],
                "usg_pct": p["advanced"]["usg_pct"],
                "gmsc_avg": p["advanced"]["gmsc_avg"]
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

    # 13. Main Standings Table
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

    print("Pipeline Complete: Individual on-court baselines & influence metrics computed.")


if __name__ == "__main__":
    main()