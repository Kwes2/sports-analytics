def parse_int(val):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def parse_split(val_str):
    """Parses 'made-attempted' strings like '10-18' into (made, attempted)."""
    if not val_str:
        return 0, 0
    if "-" in str(val_str):
        parts = str(val_str).split("-")
        return parse_int(parts[0]), parse_int(parts[1]) if len(parts) > 1 else 0
    return parse_int(val_str), 0


def process_boxscore_players(game_players, home_abbrev, away_abbrev, home_score, away_score, date_str):
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

        team_rows = []

        for stat_cat in team_entry.get("statistics", []):
            keys = stat_cat.get("names", [])
            for item in stat_cat.get("athletes", []):
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
                pos_str = ath.get("position", {}).get("abbreviation", "-")

                # Single-game Hollinger Game Score
                gmsc = round(
                    pts + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm) + 0.7 * oreb + 0.3 * dreb + stl + 0.7 * ast + 0.7 * blk - 0.4 * pf - to,
                    1
                )
                ts_pct = round(pts / (2 * (fga + 0.44 * fta)) * 100, 1) if (fga + 0.44 * fta) > 0 else 0.0

                team_rows.append({
                    "player_id": aid,
                    "player": player_name,
                    "pos": pos_str,
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
                    "gmsc": gmsc
                })

                player_game_events[aid] = {
                    "player_id": aid,
                    "player": player_name,
                    "team": team_display,
                    "team_id": team_id,
                    "team_abbrev": team_abbrev,
                    "pos": pos_str,
                    "minutes": minutes,
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
                    "log": {
                        "date": date_str,
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
                        "gmsc": gmsc,
                        "ts_pct": ts_pct
                    }
                }

        game_team_rows[team_id] = {
            "team_name": team_display,
            "team_abbrev": team_abbrev,
            "rows": team_rows
        }

    return game_team_rows, player_game_events


def compute_player_advanced_metrics(p):
    """Calculates TS%, eFG%, 3PAr, FTr, PPSA, AST/TO, TOV%, USG%, GmSc, and Stocks."""
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

    ts_pct = round(pts / (2 * (fga + 0.44 * fta)) * 100, 1) if (fga + 0.44 * fta) > 0 else 0.0
    efg_pct = round((fgm + 0.5 * fg3m) / fga * 100, 1) if fga > 0 else 0.0
    three_par = round(fg3a / fga * 100, 1) if fga > 0 else 0.0
    ft_rate = round(fta / fga * 100, 1) if fga > 0 else 0.0
    ppsa = round(pts / fga, 2) if fga > 0 else 0.0
    ast_to = round(ast / to, 2) if to > 0 else float(ast)
    tov_pct = round(to / (fga + 0.44 * fta + to) * 100, 1) if (fga + 0.44 * fta + to) > 0 else 0.0
    stocks_pg = round((stl + blk) / gp, 1) if gp > 0 else 0.0

    # Total Hollinger Game Score / GP
    tot_gmsc = pts + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm) + 0.7 * oreb + 0.3 * dreb + stl + 0.7 * ast + 0.7 * blk - 0.4 * pf - to
    gmsc_avg = round(tot_gmsc / gp, 1) if gp > 0 else 0.0

    # Estimated Usage Rate
    used_plays = fga + 0.44 * fta + to
    usg_pct = round((used_plays / (tot_min / 48.0 * 100.0)), 1) if tot_min > 0 else 0.0

    return {
        "gp": gp,
        "ts_pct": ts_pct,
        "efg_pct": efg_pct,
        "usg_pct": usg_pct,
        "tov_pct": tov_pct,
        "ast_to_ratio": ast_to,
        "three_par": three_par,
        "ft_rate": ft_rate,
        "ppsa": ppsa,
        "gmsc_avg": gmsc_avg,
        "stocks_pg": stocks_pg
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
            custom_power = round((diff * 1.5) + (win_pct * 0.5), 2)

            team_rows.append({
                "team_id": team_id,
                "team": team_name,
                "gp": gp,
                "w": wins,
                "l": losses,
                "win_pct": win_pct,
                "pts_pg": pts_for,
                "opp_pts_pg": pts_against,
                "diff": diff,
                "custom_power_rating": custom_power
            })

    team_rows.sort(key=lambda x: x["w"], reverse=True)
    return team_rows


def compute_team_advanced_metrics(team_name, team_games):
    """Computes Pace, ORtg, DRtg, NetRtg, and Four Factors for both Offense and Defense."""
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

    # Possession Estimation
    poss = 0.96 * (tot_fga + tot_to + 0.44 * tot_fta - tot_oreb)
    opp_poss = 0.96 * (opp_fga + opp_to + 0.44 * opp_fta - opp_oreb)
    avg_poss = (poss + opp_poss) / 2.0

    pace = round(avg_poss / gp, 1) if gp > 0 else 0.0
    ortg = round(tot_pts / poss * 100, 1) if poss > 0 else 0.0
    drtg = round(tot_opp_pts / opp_poss * 100, 1) if opp_poss > 0 else 0.0
    net_rtg = round(ortg - drtg, 1)

    # Four Factors: Offense
    efg_pct = round((tot_fgm + 0.5 * tot_3pm) / tot_fga * 100, 1) if tot_fga > 0 else 0.0
    tov_pct = round(tot_to / (tot_fga + 0.44 * tot_fta + tot_to) * 100, 1) if (tot_fga + 0.44 * tot_fta + tot_to) > 0 else 0.0
    orb_pct = round(tot_oreb / (tot_oreb + opp_dreb) * 100, 1) if (tot_oreb + opp_dreb) > 0 else 0.0
    ftr = round(tot_fta / tot_fga * 100, 1) if tot_fga > 0 else 0.0

    # Four Factors: Defense
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
        "In Team Wins": [g for g in game_logs if g["result"].startswith("W")],
        "In Team Losses": [g for g in game_logs if g["result"].startswith("L")]
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