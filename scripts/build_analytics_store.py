"""
scripts/build_analytics_store.py
NBA Analytics Platform - Master Production Synthesizer & Percentile Ranker

Synthesizes all analytical engines into tiered production datasets:
- Tier 1: Directory Indexes (players_index_{season}.json, teams_index_{season}.json) ~75 KB
- Tier 2: Deep Entity Profiles (players/{season}/{id}.json, teams/{season}/{abbrev}.json) ~15 KB each
- Tier 3: Categorical Leaderboards (leaderboards_{season}.json) ~35 KB
- Legacy/Catalog Stores: players_{season}.json and teams_{season}.json
"""

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AnalyticsStore")

SEASONS = ["2026-27", "2025-26"]

NBA_TEAM_METADATA = {
    1610612737: {"abbrev": "ATL", "name": "Atlanta Hawks", "conference": "East", "division": "Southeast", "colors": {"primary": "#E03A3E", "secondary": "#C1D32F"}},
    1610612738: {"abbrev": "BOS", "name": "Boston Celtics", "conference": "East", "division": "Atlantic", "colors": {"primary": "#007A33", "secondary": "#BA9653"}},
    1610612751: {"abbrev": "BKN", "name": "Brooklyn Nets", "conference": "East", "division": "Atlantic", "colors": {"primary": "#000000", "secondary": "#FFFFFF"}},
    1610612766: {"abbrev": "CHA", "name": "Charlotte Hornets", "conference": "East", "division": "Southeast", "colors": {"primary": "#1D1160", "secondary": "#00788C"}},
    1610612741: {"abbrev": "CHI", "name": "Chicago Bulls", "conference": "East", "division": "Central", "colors": {"primary": "#CE1141", "secondary": "#000000"}},
    1610612739: {"abbrev": "CLE", "name": "Cleveland Cavaliers", "conference": "East", "division": "Central", "colors": {"primary": "#860038", "secondary": "#041E42"}},
    1610612742: {"abbrev": "DAL", "name": "Dallas Mavericks", "conference": "West", "division": "Southwest", "colors": {"primary": "#00538C", "secondary": "#002B5E"}},
    1610612743: {"abbrev": "DEN", "name": "Denver Nuggets", "conference": "West", "division": "Northwest", "colors": {"primary": "#0E2240", "secondary": "#FEC524"}},
    1610612765: {"abbrev": "DET", "name": "Detroit Pistons", "conference": "East", "division": "Central", "colors": {"primary": "#1D42BA", "secondary": "#C8102E"}},
    1610612744: {"abbrev": "GSW", "name": "Golden State Warriors", "conference": "West", "division": "Pacific", "colors": {"primary": "#1D428A", "secondary": "#FFC72C"}},
    1610612745: {"abbrev": "HOU", "name": "Houston Rockets", "conference": "West", "division": "Southwest", "colors": {"primary": "#CE1141", "secondary": "#000000"}},
    1610612754: {"abbrev": "IND", "name": "Indiana Pacers", "conference": "East", "division": "Central", "colors": {"primary": "#002D62", "secondary": "#FDBB30"}},
    1610612746: {"abbrev": "LAC", "name": "LA Clippers", "conference": "West", "division": "Pacific", "colors": {"primary": "#C8102E", "secondary": "#1D428A"}},
    1610612747: {"abbrev": "LAL", "name": "Los Angeles Lakers", "conference": "West", "division": "Pacific", "colors": {"primary": "#552583", "secondary": "#FDB927"}},
    1610612763: {"abbrev": "MEM", "name": "Memphis Grizzlies", "conference": "West", "division": "Southwest", "colors": {"primary": "#5D76A9", "secondary": "#12173F"}},
    1610612748: {"abbrev": "MIA", "name": "Miami Heat", "conference": "East", "division": "Southeast", "colors": {"primary": "#98002E", "secondary": "#F9A01B"}},
    1610612749: {"abbrev": "MIL", "name": "Milwaukee Bucks", "conference": "East", "division": "Central", "colors": {"primary": "#00471B", "secondary": "#EEE1C6"}},
    1610612750: {"abbrev": "MIN", "name": "Minnesota Timberwolves", "conference": "West", "division": "Northwest", "colors": {"primary": "#0C2340", "secondary": "#236192"}},
    1610612740: {"abbrev": "NOP", "name": "New Orleans Pelicans", "conference": "West", "division": "Southwest", "colors": {"primary": "#0C2340", "secondary": "#C8102E"}},
    1610612752: {"abbrev": "NYK", "name": "New York Knicks", "conference": "East", "division": "Atlantic", "colors": {"primary": "#006BB6", "secondary": "#F58426"}},
    1610612760: {"abbrev": "OKC", "name": "Oklahoma City Thunder", "conference": "West", "division": "Northwest", "colors": {"primary": "#007AC1", "secondary": "#EF3B24"}},
    1610612753: {"abbrev": "ORL", "name": "Orlando Magic", "conference": "East", "division": "Southeast", "colors": {"primary": "#0077C0", "secondary": "#C4CED4"}},
    1610612755: {"abbrev": "PHI", "name": "Philadelphia 76ers", "conference": "East", "division": "Atlantic", "colors": {"primary": "#006BB6", "secondary": "#ED174C"}},
    1610612756: {"abbrev": "PHX", "name": "Phoenix Suns", "conference": "West", "division": "Pacific", "colors": {"primary": "#1D1160", "secondary": "#E56020"}},
    1610612757: {"abbrev": "POR", "name": "Portland Trail Blazers", "conference": "West", "division": "Northwest", "colors": {"primary": "#E03A3E", "secondary": "#000000"}},
    1610612758: {"abbrev": "SAC", "name": "Sacramento Kings", "conference": "West", "division": "Pacific", "colors": {"primary": "#5A2D81", "secondary": "#63727A"}},
    1610612759: {"abbrev": "SAS", "name": "San Antonio Spurs", "conference": "West", "division": "Southwest", "colors": {"primary": "#C4CED4", "secondary": "#000000"}},
    1610612761: {"abbrev": "TOR", "name": "Toronto Raptors", "conference": "East", "division": "Atlantic", "colors": {"primary": "#CE1141", "secondary": "#000000"}},
    1610612762: {"abbrev": "UTA", "name": "Utah Jazz", "conference": "West", "division": "Northwest", "colors": {"primary": "#002B5C", "secondary": "#00471B"}},
    1610612764: {"abbrev": "WAS", "name": "Washington Wizards", "conference": "East", "division": "Southeast", "colors": {"primary": "#002B5C", "secondary": "#E31837"}},
}


