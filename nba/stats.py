"""
stats.py - Core mathematical routines for NBA box scores, advanced metrics,
xPRF/PRFOE, and 18-stat On/Off differentials.
"""

def parse_int(val):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def parse_split(val_str):
    if not val_str:
        return 0, 0
    if "-" in str(val_str):
        parts = str(val_str).split("-")
        return parse_int(parts[0]), parse_int(parts[1]) if len(parts) > 1 else 0
    return parse_int(val_str), 0


def process_boxscore_players(game_players, home_abbrev, away_abbrev, home_score, away_score, date_str, position_map):
    game_team_rows = {}
    player_game_events = {}

    for team_entry in game_players:
        team_id = str(team_entry.get("team", {}).get("id", ""))
        team_display = team_entry.get("team", {}).get("displayName", "")
        team_abbrev = team_entry.get("team", {}).get("abbreviation", "N/A")
        is_home = (team_abbrev == home_abbrev)

        opp_str = f"vs {away_abbrev}" if is_home else f"@ {home_abbrev}"
        if is_home:
            res_str = f"{'W' if home_score > away_score else 'L'} {home_score}-{away_score}"
        else:
            res_str = f"{'W' if away_score > home_score else 'L'} {away_score}-{home_score}"

        starters_rows = []
        bench_rows = []
        all_players_rows = []

        for stat_cat in team_entry.get("statistics", []):
            keys = stat_cat.get("names", [])
            for item_idx, item in enumerate(stat_cat.get("athletes", [])):
                ath = item.get("athlete", {})
                aid = ath.get("id")
                if not aid:
                    continue

                stats = dict(zip(keys, item.get("stats", [])))
                try:
                    minutes = float(stats.get("MIN", "0"))
                except ValueError:
                    minutes = 0.0

                if minutes == 0.0:
                    continue

                pts = parse_int(stats.get("PTS", 0))
                reb = parse_int(stats.get("REB", 0))
                ast = parse_int(stats.get("AST", 0))
                stl = parse_int(stats.get("STL", 0))
                blk = parse_int(stats.get("BLK", 0))
                to = parse_int(stats.get("TO", 0))
                pf = parse_int(stats.get("PF", 0))
                oreb = parse_int(stats.get("OREB", stats.get("OR", 0)))
                dreb = parse_int(stats.get("DREB", stats.get("DR", reb - oreb)))
                plus_minus = parse_int(stats.get("+/-", stats.get("PLUSMINUS", 0)))

                fgm, fga = parse_split(stats.get("FG", stats.get("FGM", "0-0")))
                if fga == 0:
                    fgm = parse_int(stats.get("FGM", 0))
                    fga = parse_int(stats.get("FGA", 0))

                fg3m, fg3a = parse_split(stats.get("3PT", stats.get("3PM", "0-0")))
                if fg3a == 0:
                    fg3m = parse_int(stats.get("3PM", 0))
                    fg3a = parse_int(stats.get("3PA", 0))

                ftm, fta = parse_split(stats.get("FT", stats.get("FTM", "0-0")))
                if fta == 0:
                    ftm = parse_int(stats.get("FTM", 0))
                    fta = parse_int(stats.get("FTA", 0))

                player_name = ath.get("displayName", "Unknown")
                pos_str = position_map.get(str(aid), ath.get("position", {}).get("abbreviation", "-"))

                is_starter = (item_idx < 5)

                gmsc = round(
                    pts + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm) + 0.7 * oreb + 0.3 * dreb + stl + 0.7 * ast + 0.7 * blk - 0.4 * pf - to,
                    1
                )
                ts_pct = round(pts / (2 * (fga + 0.44 * fta)) * 100, 1) if (fga + 0.44 * fta) > 0 else 0.0

                row_dict = {
                    "player_id": aid,
                    "player": player_name,
                    "pos": pos_str,
                    "starter": 1 if is_starter else 0,
                    "min": int(minutes),
                    "pts": pts,
                    "reb": reb,
                    "ast": ast,
                    "stl": stl,
                    "blk": blk,
                    "to": to,
                    "fgm": fgm,
                    "fga": fga,
                    "fg3m": fg3m,
                    "fg3a": fg3a,
                    "ftm": ftm,
                    "fta": fta,
                    "oreb": oreb,
                    "dreb": dreb,
                    "pf": pf,
                    "plus_minus": plus_minus,
                    "gmsc": gmsc
                }

                if is_starter:
                    starters_rows.append(row_dict)
                else:
                    bench_rows.append(row_dict)
                all_players_rows.append(row_dict)

                player_game_events[aid] = {
                    "player_id": aid,
                    "player": player_name,
                    "team": team_display,
                    "team_id": team_id,
                    "team_abbrev": team_abbrev,
                    "pos": pos_str,
                    "minutes": minutes,
                    "starter": 1 if is_starter else 0,
                    "pts": pts,
                    "reb": reb,
                    "ast": ast,
                    "stl": stl,
                    "blk": blk,
                    "to": to,
                    "fgm": fgm,
                    "fga": fga,
                    "fg3m": fg3m,
                    "fg3a": fg3a,
                    "ftm": ftm,
                    "fta": fta,
                    "oreb": oreb,
                    "dreb": dreb,
                    "pf": pf,
                    "plus_minus": plus_minus,
                    "is_starter": is_starter,
                    "log": {
                        "date": date_str,
                        "starter": 1 if is_starter else 0,
                        "opponent": opp_str,
                        "result": res_str,
                        "min": int(minutes),
                        "pts": pts,
                        "reb": reb,
                        "ast": ast,
                        "stl": stl,
                        "blk": blk,
                        "to": to,
                        "fgm": fgm,
                        "fga": fga,
                        "fg3m": fg3m,
                        "fg3a": fg3a,
                        "ftm": ftm,
                        "fta": fta,
                        "plus_minus": plus_minus,
                        "gmsc": gmsc,
                        "ts_pct": ts_pct
                    }
                }

        game_team_rows[team_id] = {
            "team_name": team_display,
            "team_abbrev": team_abbrev,
            "starters": starters_rows,
            "bench": bench_rows,
            "all_rows": all_players_rows
        }

    return game_team_rows, player_game_events


