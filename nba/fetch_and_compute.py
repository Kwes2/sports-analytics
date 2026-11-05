import json
from pathlib import Path

from crawler import (
    crawl_full_season_schedule,
    crawl_game_summaries,
    crawl_team_standings,
    parse_score
)
from shots import (
    ZONES,
    init_zone_dict,
    process_game_shots
)
from stats import (
    process_boxscore_players,
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

DATA_DIR = Path(__file__).parent / "data"
BOX_DIR = DATA_DIR / "boxscores"
PLAYER_DIR = DATA_DIR / "players"
TEAM_DIR = DATA_DIR / "teams"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BOX_DIR.mkdir(parents=True, exist_ok=True)
PLAYER_DIR.mkdir(parents=True, exist_ok=True)
TEAM_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # 1. Crawl Schedule
    completed_games, upcoming_games, completed_ids = crawl_full_season_schedule()

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

    # 3. Crawl Game Summaries
    summaries = crawl_game_summaries(completed_ids)

    players = {}
    team_season_shots = {}
    team_game_stats_ledger = {}
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

        team_shots, game_player_shots = process_game_shots(plays, home_id, away_id)
        game_team_rows, player_events = process_boxscore_players(
            game_players, home_abbrev, away_abbrev, home_score, away_score, date_str
        )

        for tid in [home_id, away_id]:
            if tid not in team_season_shots:
                team_season_shots[tid] = init_zone_dict()
            for z in ZONES:
                team_season_shots[tid][z]["fga"] += team_shots[tid][z]["fga"]
                team_season_shots[tid][z]["fgm"] += team_shots[tid][z]["fgm"]

        # Track full team box stats for Pace & Four Factors
        def sum_team_stat(t_id, key):
            rows = game_team_rows.get(t_id, {}).get("rows", [])
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
                    "gp": 0, "tot_min": 0.0, "tot_pts": 0, "tot_reb": 0, "tot_ast": 0, "tot_stl": 0, "tot_blk": 0,
                    "tot_to": 0, "tot_fgm": 0, "tot_fga": 0, "tot_fg3m": 0, "tot_fg3a": 0, "tot_ftm": 0, "tot_fta": 0,
                    "tot_oreb": 0, "tot_dreb": 0, "tot_pf": 0, "game_logs": [], "zone_shots": init_zone_dict()
                }
            for z in ZONES:
                players[aid]["zone_shots"][z]["fga"] += s_zones[z]["fga"]
                players[aid]["zone_shots"][z]["fgm"] += s_zones[z]["fgm"]

        for aid, ev in player_events.items():
            if aid not in players:
                players[aid] = {
                    "player_id": aid, "player": ev["player"], "team": ev["team"], "team_id": ev["team_id"],
                    "team_abbrev": ev["team_abbrev"], "pos": ev["pos"], "gp": 0, "tot_min": 0.0, "tot_pts": 0,
                    "tot_reb": 0, "tot_ast": 0, "tot_stl": 0, "tot_blk": 0, "tot_to": 0, "tot_fgm": 0, "tot_fga": 0,
                    "tot_fg3m": 0, "tot_fg3a": 0, "tot_ftm": 0, "tot_fta": 0, "tot_oreb": 0, "tot_dreb": 0, "tot_pf": 0,
                    "game_logs": [], "zone_shots": init_zone_dict()
                }

            p = players[aid]
            p["player"] = ev["player"]
            p["team"] = ev["team"]
            p["team_id"] = ev["team_id"]
            p["team_abbrev"] = ev["team_abbrev"]
            p["pos"] = ev["pos"]
            p["gp"] += 1
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
            p["game_logs"].append(ev["log"])

        # Calculate Four Factors for this specific game
        game_four_factors = [
            {"team": home_name, **compute_team_advanced_metrics(home_name, [team_game_stats_ledger[home_id][-1]])},
            {"team": away_name, **compute_team_advanced_metrics(away_name, [team_game_stats_ledger[away_id][-1]])}
        ]

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
                "shooting_splits": {"meta_keys": ["zone"], "rows": split_rows},
                "meta_keys": ["player", "pos"],
                "rows": t_info["rows"]
            })

        with open(BOX_DIR / f"{event_id}.json", "w") as f:
            json.dump({
                "game_id": event_id, "date": date_str, "venue": venue_str,
                "home_team": home_name, "home_score": home_score, "home_team_id": home_id,
                "away_team": away_name, "away_score": away_score, "away_team_id": away_id,
                "four_factors": {"meta_keys": ["team"], "rows": game_four_factors},
                "teams": box_teams
            }, f, indent=2)
        saved_boxes += 1

    # 4. Compute Season Averages & Advanced Metrics for Active Players
    active_players = {}
    for aid, p in players.items():
        if p["gp"] == 0:
            continue
        gp = p["gp"]
        min_pg = round(p["tot_min"] / gp, 1)
        pts_pg = round(p["tot_pts"] / gp, 1)
        reb_pg = round(p["tot_reb"] / gp, 1)
        ast_pg = round(p["tot_ast"] / gp, 1)
        stl_pg = round(p["tot_stl"] / gp, 1)
        blk_pg = round(p["tot_blk"] / gp, 1)
        to_pg = round(p["tot_to"] / gp, 1)
        fg_pct = round((p["tot_fgm"] / p["tot_fga"]) * 100, 1) if p["tot_fga"] > 0 else 0.0

        custom_impact = round(
            pts_pg + (1.2 * reb_pg) + (1.5 * ast_pg) + (2.0 * stl_pg) + (2.0 * blk_pg) - (1.0 * to_pg), 1
        )

        p["game_logs"].sort(key=lambda x: x["date"], reverse=True)
        adv = compute_player_advanced_metrics(p)

        active_players[aid] = {
            "player_id": aid, "name": p["player"], "team": p["team"], "team_id": p["team_id"],
            "team_abbrev": p["team_abbrev"], "pos": p["pos"],
            "averages": {
                "gp": gp, "min": min_pg, "pts": pts_pg, "reb": reb_pg, "ast": ast_pg,
                "stl": stl_pg, "blk": blk_pg, "to": to_pg, "fg_pct": fg_pct,
                "custom_impact": custom_impact
            },
            "advanced": adv,
            "zone_shots": p["zone_shots"],
            "game_logs": p["game_logs"]
        }

    # 5. Distribution Pools (Including Advanced Stats)
    stat_keys = ["min", "pts", "reb", "ast", "stl", "blk", "to", "fg_pct", "custom_impact", "ts_pct", "efg_pct", "usg_pct", "gmsc_avg"]
    league_pools, pos_pools = build_stat_pools(active_players, stat_keys)
    vol_pools, eff_pools = build_shot_pools(active_players, ZONES)

    league_zone_totals = init_zone_dict()
    for p in active_players.values():
        for z in ZONES:
            league_zone_totals[z]["fgm"] += p["zone_shots"][z]["fgm"]
            league_zone_totals[z]["fga"] += p["zone_shots"][z]["fga"]

    league_avg_fg = {
        z: round(league_zone_totals[z]["fgm"] / league_zone_totals[z]["fga"] * 100, 1) if league_zone_totals[z]["fga"] > 0 else 0.0
        for z in ZONES
    }

    # 6. Assemble Section-Based Player Profile Payloads
    leader_rows = []
    for aid, p in active_players.items():
        pos = p["pos"]
        avg = p["averages"]
        adv = p["advanced"]

        combined = {**avg, **adv}
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
            vol_pctile = compute_percentile(fga, vol_pools[z])

            shooting_splits_rows.append({
                "zone": z, "fgm": fgm, "fga": fga, "fg_pct": pct, "shot_share": share,
                "league_avg_fg": league_avg_fg[z], "eff_percentile": eff_pctile, "vol_percentile": vol_pctile
            })

        situational_rows = compute_player_situational_splits(p["game_logs"])

        player_payload = {
            "player_id": aid,
            "name": p["name"],
            "team": p["team"],
            "team_id": p["team_id"],
            "position": p["pos"],
            "sections": [
                {
                    "type": "table",
                    "title": "Season Averages",
                    "data": {"meta_keys": ["gp"], "rows": [avg]}
                },
                {
                    "type": "table",
                    "title": "Advanced Statistics",
                    "data": {"meta_keys": ["gp"], "rows": [adv]}
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

        leader_rows.append({
            "player_id": aid, "player": p["name"], "team": p["team_abbrev"], "team_id": p["team_id"], "pos": p["pos"],
            "gp": avg["gp"], "min_pg": avg["min"], "pts_pg": avg["pts"], "reb_pg": avg["reb"],
            "ast_pg": avg["ast"], "stl_pg": avg["stl"], "blk_pg": avg["blk"], "ts_pct": adv["ts_pct"],
            "usg_pct": adv["usg_pct"], "gmsc_avg": adv["gmsc_avg"], "custom_impact": avg["custom_impact"]
        })

    leader_rows.sort(key=lambda x: x["pts_pg"], reverse=True)
    with open(DATA_DIR / "player_stats.json", "w") as f:
        json.dump({"meta_keys": ["player", "team", "pos"], "rows": leader_rows}, f, indent=2)

    # 7. Assemble Team Payloads (With Pace & Four Factors)
    for t_row in team_rows:
        t_id = t_row["team_id"]
        t_name = t_row["team"]

        team_roster = [
            {
                "player_id": p["player_id"],
                "player": p["name"],
                "pos": p["pos"],
                "gp": p["averages"]["gp"],
                "min_pg": p["averages"]["min"],
                "pts_pg": p["averages"]["pts"],
                "reb_pg": p["averages"]["reb"],
                "ast_pg": p["averages"]["ast"],
                "ts_pct": p["advanced"]["ts_pct"],
                "usg_pct": p["advanced"]["usg_pct"],
                "gmsc_avg": p["advanced"]["gmsc_avg"],
                "custom_rating": p["averages"]["custom_impact"]
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

    # 8. Enrich Main Standings Table with Team Advanced Metrics
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

    print("Pipeline Complete: Advanced metrics populated across all players, teams, and box scores.")


if __name__ == "__main__":
    main()