def load_json(filepath: str) -> Any:
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def clean_nan(obj: Any) -> Any:
    """Recursively replaces NaN and Infinity with None for strictly compliant JSON."""
    if isinstance(obj, float):
        if obj != obj or obj == float("inf") or obj == float("-inf"):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    return obj


def write_json(filepath: str, data: Any) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    temp_path = f"{filepath}.tmp"
    clean_data = clean_nan(data)
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, filepath)


# ---------------------------------------------------------------------------
# Team Synthesis Engine
# ---------------------------------------------------------------------------
def synthesize_teams(season: str) -> List[Dict[str, Any]]:
    team_def = load_json(os.path.join("data", "processed", "features", f"team_defense_{season}.json")).get("teams", {})
    team_elo = load_json(os.path.join("data", "processed", "features", f"team_elo_{season}.json")).get("teams", {})
    team_pm = load_json(os.path.join("data", "processed", "features", f"playmaking_and_roles_{season}.json")).get("teams", {})
    team_sp = load_json(os.path.join("data", "processed", "features", f"spatial_hot_cold_{season}.json")).get("teams", {})
    team_gf = load_json(os.path.join("data", "processed", "features", f"game_flow_{season}.json")).get("teams", {})
    team_shot = load_json(os.path.join("data", "processed", "features", f"shot_features_{season}.json")).get("teams", {})
    team_ast_net = load_json(os.path.join("data", "processed", "features", f"assist_network_{season}.json")).get("teams", {})
    team_mom = load_json(os.path.join("data", "processed", "features", f"momentum_and_runs_{season}.json")).get("teams", {})
    team_hustle = load_json(os.path.join("data", "processed", "features", f"hustle_and_lineups_{season}.json")).get("teams", {})

    if not team_def:
        logger.error(f"Missing team defense data for {season}.")
        return []

    team_records = []
    for tid_str, t_def in team_def.items():
        tid = int(tid_str)
        t_elo = team_elo.get(tid_str, {})
        t_pm = team_pm.get(tid_str, {})
        t_sp = team_sp.get(tid_str, {})
        t_gf = team_gf.get(tid_str, {})
        t_st = team_shot.get(tid_str, {})
        t_net = team_ast_net.get(tid_str, {})
        t_m = team_mom.get(tid_str, {})
        t_h = team_hustle.get(tid_str, {})

        meta = NBA_TEAM_METADATA.get(tid, {
            "abbrev": t_def["team_abbrev"],
            "name": t_def["team_name"],
            "conference": "East",
            "division": "Atlantic",
            "colors": {"primary": "#000000", "secondary": "#FFFFFF"}
        })

        record = {
            "team_id": tid,
            "team_name": t_def["team_name"],
            "team_abbrev": t_def["team_abbrev"],
            "conference": meta["conference"],
            "division": meta["division"],
            "logo_url": f"https://cdn.nba.com/logos/nba/{tid}/global/L/logo.svg",
            "colors": meta["colors"],
            "games_played": t_def["games_played"],
            "pace": t_def["pace"],
            "ratings": t_def["ratings"],
            "elo_ratings": {
                "offensive_elo": t_elo.get("offensive_elo", 1000.0),
                "defensive_elo": t_elo.get("defensive_elo", 1000.0),
                "overall_elo": t_elo.get("overall_elo", 1000.0),
            },
            "four_factors": {
                "offensive_effective_fg_pct": t_st.get("actual_efg"),
                "offensive_shot_quality_xefg": t_st.get("shot_quality_xefg"),
                "smoe_per_100": t_st.get("smoe_per_100"),
                "shot_density_bins": t_st.get("density_bins", []),
                "defensive_four_factors": t_def.get("defensive_four_factors", {}),
            },
            "defensive_spatial_suppression": {
                "opp_shot_quality_allowed_xefga": t_def.get("defensive_shot_quality", {}).get("opp_shot_quality_allowed_xefga"),
                "defensive_finishing_delta": t_def.get("defensive_shot_quality", {}).get("defensive_finishing_delta"),
                "opponent_paint_funnel_rate": t_sp.get("opponent_paint_funnel_rate"),
                "rim_denial_efficiency": t_sp.get("rim_denial_efficiency"),
                "defensive_hot_cold_allowed": t_sp.get("defensive_hot_cold_allowed", {}),
            },
            "playmaking_and_chemistry": {
                "helicentrism_index": t_pm.get("playmaking_centrality", {}).get("helicentrism_index"),
                "assist_gini_coefficient": t_pm.get("playmaking_centrality", {}).get("assist_gini_coefficient"),
                "playmaking_depth_share": t_pm.get("playmaking_centrality", {}).get("playmaking_depth_share"),
                "network_reciprocity_index": t_net.get("network_reciprocity_index"),
                "top_synergy_duos": t_net.get("top_synergy_duos", []),
            },
            "momentum_and_runs": t_m.get("scoring_runs", {}),
            "lead_volatility": t_m.get("lead_volatility", {}),
            "hustle_and_rotations": {
                "team_hustle_per_game": t_h.get("team_hustle_per_game", {}),
                "lineup_rotation_profiles": t_h.get("lineup_rotation_profiles", {}),
            },
            "possession_ledger": t_def.get("possession_ledger", {}),
            "game_flow_and_rest": {
                "quarter_splits": t_gf.get("quarter_splits", {}),
                "rest_advantage_profile": t_gf.get("rest_advantage_profile", {}),
            },
            "scheme_profile": t_def.get("scheme_profile", {}),
        }
        team_records.append(record)

    # 30-Team Comparative Percentiles
    if len(team_records) >= 10:
        df = pd.json_normalize(team_records)
        rank_cols = {
            "ratings.net_rating": ("pct_net_rating", True),
            "ratings.offensive_rating": ("pct_ortg", True),
            "ratings.defensive_rating": ("pct_drtg", False),
            "elo_ratings.overall_elo": ("pct_overall_elo", True),
            "elo_ratings.offensive_elo": ("pct_off_elo", True),
            "elo_ratings.defensive_elo": ("pct_def_elo", True),
            "possession_ledger.possession_margin_per_game": ("pct_poss_margin", True),
            "momentum_and_runs.net_run_margin_per_game": ("pct_run_margin", True),
            "defensive_spatial_suppression.rim_denial_efficiency": ("pct_rim_denial", True),
        }

        for col, (new_col, asc) in rank_cols.items():
            if col in df.columns:
                df[new_col] = (df[col].rank(ascending=asc, pct=True) * 100.0).round(1)

        pct_map = df.set_index("team_id")[[v[0] for v in rank_cols.values() if v[0] in df.columns]].to_dict(orient="index")

        for tm in team_records:
            tid = tm["team_id"]
            ranks = pct_map.get(tid, {})
            tm["percentile_ranks"] = {
                "net_rating": ranks.get("pct_net_rating"),
                "offensive_rating": ranks.get("pct_ortg"),
                "defensive_rating": ranks.get("pct_drtg"),
                "overall_elo": ranks.get("pct_overall_elo"),
                "offensive_elo": ranks.get("pct_off_elo"),
                "defensive_elo": ranks.get("pct_def_elo"),
                "possession_margin": ranks.get("pct_poss_margin"),
                "net_run_margin": ranks.get("pct_run_margin"),
                "rim_denial": ranks.get("pct_rim_denial"),
            }

    return team_records