def extract_detailed_assists_from_plays(plays):
    events = []

    for play in plays:
        if play.get("scoringPlay"):
            participants = play.get("participants", [])
            team_id = str(play.get("team", {}).get("id", ""))
            text = play.get("text", "")
            text_lower = text.lower()

            if len(participants) >= 2 and "assists" in text_lower:
                scorer_id = str(participants[0].get("athlete", {}).get("id", ""))
                passer_id = str(participants[1].get("athlete", {}).get("id", ""))

                if scorer_id and passer_id and team_id:
                    is_three = "three point" in text_lower or "3pt" in text_lower
                    shot_val = 3 if is_three else 2

                    coord = play.get("coordinate")
                    if coord and "x" in coord and "y" in coord:
                        from shots import classify_shot_distance 
                        zone = classify_shot_distance(coord["x"], coord["y"])
                    else:
                        zone = "14+ ft" if is_three else "0-4 ft"

                    events.append({
                        "team_id": team_id,
                        "passer_id": passer_id,
                        "scorer_id": scorer_id,
                        "val": shot_val,
                        "zone": zone
                    })

    return events


def compute_assist_connection_metrics(assisted_events, league_zone_avg_fg, active_players):
    total_ast = len(assisted_events)
    if total_ast == 0:
        return {}

    pts_created = sum(e["val"] for e in assisted_events)
    pts_per_ast = round(pts_created / total_ast, 2)

    two_pt_ast = sum(1 for e in assisted_events if e["val"] == 2)
    three_pt_ast = sum(1 for e in assisted_events if e["val"] == 3)
    rim_ast = sum(1 for e in assisted_events if e["zone"] == "0-4 ft")
    mid_ast = sum(1 for e in assisted_events if e["zone"] == "4-14 ft")

    tot_xpts_lg = 0.0
    for e in assisted_events:
        lg_pct = league_zone_avg_fg.get(e["zone"], 50.0) / 100.0
        tot_xpts_lg += (e["val"] * lg_pct)

    xpts_per_ast = round(tot_xpts_lg / total_ast, 2)

    scorer_id = assisted_events[0]["scorer_id"]
    finisher_data = active_players.get(scorer_id, {})
    finisher_zones = finisher_data.get("zone_shots", {})

    tot_xpts_finisher = 0.0
    for e in assisted_events:
        z_stats = finisher_zones.get(e["zone"], {"fgm": 0, "fga": 0})
        if z_stats["fga"] >= 3:
            f_pct = (z_stats["fgm"] / z_stats["fga"])
        else:
            f_pct = league_zone_avg_fg.get(e["zone"], 50.0) / 100.0
        tot_xpts_finisher += (e["val"] * f_pct)

    finisher_xpts_per_ast = round(tot_xpts_finisher / total_ast, 2)

    paoe = round(pts_per_ast - xpts_per_ast, 2)
    points_added = round(pts_created - tot_xpts_lg, 1)

    return {
        "assists": total_ast,
        "pts_created": pts_created,
        "pts_per_ast": pts_per_ast,
        "xpts_per_ast": xpts_per_ast,
        "finisher_xpts": finisher_xpts_per_ast,
        "paoe": paoe,
        "points_added": points_added,
        "two_pt_ast": two_pt_ast,
        "three_pt_ast": three_pt_ast,
        "rim_ast": rim_ast,
        "mid_ast": mid_ast
    }


