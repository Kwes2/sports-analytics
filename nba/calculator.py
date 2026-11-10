"""
calculator.py - Handles on-the-fly custom window aggregations, 
dynamic player profile recalculations, and Game Finder queries from SQLite.
"""

import json
from pathlib import Path
from db import get_db_connection, DB_PATH
from percentiles import (
    build_stat_pools,
    build_shot_pools,
    compute_percentile,
    compute_rank,
    compute_player_rankings_and_percentiles
)
from stats import (
    compute_player_advanced_metrics,
    compute_assist_connection_metrics,
    compute_on_off_metrics,
    compute_player_situational_splits
)
from shots import (
    ZONES,
    GRANULAR_ZONES,
    compute_shot_quality_metrics
)
from influence import InfluenceEngine
from stat_metadata import STAT_METADATA, get_stat_meta


class DummyBaselineEngine:
    def get_baseline(self, player_id):
        return {"ortg": 112.0, "drtg": 112.0, "net_rtg": 0.0}


def search_player_game_performances(filters=None, db_path=DB_PATH):
    """
    Queries individual player game performances from SQLite matching filter criteria.
    Outputs all per-game box score, shooting, and advanced metrics.
    """
    if filters is None:
        filters = {}

    conn = get_db_connection(db_path)
    cur = conn.cursor()

    query = """
        SELECT 
            l.player_id, p.player_name, p.pos, l.team_abbrev, p.team_id, l.date, l.game_id,
            l.minutes, l.pts, l.reb, l.ast, l.stl, l.blk, l.to_val as to_count, l.pf,
            l.plus_minus, l.fgm, l.fga, l.fg3m, l.fg3a, l.ftm, l.fta, l.oreb, l.dreb,
            g.home_team_name, g.away_team_name, g.home_score, g.away_score
        FROM player_game_logs l
        JOIN players p ON l.player_id = p.player_id
        JOIN games g ON l.game_id = g.game_id
        WHERE 1=1
    """
    params = []

    if filters.get("start_date") and filters.get("end_date"):
        query += " AND l.date BETWEEN ? AND ?"
        params.extend([filters["start_date"], filters["end_date"]])
    elif filters.get("season_year"):
        query += " AND l.season_year = ?"
        params.append(filters["season_year"])

    if filters.get("season_type"):
        query += " AND l.season_type = ?"
        params.append(filters["season_type"])

    if filters.get("min_pts") is not None:
        query += " AND l.pts >= ?"
        params.append(filters["min_pts"])

    if filters.get("min_reb") is not None:
        query += " AND l.reb >= ?"
        params.append(filters["min_reb"])

    if filters.get("min_ast") is not None:
        query += " AND l.ast >= ?"
        params.append(filters["min_ast"])

    if filters.get("min_min") is not None:
        query += " AND l.minutes >= ?"
        params.append(filters["min_min"])

    query += " ORDER BY l.date DESC, l.pts DESC LIMIT 500"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    results = []
    for r in rows:
        is_home = (r["team_abbrev"] in r["home_team_name"] or r["team_id"] in r["home_team_name"])
        if is_home:
            opp = f"vs {r['away_team_name']}"
            is_win = r["home_score"] > r["away_score"]
            res = f"{'W' if is_win else 'L'} {r['home_score']}-{r['away_score']}"
        else:
            opp = f"@ {r['home_team_name']}"
            is_win = r["away_score"] > r["home_score"]
            res = f"{'W' if is_win else 'L'} {r['away_score']}-{r['home_score']}"

        if filters.get("result") and not res.startswith(filters["result"]):
            continue

        fga = r["fga"]
        fgm = r["fgm"]
        fg3a = r["fg3a"]
        fg3m = r["fg3m"]
        fta = r["fta"]
        ftm = r["ftm"]
        pts = r["pts"]
        oreb = r["oreb"]
        dreb = r["dreb"]
        ast = r["ast"]
        stl = r["stl"]
        blk = r["blk"]
        pf = r["pf"]
        to_cnt = r["to_count"]

        fg_pct = round(fgm / fga * 100, 1) if fga > 0 else 0.0
        fg3_pct = round(fg3m / fg3a * 100, 1) if fg3a > 0 else 0.0
        ft_pct = round(ftm / fta * 100, 1) if fta > 0 else 0.0
        ts_pct = round(pts / (2 * (fga + 0.44 * fta)) * 100, 1) if (fga + 0.44 * fta) > 0 else 0.0
        gmsc = round(
            pts + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm) + 0.7 * oreb + 0.3 * dreb + stl + 0.7 * ast + 0.7 * blk - 0.4 * pf - to_cnt,
            1
        )

        results.append({
            "player_id": r["player_id"],
            "player": r["player_name"],
            "team": r["team_abbrev"],
            "team_id": r["team_id"],
            "pos": r["pos"],
            "date": r["date"],
            "opponent": opp,
            "result": res,
            "min": int(r["minutes"]),
            "pts": pts,
            "reb": r["reb"],
            "ast": ast,
            "stl": stl,
            "blk": blk,
            "to": to_cnt,
            "pf": pf,
            "plus_minus": r["plus_minus"],
            "fgm": fgm,
            "fga": fga,
            "fg_pct": fg_pct,
            "fg3m": fg3m,
            "fg3a": fg3a,
            "fg3_pct": fg3_pct,
            "ftm": ftm,
            "fta": fta,
            "ft_pct": ft_pct,
            "oreb": oreb,
            "dreb": dreb,
            "gmsc": gmsc,
            "ts_pct": ts_pct,
            "box_score": f"boxscore.html?id={r['game_id']}"
        })

    return results