# ---------------------------------------------------------------------------
# Player Synthesis Engine (with Dual Percentiles & Archetypes)
# ---------------------------------------------------------------------------
def synthesize_players(season: str) -> List[Dict[str, Any]]:
    player_logs = load_json(os.path.join("data", "raw", "game_logs", f"player_{season}.json"))
    team_logs = load_json(os.path.join("data", "raw", "game_logs", f"team_{season}.json"))
    shot_data = load_json(os.path.join("data", "processed", "features", f"shot_features_{season}.json")).get("players", {})
    context_data = load_json(os.path.join("data", "processed", "features", f"player_context_{season}.json")).get("players", {})
    pm_data = load_json(os.path.join("data", "processed", "features", f"playmaking_and_roles_{season}.json")).get("players", {})
    sp_data = load_json(os.path.join("data", "processed", "features", f"spatial_hot_cold_{season}.json")).get("players", {})
    gf_data = load_json(os.path.join("data", "processed", "features", f"game_flow_{season}.json")).get("players", {})
    ast_net_data = load_json(os.path.join("data", "processed", "features", f"assist_network_{season}.json")).get("players", {})
    epm_data = load_json(os.path.join("data", "processed", "features", f"effective_plus_minus_{season}.json")).get("players", {})
    hustle_data = load_json(os.path.join("data", "processed", "features", f"hustle_and_lineups_{season}.json")).get("players", {})
    archetype_data = load_json(os.path.join("data", "processed", "features", f"archetypes_{season}.json")).get("players", {})
    bios = {int(b["PLAYER_ID"]): b for b in load_json(os.path.join("data", "raw", "player_bios", f"{season}.json"))}

    if not player_logs or not team_logs:
        return []

    df_players = pd.DataFrame(player_logs)
    df_teams = pd.DataFrame(team_logs)

    team_agg = df_teams.groupby("TEAM_ID").agg(
        min=("MIN", "sum"),
        pts=("PTS", "sum"),
        fga=("FGA", "sum"),
        fta=("FTA", "sum"),
        oreb=("OREB", "sum"),
        tov=("TOV", "sum"),
    ).reset_index()
    team_agg["possessions"] = 0.96 * (team_agg["fga"] + 0.44 * team_agg["fta"] - team_agg["oreb"] + team_agg["tov"])
    team_map = team_agg.set_index("TEAM_ID").to_dict(orient="index")

    player_agg = df_players.groupby("PLAYER_ID").agg(
        player_name=("PLAYER_NAME", "first"),
        team_id=("TEAM_ID", "last"),
        team_abbrev=("TEAM_ABBREVIATION", "last"),
        games=("GAME_ID", "nunique"),
        min=("MIN", "sum"),
        pts=("PTS", "sum"),
        fga=("FGA", "sum"),
        fgm=("FGM", "sum"),
        fg3a=("FG3A", "sum"),
        fg3m=("FG3M", "sum"),
        fta=("FTA", "sum"),
        ftm=("FTM", "sum"),
        oreb=("OREB", "sum"),
        dreb=("DREB", "sum"),
        reb=("REB", "sum"),
        ast=("AST", "sum"),
        stl=("STL", "sum"),
        blk=("BLK", "sum"),
        tov=("TOV", "sum"),
        pf=("PF", "sum"),
    ).reset_index()

    max_games = int(player_agg["games"].max()) if not player_agg.empty else 1

    player_records = []
    for _, row in player_agg.iterrows():
        pid = int(row["PLAYER_ID"])
        pid_str = str(pid)
        tid = int(row["team_id"])
        tm = team_map.get(tid)

        if not tm or row["min"] == 0:
            continue

        p_min = float(row["min"])
        tm_min_per_player = tm["min"] / 5.0
        player_poss = (tm["possessions"] * (p_min / tm_min_per_player)) if tm_min_per_player > 0 else 0.0

        denom_usg = p_min * (tm["fga"] + 0.44 * tm["fta"] + tm["tov"])
        nom_usg = (row["fga"] + 0.44 * row["fta"] + row["tov"]) * tm_min_per_player
        usg_pct = (100.0 * nom_usg / denom_usg) if denom_usg > 0 else 0.0

        ts_denom = 2.0 * (row["fga"] + 0.44 * row["fta"])
        ts_pct = (row["pts"] / ts_denom) if ts_denom > 0 else None
        efg_pct = ((row["fgm"] + 0.5 * row["fg3m"]) / row["fga"]) if row["fga"] > 0 else None
        ast_tov = (row["ast"] / row["tov"]) if row["tov"] > 0 else float(row["ast"])

        poss_factor = (100.0 / player_poss) if player_poss > 0 else 0.0

        p_shot = shot_data.get(pid_str, {})
        p_ctx = context_data.get(pid_str, {})
        p_pm = pm_data.get(pid_str, {})
        p_sp = sp_data.get(pid_str, {})
        p_gf = gf_data.get(pid_str, {})
        p_net = ast_net_data.get(pid_str, {})
        p_epm = epm_data.get(pid_str, {})
        p_hst = hustle_data.get(pid_str, {})
        p_arch = archetype_data.get(pid_str, {})
        bio = bios.get(pid, {})

        pos = p_pm.get("position") or bio.get("POSITION") or "F"
        if pos.startswith("G"):
            pos_group = "Guard"
        elif pos.startswith("C"):
            pos_group = "Center"
        else:
            pos_group = "Forward"

        record = {
            "player_id": pid,
            "player_name": row["player_name"],
            "team_id": tid,
            "team_abbrev": row["team_abbrev"],
            "position": pos_group,
            "headshot_url": f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png",
            "bio": {
                "raw_position": pos,
                "height": bio.get("PLAYER_HEIGHT"),
                "weight": bio.get("PLAYER_WEIGHT"),
                "age": bio.get("AGE"),
            },
            "games_played": int(row["games"]),
            "minutes_total": round(p_min, 1),
            "minutes_per_game": round(p_min / row["games"], 1),
            "usage_pct": round(usg_pct, 2),
            "true_shooting_pct": round(ts_pct, 4) if ts_pct is not None else None,
            "effective_fg_pct": round(efg_pct, 4) if efg_pct is not None else None,
            "ast_tov_ratio": round(ast_tov, 2),
            "per_100_possessions": {
                "points": round(row["pts"] * poss_factor, 1),
                "rebounds": round(row["reb"] * poss_factor, 1),
                "assists": round(row["ast"] * poss_factor, 1),
                "turnovers": round(row["tov"] * poss_factor, 1),
                "steals": round(row["stl"] * poss_factor, 1),
                "blocks": round(row["blk"] * poss_factor, 1),
            },
            "effective_plus_minus": p_epm.get("epm_ratings", {}),
            "relative_plus_minus": p_epm.get("relative_plus_minus", {}),
            "oliver_floor_rates": p_pm.get("oliver_floor_rates", {}),
            "hustle_tracking": p_hst.get("hustle_stats", {}),
            "archetype": p_arch.get("archetype"),
            "similar_players": p_arch.get("similar_players", []),
            "assist_network_profile": {
                "passer_profile": p_net.get("passer_profile", {}),
                "finisher_profile": p_net.get("finisher_profile", {}),
            },
            "shot_making_and_creation": {
                "fga": int(row["fga"]),
                "shot_quality_xefg": p_shot.get("shot_quality_xefg"),
                "smoe_total": p_shot.get("smoe_total"),
                "smoe_per_100": p_shot.get("smoe_per_100"),
                "creation_profile": p_shot.get("creation_profile", {}),
                "rim_pressure": p_shot.get("rim_pressure", {}),
                "corner_3_specialist_premium": p_sp.get("corner_3_specialist_premium"),
                "hot_cold_zones": p_sp.get("hot_cold_zones", {}),
                "shot_density_bins": p_shot.get("density_bins", []),
            },
            "game_flow_and_clutch": {
                "quarter_splits": p_gf.get("quarter_splits", {}),
                "clutch_execution": p_gf.get("clutch_execution", {}),
            },
            "consistency_and_schedule": {
                "volatility_profile": p_ctx.get("volatility_profile", {}),
                "schedule_rest_splits": p_ctx.get("schedule_rest_splits", {}),
                "venue_splits": p_ctx.get("venue_splits", {}),
            },
        }
        player_records.append(record)

    # Dual Percentile Engine
    min_fga = max(5, min(50, max_games * 4))
    min_minutes = max(10, min(100, max_games * 8))

    df_rec = pd.json_normalize(player_records)
    qualified = df_rec[
        (df_rec["shot_making_and_creation.fga"] >= min_fga)
        & (df_rec["minutes_total"] >= min_minutes)
    ].copy()

    metrics_to_rank = {
        "true_shooting_pct": "pct_ts",
        "usage_pct": "pct_usage",
        "ast_tov_ratio": "pct_ast_tov",
        "oliver_floor_rates.true_ast_pct": "pct_true_ast",
        "oliver_floor_rates.true_dreb_pct": "pct_true_dreb",
        "oliver_floor_rates.stock_rate_per_100": "pct_stock_rate",
        "effective_plus_minus.net_epm": "pct_net_epm",
        "relative_plus_minus.relative_plus_minus": "pct_relative_pm",
        "hustle_tracking.deflections_per_100": "pct_deflections",
        "hustle_tracking.screen_assist_pts_per_100": "pct_screen_pts",
        "shot_making_and_creation.smoe_per_100": "pct_smoe",
        "shot_making_and_creation.shot_quality_xefg": "pct_shot_quality",
        "shot_making_and_creation.creation_profile.self_creation_rate": "pct_self_creation",
        "shot_making_and_creation.rim_pressure.rim_pressure_rate": "pct_rim_pressure",
        "per_100_possessions.points": "pct_pts_100",
    }

    # 1. League-Wide Percentiles
    for col, new_col in metrics_to_rank.items():
        if col in qualified.columns:
            qualified[f"league_{new_col}"] = (qualified[col].rank(pct=True) * 100.0).round(1)

    # 2. Positional Peer Percentiles
    pos_metric_map = {
        "true_shooting_pct": "pos_pct_ts",
        "effective_plus_minus.net_epm": "pos_pct_net_epm",
        "shot_making_and_creation.rim_pressure.rim_pressure_rate": "pos_pct_rim_pressure",
        "oliver_floor_rates.true_ast_pct": "pos_pct_playmaking_load",
        "oliver_floor_rates.true_dreb_pct": "pos_pct_rebound_dominance",
    }

    pos_mean_ts = qualified.groupby("position")["true_shooting_pct"].transform("mean")
    qualified["calc_pos_usg_eff_ratio"] = (qualified["true_shooting_pct"] / pos_mean_ts) * qualified["usage_pct"]
    pos_metric_map["calc_pos_usg_eff_ratio"] = "pos_pct_usg_to_eff"

    for col, new_col in pos_metric_map.items():
        if col in qualified.columns:
            qualified[new_col] = (
                qualified.groupby("position")[col].rank(pct=True) * 100.0
            ).round(1)

    all_pct_cols = [f"league_{c}" for c in metrics_to_rank.values()] + list(pos_metric_map.values())
    pct_map = qualified.set_index("player_id")[[c for c in all_pct_cols if c in qualified.columns]].to_dict(orient="index")

    for p in player_records:
        pid = p["player_id"]
        if pid in pct_map:
            ranks = pct_map[pid]
            p["percentile_ranks"] = {
                "league_wide": {
                    "true_shooting": ranks.get("league_pct_ts"),
                    "usage": ranks.get("league_pct_usage"),
                    "ast_tov_ratio": ranks.get("league_pct_ast_tov"),
                    "true_ast_pct": ranks.get("league_pct_true_ast"),
                    "true_dreb_pct": ranks.get("league_pct_true_dreb"),
                    "stock_rate": ranks.get("league_pct_stock_rate"),
                    "net_epm": ranks.get("league_pct_net_epm"),
                    "relative_plus_minus": ranks.get("league_pct_relative_pm"),
                    "deflections": ranks.get("league_pct_deflections"),
                    "screen_assist_points": ranks.get("league_pct_screen_pts"),
                    "smoe_per_100": ranks.get("league_pct_smoe"),
                    "shot_quality": ranks.get("league_pct_shot_quality"),
                    "self_creation_rate": ranks.get("league_pct_self_creation"),
                    "rim_pressure_rate": ranks.get("league_pct_rim_pressure"),
                    "points_per_100": ranks.get("league_pct_pts_100"),
                },
                "positional_peer": {
                    "position_group": p["position"],
                    "true_shooting": ranks.get("pos_pct_ts"),
                    "net_epm": ranks.get("pos_pct_net_epm"),
                    "rim_pressure": ranks.get("pos_pct_rim_pressure"),
                    "playmaking_load": ranks.get("pos_pct_playmaking_load"),
                    "rebound_dominance": ranks.get("pos_pct_rebound_dominance"),
                    "usage_to_efficiency_ratio": ranks.get("pos_pct_usg_to_eff"),
                },
            }
        else:
            p["percentile_ranks"] = {
                "league_wide": {k: None for k in [
                    "true_shooting", "usage", "ast_tov_ratio", "true_ast_pct",
                    "true_dreb_pct", "stock_rate", "net_epm", "relative_plus_minus",
                    "deflections", "screen_assist_points", "smoe_per_100",
                    "shot_quality", "self_creation_rate", "rim_pressure_rate", "points_per_100"
                ]},
                "positional_peer": {
                    "position_group": p["position"],
                    "true_shooting": None,
                    "net_epm": None,
                    "rim_pressure": None,
                    "playmaking_load": None,
                    "rebound_dominance": None,
                    "usage_to_efficiency_ratio": None,
                },
            }

    return player_records