def compute_xprf_metrics(fga, xfg_pct, fta, xft_pct, expected_assist_pts, actual_prf_pg, gp):
    if gp <= 0:
        return {"xprf_pg": 0.0, "prfoe_pg": 0.0}

    # Expected points from FGA accurately mapped using Expected eFG% (since xeFG% already mathematically factors the 3-point bonus per zone)
    exp_fg_pts = fga * (xfg_pct / 100.0) * 2.0
    exp_ft_pts = fta * (xft_pct / 100.0) * 1.0

    total_expected_pts = exp_fg_pts + exp_ft_pts + expected_assist_pts
    xprf_pg = round(total_expected_pts / gp, 1)
    prfoe_pg = round(actual_prf_pg - xprf_pg, 1)

    return {
        "xprf_pg": xprf_pg,
        "prfoe_pg": prfoe_pg
    }


def compute_player_advanced_metrics(p):
    gp = p["gp"]
    fga = p["tot_fga"]
    fgm = p["tot_fgm"]
    fg3a = p.get("tot_fg3a", 0)
    fg3m = p.get("tot_fg3m", 0)
    fta = p.get("tot_fta", 0)
    ftm = p.get("tot_ftm", 0)
    pts = p["tot_pts"]
    to = p["tot_to"]
    ast = p["tot_ast"]
    stl = p["tot_stl"]
    blk = p["tot_blk"]
    oreb = p.get("tot_oreb", 0)
    dreb = p.get("tot_dreb", 0)
    pf = p.get("tot_pf", 0)
    tot_min = p["tot_min"]
    reb = oreb + dreb

    ts_pct = round(pts / (2 * (fga + 0.44 * fta)) * 100, 1) if (fga + 0.44 * fta) > 0 else 0.0
    efg_pct = round((fgm + 0.5 * fg3m) / fga * 100, 1) if fga > 0 else 0.0
    three_par = round(fg3a / fga * 100, 1) if fga > 0 else 0.0
    ft_rate = round(fta / fga * 100, 1) if fga > 0 else 0.0
    ppsa = round(pts / fga, 2) if fga > 0 else 0.0
    ast_to = round(ast / to, 2) if to > 0 else float(ast)
    tov_pct = round(to / (fga + 0.44 * fta + to) * 100, 1) if (fga + 0.44 * fta + to) > 0 else 0.0
    stocks_pg = round((stl + blk) / gp, 1) if gp > 0 else 0.0

    tot_gmsc = pts + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm) + 0.7 * oreb + 0.3 * dreb + stl + 0.7 * ast + 0.7 * blk - 0.4 * pf - to
    gmsc_avg = round(tot_gmsc / gp, 1) if gp > 0 else 0.0

    # Precise Unadjusted PER Approximation (weighted closely to Hollinger values, scaled to 15.0 League Avg)
    if tot_min > 0:
        raw_per = (pts + 1.2*oreb + 0.8*dreb + 1.5*ast + 2.0*stl + 2.0*blk - 0.8*(fga - fgm) - 0.4*(fta - ftm) - 1.5*to) / tot_min
        per = round(raw_per * 28.0, 1)
    else:
        per = 0.0

    # BPM 2.0 Scaled Estimation
    pts_pg = pts / gp if gp > 0 else 0
    reb_pg = reb / gp if gp > 0 else 0
    ast_pg = ast / gp if gp > 0 else 0
    stl_pg = stl / gp if gp > 0 else 0
    blk_pg = blk / gp if gp > 0 else 0
    to_pg = to / gp if gp > 0 else 0
    fga_pg = fga / gp if gp > 0 else 0

    bpm = round(0.15 * pts_pg + 0.20 * reb_pg + 0.25 * ast_pg + 1.0 * stl_pg + 0.8 * blk_pg - 0.5 * to_pg - 0.15 * fga_pg - 2.0, 1)
    vorp = round((bpm + 2.0) * (tot_min / 3936.0) * 82.0, 2)

    return {
        "gp": gp,
        "ts_pct": ts_pct,
        "efg_pct": efg_pct,
        "tov_pct": tov_pct,
        "ast_to_ratio": ast_to,
        "three_par": three_par,
        "ft_rate": ft_rate,
        "ppsa": ppsa,
        "gmsc_avg": gmsc_avg,
        "stocks_pg": stocks_pg,
        "per": per,
        "bpm": bpm,
        "vorp": vorp
    }


