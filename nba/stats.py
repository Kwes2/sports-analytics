def parse_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def process_boxscore_players(game_players, home_abbrev, away_abbrev, home_score, away_score, date_str):
    """
    Extracts individual player performances from a game box score.
    Returns:
      game_team_rows: {team_id: [player_rows]}
      player_game_events: {aid: {player_info, log_entry, game_totals}}
    """
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

                fg_parts = stats.get("FGM", "0-0").split("-") if "-" in stats.get("FGM", "") else [stats.get("FGM", "0"), stats.get("FGA", "0")]
                fgm = parse_int(fg_parts[0])
                fga = parse_int(fg_parts[1]) if len(fg_parts) > 1 else 0

                player_name = ath.get("displayName", "Unknown")
                pos_str = ath.get("position", {}).get("abbreviation", "-")

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
                    "fga": fga
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
                        "fga": fga
                    }
                }

        game_team_rows[team_id] = {
            "team_name": team_display,
            "team_abbrev": team_abbrev,
            "rows": team_rows
        }

    return game_team_rows, player_game_events


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


def compute_player_situational_splits(game_logs):
    """Slices a player's logs into Overall, Home, Away, Last 5, Wins, and Losses."""
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
    """Slices team schedule into Overall, Home, Away, and Last 5 games."""
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