# ---------------------------------------------------------------------------
# Tiered Partitioning Generators (Tiers 1, 2, 3)
# ---------------------------------------------------------------------------
def generate_player_index(players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tier 1: Lightweight Directory Index (~75 KB)."""
    index = []
    for p in players:
        epm = p.get("effective_plus_minus", {})
        pct_lw = p.get("percentile_ranks", {}).get("league_wide", {})
        arch = p.get("archetype") or {}

        index.append({
            "player_id": p["player_id"],
            "player_name": p["player_name"],
            "team_id": p["team_id"],
            "team_abbrev": p["team_abbrev"],
            "position": p["position"],
            "headshot_url": p["headshot_url"],
            "games_played": p["games_played"],
            "minutes_per_game": p["minutes_per_game"],
            "usage_pct": p["usage_pct"],
            "true_shooting_pct": p["true_shooting_pct"],
            "effective_fg_pct": p["effective_fg_pct"],
            "pts_per_100": p["per_100_possessions"]["points"],
            "ast_per_100": p["per_100_possessions"]["assists"],
            "reb_per_100": p["per_100_possessions"]["rebounds"],
            "net_epm": epm.get("net_epm"),
            "offensive_epm": epm.get("offensive_epm"),
            "defensive_epm": epm.get("defensive_epm"),
            "archetype": arch.get("offensive_role"),
            "percentile_ranks": {
                "net_epm": pct_lw.get("net_epm"),
                "true_shooting": pct_lw.get("true_shooting"),
                "rim_pressure": pct_lw.get("rim_pressure_rate"),
                "self_creation": pct_lw.get("self_creation_rate"),
            },
        })
    return index


def generate_team_index(teams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tier 1: Lightweight Team Directory Index (~10 KB)."""
    index = []
    for t in teams:
        pct = t.get("percentile_ranks", {})
        index.append({
            "team_id": t["team_id"],
            "team_name": t["team_name"],
            "team_abbrev": t["team_abbrev"],
            "conference": t["conference"],
            "division": t["division"],
            "logo_url": t["logo_url"],
            "colors": t["colors"],
            "games_played": t["games_played"],
            "pace": t["pace"],
            "offensive_rating": t["ratings"]["offensive_rating"],
            "defensive_rating": t["ratings"]["defensive_rating"],
            "net_rating": t["ratings"]["net_rating"],
            "overall_elo": t["elo_ratings"]["overall_elo"],
            "offensive_elo": t["elo_ratings"]["offensive_elo"],
            "defensive_elo": t["elo_ratings"]["defensive_elo"],
            "percentile_ranks": {
                "net_rating": pct.get("net_rating"),
                "overall_elo": pct.get("overall_elo"),
                "rim_denial": pct.get("rim_denial"),
            },
        })
    return index


def generate_leaderboards(season: str, players: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Tier 3: Categorical Pre-sorted Leaderboards (~35 KB)."""
    # Filter qualified players (having net_epm rank)
    qualified = [p for p in players if p.get("percentile_ranks", {}).get("league_wide", {}).get("net_epm") is not None]
    if len(qualified) < 10:
        qualified = players

    def build_top_list(key_func, top_n=20, reverse=True):
        sorted_p = sorted(qualified, key=key_func, reverse=reverse)[:top_n]
        return [
            {
                "rank": idx + 1,
                "player_id": p["player_id"],
                "player_name": p["player_name"],
                "team_abbrev": p["team_abbrev"],
                "position": p["position"],
                "headshot_url": p["headshot_url"],
                "value": key_func(p),
            }
            for idx, p in enumerate(sorted_p)
        ]

    return {
        "season": season,
        "categories": {
            "net_epm": build_top_list(lambda p: p["effective_plus_minus"].get("net_epm") or -99.0),
            "offensive_epm": build_top_list(lambda p: p["effective_plus_minus"].get("offensive_epm") or -99.0),
            "defensive_epm": build_top_list(lambda p: p["effective_plus_minus"].get("defensive_epm") or -99.0),
            "self_creation_rate": build_top_list(lambda p: p["shot_making_and_creation"].get("creation_profile", {}).get("self_creation_rate") or 0.0),
            "rim_pressure_rate": build_top_list(lambda p: p["shot_making_and_creation"].get("rim_pressure", {}).get("rim_pressure_rate") or 0.0),
            "smoe_per_100": build_top_list(lambda p: p["shot_making_and_creation"].get("smoe_per_100") or -99.0),
            "true_ast_pct": build_top_list(lambda p: p["oliver_floor_rates"].get("true_ast_pct") or 0.0),
            "deflections_per_100": build_top_list(lambda p: p["hustle_tracking"].get("deflections_per_100") or 0.0),
            "screen_assist_pts_per_100": build_top_list(lambda p: p["hustle_tracking"].get("screen_assist_pts_per_100") or 0.0),
            "true_shooting_pct": build_top_list(lambda p: p["true_shooting_pct"] or 0.0),
        },
    }


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("==================================================")
    logger.info("Synthesizing Full Production Analytics Stores (Tiered)")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Synthesizing Production Stores for Season: {season} ---")
        teams = synthesize_teams(season)
        players = synthesize_players(season)

        # 1. Full Catalog Legacy Files
        player_out = os.path.join("data", "analytics", f"players_{season}.json")
        team_out = os.path.join("data", "analytics", f"teams_{season}.json")
        write_json(player_out, players)
        write_json(team_out, teams)

        # 2. Tier 1: Directory Indexes
        p_index = generate_player_index(players)
        t_index = generate_team_index(teams)
        write_json(os.path.join("data", "analytics", f"players_index_{season}.json"), p_index)
        write_json(os.path.join("data", "analytics", f"teams_index_{season}.json"), t_index)

        # 3. Tier 2: Individual Entity Payloads
        for p in players:
            pid = p["player_id"]
            write_json(os.path.join("data", "analytics", "players", season, f"{pid}.json"), p)

        for t in teams:
            abbrev = t["team_abbrev"]
            write_json(os.path.join("data", "analytics", "teams", season, f"{abbrev}.json"), t)

        # 4. Tier 3: Pre-sorted Leaderboards
        l_boards = generate_leaderboards(season, players)
        write_json(os.path.join("data", "analytics", f"leaderboards_{season}.json"), l_boards)

        logger.info(f"Tier 1 Index: Exported {len(p_index)} players & {len(t_index)} teams.")
        logger.info(f"Tier 2 Granular: Exported {len(players)} player & {len(teams)} team JSONs.")
        logger.info(f"Tier 3 Leaderboards: Generated top 20 across 10 categories.")

    logger.info("==================================================")
    logger.info("Tiered Analytics Store synthesis complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()