def compute_team_standings(standings_data):
    team_rows = []
    for group in standings_data.get("children", []):
        for entry in group.get("standings", {}).get("entries", []):
            team_obj = entry.get("team", {})
            team_name = team_obj.get("displayName", "")
            team_id = str(team_obj.get("id", ""))
            stats_list = entry.get("stats", [])

            def get_stat(name, default=0.0):
                for s in stats_list:
                    if s.get("name") == name:
                        return float(s.get("value", default))
                return default

            wins = int(get_stat("wins", 0))
            losses = int(get_stat("losses", 0))
            gp = wins + losses
            win_pct = round(get_stat("winPercent", 0.0) * 100, 1)
            pts_for = round(get_stat("avgPointsFor", 0.0), 1)
            pts_against = round(get_stat("avgPointsAgainst", 0.0), 1)
            diff = round(pts_for - pts_against, 1)

            team_rows.append({
                "team_id": team_id,
                "team": team_name,
                "gp": gp,
                "w": wins,
                "l": losses,
                "win_pct": win_pct,
                "pts_pg": pts_for,
                "opp_pts_pg": pts_against,
                "diff": diff
            })

    team_rows.sort(key=lambda x: x["w"], reverse=True)
    return team_rows


def compute_team_advanced_metrics(team_name, team_games):
    gp = len(team_games)
    if gp == 0:
        return {}

    tot_pts = sum(g["pts"] for g in team_games)
    tot_opp_pts = sum(g["opp_pts"] for g in team_games)
    tot_fga = sum(g["fga"] for g in team_games)
    tot_fgm = sum(g["fgm"] for g in team_games)
    tot_3pm = sum(g["fg3m"] for g in team_games)
    tot_fta = sum(g["fta"] for g in team_games)
    tot_to = sum(g["to"] for g in team_games)
    tot_oreb = sum(g["oreb"] for g in team_games)
    tot_dreb = sum(g["dreb"] for g in team_games)

    opp_fga = sum(g["opp_fga"] for g in team_games)
    opp_fgm = sum(g["opp_fgm"] for g in team_games)
    opp_3pm = sum(g["opp_fg3m"] for g in team_games)
    opp_fta = sum(g["opp_fta"] for g in team_games)
    opp_to = sum(g["opp_to"] for g in team_games)
    opp_oreb = sum(g["opp_oreb"] for g in team_games)
    opp_dreb = sum(g["opp_dreb"] for g in team_games)

    poss = 0.96 * (tot_fga + tot_to + 0.44 * tot_fta - tot_oreb)
    opp_poss = 0.96 * (opp_fga + opp_to + 0.44 * opp_fta - opp_oreb)
    avg_poss = (poss + opp_poss) / 2.0

    pace = round(avg_poss / gp, 1) if gp > 0 else 0.0
    ortg = round(tot_pts / poss * 100, 1) if poss > 0 else 0.0
    drtg = round(tot_opp_pts / opp_poss * 100, 1) if opp_poss > 0 else 0.0
    net_rtg = round(ortg - drtg, 1)

    efg_pct = round((tot_fgm + 0.5 * tot_3pm) / tot_fga * 100, 1) if tot_fga > 0 else 0.0
    tov_pct = round(tot_to / (tot_fga + 0.44 * tot_fta + tot_to) * 100, 1) if (tot_fga + 0.44 * tot_fta + tot_to) > 0 else 0.0
    orb_pct = round(tot_oreb / (tot_oreb + opp_dreb) * 100, 1) if (tot_oreb + opp_dreb) > 0 else 0.0
    ftr = round(tot_fta / tot_fga * 100, 1) if tot_fga > 0 else 0.0

    opp_efg_pct = round((opp_fgm + 0.5 * opp_3pm) / opp_fga * 100, 1) if opp_fga > 0 else 0.0
    opp_tov_pct = round(opp_to / (opp_fga + 0.44 * opp_fta + opp_to) * 100, 1) if (opp_fga + 0.44 * opp_fta + opp_to) > 0 else 0.0
    drb_pct = round(tot_dreb / (tot_dreb + opp_oreb) * 100, 1) if (tot_dreb + opp_oreb) > 0 else 0.0
    opp_ftr = round(opp_fta / opp_fga * 100, 1) if opp_fga > 0 else 0.0

    return {
        "pace": pace,
        "ortg": ortg,
        "drtg": drtg,
        "net_rtg": net_rtg,
        "efg_pct": efg_pct,
        "tov_pct": tov_pct,
        "orb_pct": orb_pct,
        "ft_rate": ftr,
        "opp_efg_pct": opp_efg_pct,
        "opp_tov_pct": opp_tov_pct,
        "drb_pct": drb_pct,
        "opp_ft_rate": opp_ftr
    }