def compute_window_player_stats(start_date=None, end_date=None, season_years=None, season_types=None, db_path=DB_PATH):
    """
    Recalculates player statistics, advanced metrics, shot quality,
    and decomposed RAPM on the fly for any date or season window.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    where_clauses = []
    params = []

    # Prioritize date filter if specified
    if start_date and end_date:
        where_clauses.append("l.date BETWEEN ? AND ?")
        params.extend([start_date, end_date])
    elif season_years:
        placeholders = ",".join(["?"] * len(season_years))
        where_clauses.append(f"l.season_year IN ({placeholders})")
        params.extend(season_years)

    if season_types:
        placeholders = ",".join(["?"] * len(season_types))
        where_clauses.append(f"l.season_type IN ({placeholders})")
        params.extend(season_types)

    where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cur.execute(f"""
        SELECT 
            l.player_id, p.player_name, p.team_id, p.team_abbrev, p.pos,
            COUNT(*) as gp,
            SUM(l.is_starter) as gs,
            SUM(l.minutes) as tot_min,
            SUM(l.pts) as tot_pts,
            SUM(l.reb) as tot_reb,
            SUM(l.ast) as tot_ast,
            SUM(l.stl) as tot_stl,
            SUM(l.blk) as tot_blk,
            SUM(l.to_val) as tot_to,
            SUM(l.pf) as tot_pf,
            SUM(l.plus_minus) as tot_pm,
            SUM(l.fgm) as tot_fgm,
            SUM(l.fga) as tot_fga,
            SUM(l.fg3m) as tot_fg3m,
            SUM(l.fg3a) as tot_fg3a,
            SUM(l.ftm) as tot_ftm,
            SUM(l.fta) as tot_fta,
            SUM(l.oreb) as tot_oreb,
            SUM(l.dreb) as tot_dreb
        FROM player_game_logs l
        JOIN players p ON l.player_id = p.player_id
        {where_str}
        GROUP BY l.player_id
    """, params)
    log_rows = cur.fetchall()

    if not log_rows:
        conn.close()
        return []

    # Shots query
    shot_where = where_str.replace("l.date", "date").replace("l.season_year", "season_year").replace("l.season_type", "season_type")
    cur.execute(f"""
        SELECT 
            shooter_id, granular_zone,
            COUNT(*) as fga,
            SUM(made) as fgm,
            SUM(CASE WHEN val = 3 AND made = 1 THEN 1 ELSE 0 END) as fg3m
        FROM shots
        {shot_where}
        GROUP BY shooter_id, granular_zone
    """, params)
    shot_rows = cur.fetchall()

    player_granular = {}
    league_granular = {gz: {"fga": 0, "fgm": 0, "fg3m": 0} for gz in GRANULAR_ZONES}

    for sr in shot_rows:
        sid = sr["shooter_id"]
        gz = sr["granular_zone"]
        fga = sr["fga"]
        fgm = sr["fgm"]
        fg3m = sr["fg3m"]

        if sid not in player_granular:
            player_granular[sid] = {z: {"fga": 0, "fgm": 0, "fg3m": 0} for z in GRANULAR_ZONES}

        if gz in player_granular[sid]:
            player_granular[sid][gz]["fga"] += fga
            player_granular[sid][gz]["fgm"] += fgm
            player_granular[sid][gz]["fg3m"] += fg3m

        if gz in league_granular:
            league_granular[gz]["fga"] += fga
            league_granular[gz]["fgm"] += fgm
            league_granular[gz]["fg3m"] += fg3m

    league_granular_efg = {}
    for gz in GRANULAR_ZONES:
        f = league_granular[gz]["fga"]
        m = league_granular[gz]["fgm"]
        t = league_granular[gz]["fg3m"]
        league_granular_efg[gz] = round((m + 0.5 * t) / f * 100, 1) if f > 0 else 50.0

    # Distance zone query
    cur.execute(f"""
        SELECT shooter_id, zone, COUNT(*) as fga, SUM(made) as fgm
        FROM shots
        {shot_where}
        GROUP BY shooter_id, zone
    """, params)
    zone_rows = cur.fetchall()

    player_zones = {}
    league_zone_totals = {z: {"fga": 0, "fgm": 0} for z in ZONES}

    for zr in zone_rows:
        sid = zr["shooter_id"]
        z = zr["zone"]
        fga = zr["fga"]
        fgm = zr["fgm"]

        if sid not in player_zones:
            player_zones[sid] = {zk: {"fga": 0, "fgm": 0} for zk in ZONES}

        if z in player_zones[sid]:
            player_zones[sid][z]["fga"] += fga
            player_zones[sid][z]["fgm"] += fgm

        if z in league_zone_totals:
            league_zone_totals[z]["fga"] += fga
            league_zone_totals[z]["fgm"] += fgm

    league_zone_avg_fg = {
        z: round(league_zone_totals[z]["fgm"] / league_zone_totals[z]["fga"] * 100, 1) if league_zone_totals[z]["fga"] > 0 else 0.0
        for z in ZONES
    }

    # Assisted baskets query
    cur.execute(f"""
        SELECT passer_id, scorer_id, val, zone
        FROM assisted_baskets
        {shot_where}
    """, params)
    assist_rows = cur.fetchall()

    player_assists = {}
    for ar in assist_rows:
        pid = ar["passer_id"]
        if pid not in player_assists:
            player_assists[pid] = []
        player_assists[pid].append({
            "scorer_id": ar["scorer_id"],
            "val": ar["val"],
            "zone": ar["zone"]
        })

    # Fixed Stints Query: join with games to get home_team_id and away_team_id reliably
    stint_where = where_str.replace("l.", "s.")
    cur.execute(f"""
        SELECT g.home_team_id, g.away_team_id, s.home_lineup, s.away_lineup, s.home_pts, s.away_pts, s.poss
        FROM stints s
        JOIN games g ON s.game_id = g.game_id
        {stint_where}
    """, params)
    stint_rows = cur.fetchall()

    player_on_court = {}
    team_totals = {}
    valid_stints = []

    for sr in stint_rows:
        h_lineup = json.loads(sr["home_lineup"])
        a_lineup = json.loads(sr["away_lineup"])
        h_pts = sr["home_pts"]
        a_pts = sr["away_pts"]
        poss = sr["poss"]
        h_tid = sr["home_team_id"]
        a_tid = sr["away_team_id"]

        valid_stints.append({
            "home_lineup": h_lineup,
            "away_lineup": a_lineup,
            "home_pts": h_pts,
            "away_pts": a_pts,
            "poss": poss
        })

        if h_tid not in team_totals:
            team_totals[h_tid] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
        if a_tid not in team_totals:
            team_totals[a_tid] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}

        team_totals[h_tid]["pts_for"] += h_pts
        team_totals[h_tid]["pts_against"] += a_pts
        team_totals[h_tid]["poss"] += poss

        team_totals[a_tid]["pts_for"] += a_pts
        team_totals[a_tid]["pts_against"] += h_pts
        team_totals[a_tid]["poss"] += poss

        for hp in h_lineup:
            if hp not in player_on_court:
                player_on_court[hp] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
            player_on_court[hp]["pts_for"] += h_pts
            player_on_court[hp]["pts_against"] += a_pts
            player_on_court[hp]["poss"] += poss

        for ap in a_lineup:
            if ap not in player_on_court:
                player_on_court[ap] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
            player_on_court[ap]["pts_for"] += a_pts
            player_on_court[ap]["pts_against"] += h_pts
            player_on_court[ap]["poss"] += poss

    conn.close()

    active_players_dict = {r["player_id"]: None for r in log_rows}
    influence_engine = InfluenceEngine(active_players_dict, DummyBaselineEngine(), None, all_games_stints=valid_stints)
    influence_results = influence_engine.attr

    output_rows = []
    for r in log_rows:
        aid = r["player_id"]
        gp = r["gp"]
        min_pg = round(r["tot_min"] / gp, 1) if gp > 0 else 0.0
        pts_pg = round(r["tot_pts"] / gp, 1) if gp > 0 else 0.0
        reb_pg = round(r["tot_reb"] / gp, 1) if gp > 0 else 0.0
        ast_pg = round(r["tot_ast"] / gp, 1) if gp > 0 else 0.0
        stl_pg = round(r["tot_stl"] / gp, 1) if gp > 0 else 0.0
        blk_pg = round(r["tot_blk"] / gp, 1) if gp > 0 else 0.0
        to_pg = round(r["tot_to"] / gp, 1) if gp > 0 else 0.0
        pf_pg = round(r["tot_pf"] / gp, 1) if gp > 0 else 0.0
        plus_minus_pg = round(r["tot_pm"] / gp, 1) if gp > 0 else 0.0

        fga = r["tot_fga"]
        fgm = r["tot_fgm"]
        fg_pct = round(fgm / fga * 100, 1) if fga > 0 else 0.0

        fg3a = r["tot_fg3a"]
        fg3m = r["tot_fg3m"]
        fg3_pct = round(fg3m / fg3a * 100, 1) if fg3a > 0 else 0.0

        fta = r["tot_fta"]
        ftm = r["tot_ftm"]
        ft_pct = round(ftm / fta * 100, 1) if fta > 0 else 0.0

        p_struct = {
            "gp": gp, "tot_min": r["tot_min"], "tot_pts": r["tot_pts"], "tot_reb": r["tot_reb"],
            "tot_ast": r["tot_ast"], "tot_stl": r["tot_stl"], "tot_blk": r["tot_blk"], "tot_to": r["tot_to"],
            "tot_pf": r["tot_pf"], "tot_fga": fga, "tot_fgm": fgm, "tot_fg3a": fg3a, "tot_fg3m": fg3m,
            "tot_fta": fta, "tot_ftm": ftm, "tot_oreb": r["tot_oreb"], "tot_dreb": r["tot_dreb"]
        }

        adv = compute_player_advanced_metrics(p_struct)
        on_off = compute_on_off_metrics(player_on_court.get(aid, {}), team_totals.get(r["team_id"], {}))
        p_gz = player_granular.get(aid, {z: {"fga": 0, "fgm": 0, "fg3m": 0} for z in GRANULAR_ZONES})
        sq_metrics = compute_shot_quality_metrics(p_gz, league_granular_efg, fta, fga)

        ev_list = player_assists.get(aid, [])
        tot_ast_ct = len(ev_list)
        pts_created = sum(e["val"] for e in ev_list)
        pts_created_pg = round(pts_created / gp, 1) if gp > 0 else 0.0
        pts_per_ast = round(pts_created / tot_ast_ct, 2) if tot_ast_ct > 0 else 0.0

        tot_xpts = sum(e["val"] * (league_zone_avg_fg.get(e["zone"], 50.0) / 100.0) for e in ev_list)
        xpts_per_ast = round(tot_xpts / tot_ast_ct, 2) if tot_ast_ct > 0 else 0.0
        paoe = round(pts_per_ast - xpts_per_ast, 2) if tot_ast_ct > 0 else 0.0
        points_added_pg = round((pts_created - tot_xpts) / gp, 2) if gp > 0 else 0.0
        rim_ast_pct = round(sum(1 for e in ev_list if e["zone"] == "0-4 ft") / tot_ast_ct * 100, 1) if tot_ast_ct > 0 else 0.0
        three_ast_pct = round(sum(1 for e in ev_list if e["val"] == 3) / tot_ast_ct * 100, 1) if tot_ast_ct > 0 else 0.0

        prf_pg = round(pts_pg + pts_created_pg, 1)

        p_z = player_zones.get(aid, {z: {"fga": 0, "fgm": 0} for z in ZONES})
        tot_z_fga = sum(p_z[z]["fga"] for z in ZONES)
        zone_dict = {}
        for z, label in [("0-4 ft", "rim"), ("4-14 ft", "mid"), ("14+ ft", "three")]:
            zf = p_z[z]["fga"]
            zm = p_z[z]["fgm"]
            zone_dict[f"{label}_fga_pg"] = round(zf / gp, 1) if gp > 0 else 0.0
            zone_dict[f"{label}_fg_pct"] = round(zm / zf * 100, 1) if zf > 0 else 0.0
            zone_dict[f"{label}_share"] = round(zf / tot_z_fga * 100, 1) if tot_z_fga > 0 else 0.0

        inf = influence_results.get(aid, {"orapm": 0.0, "drapm": 0.0, "net_rapm": 0.0})

        output_rows.append({
            "player_id": aid, "player": r["player_name"], "team": r["team_abbrev"], "team_id": r["team_id"], "pos": r["pos"],
            "gp": gp, "gs": r["gs"], "min_pg": min_pg, "pts_pg": pts_pg, "prf_pg": prf_pg,
            "reb_pg": reb_pg, "ast_pg": ast_pg, "stl_pg": stl_pg, "blk_pg": blk_pg, "to_pg": to_pg, "pf_pg": pf_pg,
            "plus_minus_pg": plus_minus_pg, "fgm_pg": round(fgm / gp, 1) if gp > 0 else 0.0, "fga_pg": round(fga / gp, 1) if gp > 0 else 0.0,
            "fg_pct": fg_pct, "fg3m_pg": round(fg3m / gp, 1) if gp > 0 else 0.0, "fg3a_pg": round(fg3a / gp, 1) if gp > 0 else 0.0,
            "fg3_pct": fg3_pct, "ftm_pg": round(ftm / gp, 1) if gp > 0 else 0.0, "fta_pg": round(fta / gp, 1) if gp > 0 else 0.0,
            "ft_pct": ft_pct, "oreb_pg": round(r["tot_oreb"] / gp, 1) if gp > 0 else 0.0, "dreb_pg": round(r["tot_dreb"] / gp, 1) if gp > 0 else 0.0,
            **adv, **sq_metrics, **on_off,
            "ast_recorded": tot_ast_ct, "pts_created_pg": pts_created_pg, "pts_per_ast": pts_per_ast,
            "xpts_per_ast": xpts_per_ast, "paoe": paoe, "points_added_pg": points_added_pg,
            "rim_ast_pct": rim_ast_pct, "three_ast_pct": three_ast_pct,
            **zone_dict, **inf
        })

    output_rows.sort(key=lambda x: x["pts_pg"], reverse=True)
    return output_rows


def compute_window_single_player_profile(player_id, start_date=None, end_date=None, season_years=None, season_types=None, db_path=DB_PATH):
    """
    Recalculates a single player's entire categorized profile (values, league ranks,
    league percentiles, pos ranks, pos percentiles) across any custom window.
    """
    all_players = compute_window_player_stats(start_date, end_date, season_years, season_types, db_path)
    if not all_players:
        return None

    target = next((p for p in all_players if str(p["player_id"]) == str(player_id)), None)
    if not target:
        return None

    stat_keys = list(STAT_METADATA.keys())
    league_pools = {k: [] for k in stat_keys}
    pos_pools = {}

    for p in all_players:
        pos = p["pos"]
        if pos not in pos_pools:
            pos_pools[pos] = {k: [] for k in stat_keys}
        for k in stat_keys:
            val = p.get(k, 0.0)
            league_pools[k].append(val)
            pos_pools[pos][k].append(val)

    rankings_data = compute_player_rankings_and_percentiles(target, league_pools, pos_pools, target["pos"], stat_keys)

    categorized_tables = {
        "Basic": [],
        "Advanced": [],
        "Shooting": [],
        "Passing": [],
        "Ratings": [],
        "Miscellaneous": []
    }

    for k, v in target.items():
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
                "data": {"meta_keys": ["stat_name"], "rows": rows}
            })

    return {
        "player_id": target["player_id"],
        "name": target["player"],
        "team": target["team"],
        "team_id": target["team_id"],
        "position": target["pos"],
        "sections": sections
    }