import json
import math
from pathlib import Path
from db import get_db_connection, DB_PATH
from percentiles import compute_percentile, build_stat_pools, build_shot_pools

ZONES = ["0-4 ft", "4-14 ft", "14+ ft"]
GRANULAR_ZONES = ["rim", "short_mid", "long_mid", "corner_3", "atb_3"]


def compute_window_player_stats(start_date, end_date, db_path=DB_PATH):
    """
    Recalculates 100% of player statistics, advanced metrics, shot quality,
    assist expected points, and influence ratings on the fly for any date window.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # 1. Query Player Game Logs within Date Range
    cur.execute("""
        SELECT 
            player_id, player_name, team_id, team_abbrev, pos,
            COUNT(*) as gp,
            SUM(is_starter) as gs,
            SUM(minutes) as tot_min,
            SUM(pts) as tot_pts,
            SUM(reb) as tot_reb,
            SUM(ast) as tot_ast,
            SUM(stl) as tot_stl,
            SUM(blk) as tot_blk,
            SUM(to_val) as tot_to,
            SUM(pf) as tot_pf,
            SUM(plus_minus) as tot_pm,
            SUM(fgm) as tot_fgm,
            SUM(fga) as tot_fga,
            SUM(fg3m) as tot_fg3m,
            SUM(fg3a) as tot_fg3a,
            SUM(ftm) as tot_ftm,
            SUM(fta) as tot_fta,
            SUM(oreb) as tot_oreb,
            SUM(dreb) as tot_dreb
        FROM player_game_logs
        WHERE date BETWEEN ? AND ?
        GROUP BY player_id
    """, (start_date, end_date))
    log_rows = cur.fetchall()

    if not log_rows:
        conn.close()
        return []

    # 2. Query Granular Shots within Date Range
    cur.execute("""
        SELECT 
            shooter_id, granular_zone,
            COUNT(*) as fga,
            SUM(made) as fgm,
            SUM(CASE WHEN val = 3 AND made = 1 THEN 1 ELSE 0 END) as fg3m
        FROM shots
        WHERE date BETWEEN ? AND ?
        GROUP BY shooter_id, granular_zone
    """, (start_date, end_date))
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

    # 3. Query Distance Zone Splits within Date Range
    cur.execute("""
        SELECT 
            shooter_id, zone,
            COUNT(*) as fga,
            SUM(made) as fgm
        FROM shots
        WHERE date BETWEEN ? AND ?
        GROUP BY shooter_id, zone
    """, (start_date, end_date))
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

    # 4. Query Assisted Baskets within Date Range
    cur.execute("""
        SELECT 
            passer_id, scorer_id, val, zone
        FROM assisted_baskets
        WHERE date BETWEEN ? AND ?
    """, (start_date, end_date))
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

    # 5. Query Stints & Calculate On-Court Influence within Date Range
    cur.execute("""
        SELECT 
            home_team_id, away_team_id, home_lineup, away_lineup, home_pts, away_pts, poss
        FROM stints
        WHERE date BETWEEN ? AND ?
    """, (start_date, end_date))
    stint_rows = cur.fetchall()

    player_on_court = {}
    pair_ledger = {}

    for sr in stint_rows:
        h_lineup = json.loads(sr["home_lineup"])
        a_lineup = json.loads(sr["away_lineup"])
        h_pts = sr["home_pts"]
        a_pts = sr["away_pts"]
        poss = sr["poss"]

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

        # Teammate pairs
        for team_lineup, pts_f, pts_a in [(h_lineup, h_pts, a_pts), (a_lineup, a_pts, h_pts)]:
            for i in range(len(team_lineup)):
                for j in range(i + 1, len(team_lineup)):
                    p1, p2 = team_lineup[i], team_lineup[j]
                    for m1, m2 in [(p1, p2), (p2, p1)]:
                        if m1 not in pair_ledger:
                            pair_ledger[m1] = {"teammates": {}, "opponents": {}}
                        if m2 not in pair_ledger[m1]["teammates"]:
                            pair_ledger[m1]["teammates"][m2] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
                        pair_ledger[m1]["teammates"][m2]["pts_for"] += pts_f
                        pair_ledger[m1]["teammates"][m2]["pts_against"] += pts_a
                        pair_ledger[m1]["teammates"][m2]["poss"] += poss

        # Opponent pairs
        for hp in h_lineup:
            for ap in a_lineup:
                for m1, m2, pf, pa in [(hp, ap, h_pts, a_pts), (ap, hp, a_pts, h_pts)]:
                    if m1 not in pair_ledger:
                        pair_ledger[m1] = {"teammates": {}, "opponents": {}}
                    if m2 not in pair_ledger[m1]["opponents"]:
                        pair_ledger[m1]["opponents"][m2] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
                    pair_ledger[m1]["opponents"][m2]["pts_for"] += pf
                    pair_ledger[m1]["opponents"][m2]["pts_against"] += pa
                    pair_ledger[m1]["opponents"][m2]["poss"] += poss

    conn.close()

    # Compute On-Court Baselines
    player_baselines = {}
    for pid, oc in player_on_court.items():
        if oc["poss"] >= 50.0:
            player_baselines[pid] = {
                "ortg": (oc["pts_for"] / oc["poss"]) * 100.0,
                "drtg": (oc["pts_against"] / oc["poss"]) * 100.0
            }
        else:
            player_baselines[pid] = {"ortg": 112.0, "drtg": 112.0}

    # Compute Influence Metrics per Player
    influence_results = {}
    for pid in player_on_court.keys():
        p_pairs = pair_ledger.get(pid, {"teammates": {}, "opponents": {}})

        # Teammate deltas
        t_off_diff, t_def_diff, t_poss = 0.0, 0.0, 0.0
        for tid, data in p_pairs["teammates"].items():
            if data["poss"] >= 4.0:
                s_ortg = (data["pts_for"] / data["poss"]) * 100.0
                s_drtg = (data["pts_against"] / data["poss"]) * 100.0
                t_base = player_baselines.get(tid, {"ortg": 112.0, "drtg": 112.0})
                t_off_diff += (s_ortg - t_base["ortg"]) * data["poss"]
                t_def_diff += (t_base["drtg"] - s_drtg) * data["poss"]
                t_poss += data["poss"]

        t_off = round(t_off_diff / t_poss, 2) if t_poss > 0 else 0.0
        t_def = round(t_def_diff / t_poss, 2) if t_poss > 0 else 0.0

        # Opponent deltas
        o_off_diff, o_def_diff, o_poss = 0.0, 0.0, 0.0
        for oid, data in p_pairs["opponents"].items():
            if data["poss"] >= 4.0:
                opp_ortg = (data["pts_against"] / data["poss"]) * 100.0
                opp_drtg = (data["pts_for"] / data["poss"]) * 100.0
                o_base = player_baselines.get(oid, {"ortg": 112.0, "drtg": 112.0})
                o_off_diff += (o_base["ortg"] - opp_ortg) * data["poss"]
                o_def_diff += (opp_drtg - o_base["drtg"]) * data["poss"]
                o_poss += data["poss"]

        o_off = round(o_off_diff / o_poss, 2) if o_poss > 0 else 0.0
        o_def = round(o_def_diff / o_poss, 2) if o_poss > 0 else 0.0

        t_net = round(t_off + t_def, 2)
        o_net = round(o_off + o_def, 2)
        ovr = round(0.5 * t_net + 0.5 * o_net, 2)

        influence_results[pid] = {
            "teammate_off_impact": t_off, "teammate_def_impact": t_def, "teammate_overall_impact": t_net,
            "opponent_off_impact": o_off, "opponent_def_impact": o_def, "opponent_overall_impact": o_net,
            "overall_impact": ovr
        }

    # 6. Synthesize Unified Player Rows
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

        # Advanced stats
        ts_pct = round(r["tot_pts"] / (2 * (fga + 0.44 * fta)) * 100, 1) if (fga + 0.44 * fta) > 0 else 0.0
        efg_pct = round((fgm + 0.5 * fg3m) / fga * 100, 1) if fga > 0 else 0.0
        three_par = round(fg3a / fga * 100, 1) if fga > 0 else 0.0
        ft_rate = round(fta / fga * 100, 1) if fga > 0 else 0.0
        ppsa = round(r["tot_pts"] / fga, 2) if fga > 0 else 0.0
        ast_to = round(r["tot_ast"] / r["tot_to"], 2) if r["tot_to"] > 0 else float(r["tot_ast"])
        tov_pct = round(r["tot_to"] / (fga + 0.44 * fta + r["tot_to"]) * 100, 1) if (fga + 0.44 * fta + r["tot_to"]) > 0 else 0.0
        stocks_pg = round((r["tot_stl"] + r["tot_blk"]) / gp, 1) if gp > 0 else 0.0

        tot_gmsc = r["tot_pts"] + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm) + 0.7 * r["tot_oreb"] + 0.3 * r["tot_dreb"] + r["tot_stl"] + 0.7 * r["tot_ast"] + 0.7 * r["tot_blk"] - 0.4 * r["tot_pf"] - r["tot_to"]
        gmsc_avg = round(tot_gmsc / gp, 1) if gp > 0 else 0.0

        used_plays = fga + 0.44 * fta + r["tot_to"]
        usg_pct = round((used_plays / (r["tot_min"] * 2.0)) * 100.0, 1) if r["tot_min"] > 0 else 0.0

        # Shot quality
        p_gz = player_granular.get(aid, {z: {"fga": 0, "fgm": 0, "fg3m": 0} for z in GRANULAR_ZONES})
        tot_tracked = sum(p_gz[z]["fga"] for z in GRANULAR_ZONES)
        exp_makes = sum(p_gz[z]["fga"] * (league_granular_efg.get(z, 50.0) / 100.0) for z in GRANULAR_ZONES)
        xefg_pct = round(exp_makes / tot_tracked * 100, 1) if tot_tracked > 0 else 0.0
        smoe = round(efg_pct - xefg_pct, 1)

        rim_fga = p_gz["rim"]["fga"]
        three_fga = p_gz["corner_3"]["fga"] + p_gz["atb_3"]["fga"]
        mei = round((rim_fga + three_fga + 0.44 * fta) / (fga + 0.44 * fta) * 100, 1) if (fga + 0.44 * fta) > 0 else 0.0

        # Passing quality
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

        # PRF
        prf_pg = round(pts_pg + pts_created_pg, 1)

        # Distance zones
        p_z = player_zones.get(aid, {z: {"fga": 0, "fgm": 0} for z in ZONES})
        tot_z_fga = sum(p_z[z]["fga"] for z in ZONES)
        zone_dict = {}
        for z, label in [("0-4 ft", "rim"), ("4-14 ft", "mid"), ("14+ ft", "three")]:
            zf = p_z[z]["fga"]
            zm = p_z[z]["fgm"]
            zone_dict[f"{label}_fga_pg"] = round(zf / gp, 1) if gp > 0 else 0.0
            zone_dict[f"{label}_fg_pct"] = round(zm / zf * 100, 1) if zf > 0 else 0.0
            zone_dict[f"{label}_share"] = round(zf / tot_z_fga * 100, 1) if tot_z_fga > 0 else 0.0

        inf = influence_results.get(aid, {
            "teammate_off_impact": 0.0, "teammate_def_impact": 0.0, "teammate_overall_impact": 0.0,
            "opponent_off_impact": 0.0, "opponent_def_impact": 0.0, "opponent_overall_impact": 0.0,
            "overall_impact": 0.0
        })

        output_rows.append({
            "player_id": aid, "player": r["player_name"], "team": r["team_abbrev"], "team_id": r["team_id"], "pos": r["pos"],
            "gp": gp, "gs": r["gs"], "min_pg": min_pg, "pts_pg": pts_pg, "prf_pg": prf_pg,
            "reb_pg": reb_pg, "ast_pg": ast_pg, "stl_pg": stl_pg, "blk_pg": blk_pg, "to_pg": to_pg, "pf_pg": pf_pg,
            "plus_minus_pg": plus_minus_pg, "fgm_pg": round(fgm / gp, 1) if gp > 0 else 0.0, "fga_pg": round(fga / gp, 1) if gp > 0 else 0.0,
            "fg_pct": fg_pct, "fg3m_pg": round(fg3m / gp, 1) if gp > 0 else 0.0, "fg3a_pg": round(fg3a / gp, 1) if gp > 0 else 0.0,
            "fg3_pct": fg3_pct, "ftm_pg": round(ftm / gp, 1) if gp > 0 else 0.0, "fta_pg": round(fta / gp, 1) if gp > 0 else 0.0,
            "ft_pct": ft_pct, "oreb_pg": round(r["tot_oreb"] / gp, 1) if gp > 0 else 0.0, "dreb_pg": round(r["tot_dreb"] / gp, 1) if gp > 0 else 0.0,
            "ts_pct": ts_pct, "efg_pct": efg_pct, "xefg_pct": xefg_pct, "smoe": smoe, "mei": mei,
            "usg_pct": usg_pct, "tov_pct": tov_pct, "ast_to_ratio": ast_to, "three_par": three_par, "ft_rate": ft_rate,
            "ppsa": ppsa, "gmsc_avg": gmsc_avg, "stocks_pg": stocks_pg,
            "ast_recorded": tot_ast_ct, "pts_created_pg": pts_created_pg, "pts_per_ast": pts_per_ast,
            "xpts_per_ast": xpts_per_ast, "paoe": paoe, "points_added_pg": points_added_pg,
            "rim_ast_pct": rim_ast_pct, "three_ast_pct": three_ast_pct,
            **zone_dict,
            **inf
        })

    output_rows.sort(key=lambda x: x["pts_pg"], reverse=True)
    return output_rows