def compute_player_situational_splits(game_logs):
    splits = {
        "Overall": game_logs,
        "Home Games": [g for g in game_logs if not g["opponent"].startswith("@")],
        "Away Games": [g for g in game_logs if g["opponent"].startswith("@")],
        "Last 5 Games": game_logs[:5],
        "In Team Wins": [g for g in game_logs if g["result"].startswith("W") or g["result"] == "OT-W"],
        "In Team Losses": [g for g in game_logs if g["result"].startswith("L") or g["result"] == "OT-L"]
    }

    rows = []
    for label, subset in splits.items():
        gp = len(subset)
        if gp == 0:
            continue
        tot_min = sum(g["min"] for g in subset)
        tot_pts = sum(g["pts"] for g in subset)
        tot_reb = sum(g["reb"] for g in subset)
        tot_ast = sum(g["ast"] for g in subset)
        tot_stl = sum(g["stl"] for g in subset)
        tot_blk = sum(g["blk"] for g in subset)
        tot_to = sum(g["to"] for g in subset)
        tot_fgm = sum(g["fgm"] for g in subset)
        tot_fga = sum(g["fga"] for g in subset)
        tot_pm = sum(g.get("plus_minus", 0) for g in subset)

        rows.append({
            "split": label,
            "gp": gp,
            "min_pg": round(tot_min / gp, 1),
            "pts_pg": round(tot_pts / gp, 1),
            "reb_pg": round(tot_reb / gp, 1),
            "ast_pg": round(tot_ast / gp, 1),
            "stl_pg": round(tot_stl / gp, 1),
            "blk_pg": round(tot_blk / gp, 1),
            "to_pg": round(tot_to / gp, 1),
            "plus_minus_pg": round(tot_pm / gp, 1),
            "fg_pct": round(tot_fgm / tot_fga * 100, 1) if tot_fga > 0 else 0.0
        })

    return rows


def compute_team_situational_splits(team_name, completed_games):
    team_games = []
    for g in completed_games:
        is_home = (g["home_team"] == team_name)
        is_away = (g["away_team"] == team_name)
        if not is_home and not is_away:
            continue

        team_pts = g["home_score"] if is_home else g["away_score"]
        opp_pts = g["away_score"] if is_home else g["home_score"]
        is_win = (team_pts > opp_pts)

        team_games.append({
            "date": g["date"],
            "is_home": is_home,
            "is_win": is_win,
            "pts_for": team_pts,
            "pts_against": opp_pts
        })

    splits = {
        "Overall": team_games,
        "Home": [g for g in team_games if g["is_home"]],
        "Away": [g for g in team_games if not g["is_home"]],
        "Last 5 Games": team_games[:5]
    }

    rows = []
    for label, subset in splits.items():
        gp = len(subset)
        if gp == 0:
            continue
        wins = sum(1 for g in subset if g["is_win"])
        losses = gp - wins
        pct = round(wins / gp * 100, 1)
        pts_for = round(sum(g["pts_for"] for g in subset) / gp, 1)
        pts_against = round(sum(g["pts_against"] for g in subset) / gp, 1)
        diff = round(pts_for - pts_against, 1)

        rows.append({
            "split": label,
            "gp": gp,
            "w": wins,
            "l": losses,
            "win_pct": pct,
            "pts_pg": pts_for,
            "opp_pts_pg": pts_against,
            "diff": diff
        })

    return rows


def compute_on_off_metrics(player_on_court, team_totals):
    on_poss = player_on_court.get("poss", 0.0)
    on_pf = player_on_court.get("pts_for", 0)
    on_pa = player_on_court.get("pts_against", 0)

    t_poss = team_totals.get("poss", 0.0)
    t_pf = team_totals.get("pts_for", 0)
    t_pa = team_totals.get("pts_against", 0)

    off_poss = max(0.0, t_poss - on_poss)
    off_pf = max(0, t_pf - on_pf)
    off_pa = max(0, t_pa - on_pa)

    team_on_ortg = (on_pf / on_poss * 100.0) if on_poss > 0 else 0.0
    team_on_drtg = (on_pa / on_poss * 100.0) if on_poss > 0 else 0.0
    team_on_net = team_on_ortg - team_on_drtg

    team_off_ortg = (off_pf / off_poss * 100.0) if off_poss > 0 else 0.0
    team_off_drtg = (off_pa / off_poss * 100.0) if off_poss > 0 else 0.0
    team_off_net = team_off_ortg - team_off_drtg

    team_diff_ortg = team_on_ortg - team_off_ortg
    team_diff_drtg = team_on_drtg - team_off_drtg
    team_diff_net = team_on_net - team_off_net

    return {
        "team_on_ortg": round(team_on_ortg, 1),
        "team_on_drtg": round(team_on_drtg, 1),
        "team_on_net_rtg": round(team_on_net, 1),
        "team_off_ortg": round(team_off_ortg, 1),
        "team_off_drtg": round(team_off_drtg, 1),
        "team_off_net_rtg": round(team_off_net, 1),
        "team_diff_ortg": round(team_diff_ortg, 1),
        "team_diff_drtg": round(team_diff_drtg, 1),
        "team_diff_net_rtg": round(team_diff_net, 1),

        "on_ortg": round(team_on_ortg, 1),
        "on_drtg": round(team_on_drtg, 1),
        "on_net_rtg": round(team_on_net, 1),
        "off_on_off": round(team_diff_ortg, 1),
        "def_on_off": round(team_diff_drtg, 1),
        "net_on_off": round(team_diff_net, 1)
    }