"""
scripts/features/archetypes.py
NBA Analytics Platform - Machine Learning Archetype & Player Similarity Engine

1. Categorizes players into modern functional NBA tactical archetypes:
   - Offensive: Heliocentric Creator, Primary Slasher, Shot-Creating Wing, 
                Movement/Spot-Up Shooter, Connector/Secondary Creator, 
                Pick-and-Pop Spacer, Roll-and-Cut Finisher, Playmaking Hub.
   - Defensive: Anchor Rim Protector, Point-of-Attack Disruptor, 
                Roaming Free Safety, Perimeter Chaser, Switch Defender.
2. Computes pairwise Cosine Similarity across standardized skill vectors
   to identify top 5 player comparisons ("Who does Player X play like?").
"""

import json
import logging
import math
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Archetypes")

SEASONS = ["2026-27", "2025-26"]


def load_json(filepath: str) -> Any:
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath: str, data: Any) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, filepath)


def parse_height_inches(h_str: Optional[str]) -> float:
    """Converts '6-9' or '6-11' to inches (81.0, 83.0)."""
    if not h_str or not isinstance(h_str, str) or "-" not in h_str:
        return 78.0  # ~6'6" league average default
    try:
        parts = h_str.strip().split("-")
        return float(parts[0]) * 12.0 + float(parts[1])
    except Exception:
        return 78.0


# ---------------------------------------------------------------------------
# Archetype Classification Engine
# ---------------------------------------------------------------------------
def classify_offensive_archetype(row: Dict[str, Any]) -> Tuple[str, str]:
    usg = row.get("usg_pct", 20.0)
    ast_pct = row.get("true_ast_pct", 15.0)
    sc_rate = row.get("self_creation_rate", 0.30)
    rim_rate = row.get("rim_pressure_rate", 0.25)
    three_rate = row.get("three_point_rate", 0.35)
    pos = row.get("position", "F")
    screen_pts = row.get("screen_pts_100", 0.0)

    # 1. Big Man Playmaking Hub (Jokic, Sabonis)
    if pos == "Center" and ast_pct >= 24.0:
        return (
            "Versatile Playmaking Hub",
            "Offensive anchor facilitating action from the high post and elbow with elite floor vision.",
        )

    # 2. Heliocentric Creator (Luka, Trae, Brunson)
    if usg >= 28.0 and ast_pct >= 28.0 and sc_rate >= 0.40:
        return (
            "Heliocentric Engine",
            "High-usage primary decision maker commanding the offense in pick-and-roll and isolation.",
        )

    # 3. Primary Slasher / Rim Punisher (Giannis, Ja, Zion)
    if usg >= 24.0 and rim_rate >= 0.42:
        return (
            "Primary Slasher",
            "Relentless downhill rim attacker generating high-percentage paint points and foul pressure.",
        )

    # 4. Shot-Creating Wing (Tatum, Booker, Edwards, DeRozan)
    if usg >= 23.0 and sc_rate >= 0.38:
        return (
            "Shot-Creating Wing",
            "Three-level scoring threat capable of generating efficient looks off the dribble.",
        )

    # 5. Pick-and-Pop Spacer (Porzingis, Markkanen, Brook Lopez)
    if pos in ["Center", "Forward"] and three_rate >= 0.42 and usg >= 18.0:
        return (
            "Pick-and-Pop Spacer",
            "Frontcourt perimeter sniper opening driving lanes by drawing opposing shot blockers to the arc.",
        )

    # 6. Roll-and-Cut Rim Finisher (Gobert, Capela, Gafford, Lively)
    if pos in ["Center", "Forward"] and rim_rate >= 0.55 and sc_rate <= 0.22:
        return (
            "Roll-and-Cut Rim Finisher",
            "Vertical spacing target converting lobs, cuts, and screen actions at the rim.",
        )

    # 7. Movement / Spot-Up Shooter (Curry, Hield, Robinson, Beasley)
    if three_rate >= 0.55 and sc_rate <= 0.30:
        return (
            "Movement / Spot-Up Shooter",
            "Lethal floor spacer stressing defensive shell coverages through continuous off-ball movement.",
        )

    # 8. Connector / Secondary Creator (White, Caruso, Conley)
    if ast_pct >= 18.0 and usg <= 22.0:
        return (
            "Connector / Secondary Playmaker",
            "High-IQ ball mover sustaining offensive flow through rapid swing passes and quick attacks.",
        )

    # Fallback
    if three_rate >= 0.40:
        return (
            "Floor Spacer",
            "Perimeter-oriented contributor maintaining spacing along the arc.",
        )
    return (
        "Slashing Role Player",
        "Opportunistic off-ball finisher attacking second-side rotations and offensive boards.",
    )


def classify_defensive_archetype(row: Dict[str, Any]) -> Tuple[str, str]:
    pos = row.get("position", "F")
    deflections = row.get("deflections_100", 2.0)
    dreb_pct = row.get("true_dreb_pct", 15.0)
    stock_rate = row.get("stock_rate", 2.0)
    depm = row.get("defensive_epm", 0.0)

    # 1. Anchor Rim Protector (Gobert, Davis, Wembanyama, Kessler)
    if pos == "Center" and (stock_rate >= 3.5 or (dreb_pct >= 22.0 and depm >= 0.5)):
        return (
            "Anchor Rim Protector",
            "Defensive linchpin defending the paint, deterring rim attempts, and cleaning the defensive glass.",
        )

    # 2. Point-of-Attack Disruptor (Caruso, Suggs, Dort, Holiday, White)
    if pos in ["Guard", "Forward"] and deflections >= 3.8:
        return (
            "Point-of-Attack Disruptor",
            "Aggressive perimeter defender generating deflections, blowing up screens, and forcing turnovers.",
        )

    # 3. Roaming Free Safety (Giannis, Mobley, Jaren Jackson Jr.)
    if pos in ["Forward", "Center"] and stock_rate >= 3.0 and depm >= 0.8:
        return (
            "Roaming Free Safety",
            "Weakside rim-protecting rover helping off non-shooters to erase paint scoring.",
        )

    # 4. Switchable Wing Defender
    if pos == "Forward" and depm >= 0.0:
        return (
            "Switchable Wing Defender",
            "Versatile multi-positional stopper capable of sliding feet on guards and holding ground on bigs.",
        )

    if pos == "Guard":
        return (
            "Perimeter Chaser",
            "Active guard navigating screen traffic and staying connected to movement shooters.",
        )

    return (
        "Positional Team Defender",
        "Solid system defender executing standard drop and rotation schemes.",
    )


# ---------------------------------------------------------------------------
# Similarity Engine (Cosine Similarity on Standardized Features)
# ---------------------------------------------------------------------------
def compute_player_similarities(
    players_df: pd.DataFrame,
    features_to_scale: List[str],
    top_n: int = 5,
) -> Dict[int, List[Dict[str, Any]]]:
    """
    Standardizes feature vectors and computes pairwise Cosine Similarity.
    Returns {player_id: [{player_id, player_name, similarity_score_pct, headshot_url}]}
    """
    if len(players_df) < 5:
        return {}

    sub_df = players_df.dropna(subset=features_to_scale).copy()
    if len(sub_df) < 5:
        sub_df = players_df.fillna(0).copy()

    # Z-score standardization: (X - mean) / std
    scaled_matrix = sub_df[features_to_scale].values
    means = np.mean(scaled_matrix, axis=0)
    stds = np.std(scaled_matrix, axis=0)
    stds[stds == 0] = 1.0  # avoid division by zero
    standardized = (scaled_matrix - means) / stds

    # L2 normalize rows for cosine similarity
    norms = np.linalg.norm(standardized, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized_matrix = standardized / norms

    # Pairwise Cosine Matrix: N x N
    cosine_sim = np.dot(normalized_matrix, normalized_matrix.T)

    player_ids = sub_df["player_id"].tolist()
    player_names = sub_df["player_name"].tolist()
    p_map = {pid: (name, sub_df["team_abbrev"].iloc[i]) for i, (pid, name) in enumerate(zip(player_ids, player_names))}

    similarity_results: Dict[int, List[Dict[str, Any]]] = {}

    for idx, pid in enumerate(player_ids):
        sim_scores = cosine_sim[idx]
        # Sort descending, excluding self
        ranked_indices = np.argsort(sim_scores)[::-1]
        top_matches = []

        for r_idx in ranked_indices:
            other_pid = player_ids[r_idx]
            if other_pid == pid:
                continue
            raw_score = float(sim_scores[r_idx])
            # Map [-1, 1] to percentage [0, 100]
            pct_score = round(max(0.0, min(100.0, ((raw_score + 1.0) / 2.0) * 100.0)), 1)
            other_name, other_team = p_map[other_pid]

            top_matches.append({
                "player_id": other_pid,
                "player_name": other_name,
                "team_abbrev": other_team,
                "similarity_score_pct": pct_score,
                "headshot_url": f"https://cdn.nba.com/headshots/nba/latest/1040x760/{other_pid}.png",
            })

            if len(top_matches) >= top_n:
                break

        similarity_results[pid] = top_matches

    return similarity_results


# ---------------------------------------------------------------------------
# Main Feature Assembly
# ---------------------------------------------------------------------------
def process_season_archetypes(season: str) -> Dict[str, Any]:
    player_logs_file = os.path.join("data", "raw", "game_logs", f"player_{season}.json")
    bio_file = os.path.join("data", "raw", "player_bios", f"{season}.json")
    shot_features_file = os.path.join("data", "processed", "features", f"shot_features_{season}.json")
    pm_file = os.path.join("data", "processed", "features", f"playmaking_and_roles_{season}.json")
    hustle_file = os.path.join("data", "processed", "features", f"hustle_and_lineups_{season}.json")
    epm_file = os.path.join("data", "processed", "features", f"effective_plus_minus_{season}.json")

    if not os.path.exists(player_logs_file):
        return {}

    logs = load_json(player_logs_file)
    bios = {int(b["PLAYER_ID"]): b for b in load_json(bio_file)} if os.path.exists(bio_file) else {}
    shot_data = load_json(shot_features_file).get("players", {})
    pm_data = load_json(pm_file).get("players", {})
    hustle_data = load_json(hustle_file).get("players", {})
    epm_data = load_json(epm_file).get("players", {})

    df = pd.DataFrame(logs)
    agg = df.groupby("PLAYER_ID").agg(
        player_name=("PLAYER_NAME", "first"),
        team_id=("TEAM_ID", "last"),
        team_abbrev=("TEAM_ABBREVIATION", "last"),
        games=("GAME_ID", "nunique"),
        min=("MIN", "sum"),
        pts=("PTS", "sum"),
        fga=("FGA", "sum"),
        fg3a=("FG3A", "sum"),
        fta=("FTA", "sum"),
        ast=("AST", "sum"),
        reb=("REB", "sum"),
        tov=("TOV", "sum"),
    ).reset_index()

    player_records = []
    for _, row in agg.iterrows():
        pid = int(row["PLAYER_ID"])
        pid_str = str(pid)
        p_min = float(row["min"])
        if p_min < 10.0:
            continue

        p_fga = float(row["fga"])
        p_fg3a = float(row["fg3a"])
        three_pt_rate = (p_fg3a / p_fga) if p_fga > 0 else 0.0

        bio = bios.get(pid, {})
        height_inches = parse_height_inches(bio.get("PLAYER_HEIGHT"))
        raw_pos = bio.get("POSITION", "F")
        if raw_pos.startswith("G"):
            pos_group = "Guard"
        elif raw_pos.startswith("C"):
            pos_group = "Center"
        else:
            pos_group = "Forward"

        p_shot = shot_data.get(pid_str, {})
        sc_rate = p_shot.get("creation_profile", {}).get("self_creation_rate", 0.25)
        rim_rate = p_shot.get("rim_pressure", {}).get("rim_pressure_rate", 0.25)
        smoe = p_shot.get("smoe_per_100", 0.0)

        p_pm = pm_data.get(pid_str, {})
        oliver = p_pm.get("oliver_floor_rates", {})
        ast_pct = oliver.get("true_ast_pct", 10.0)
        orb_pct = oliver.get("true_orb_pct", 5.0)
        dreb_pct = oliver.get("true_dreb_pct", 12.0)
        stock_rate = oliver.get("stock_rate_per_100", 2.0)

        p_hst = hustle_data.get(pid_str, {}).get("hustle_stats", {})
        deflections_100 = p_hst.get("deflections_per_100", 2.0)
        screen_pts_100 = p_hst.get("screen_assist_pts_per_100", 1.0)

        p_epm = epm_data.get(pid_str, {}).get("epm_ratings", {})
        o_epm = p_epm.get("offensive_epm", 0.0)
        d_epm = p_epm.get("defensive_epm", 0.0)
        net_epm = p_epm.get("net_epm", 0.0)

        # Approximate Usage %
        usg = ((row["fga"] + 0.44 * row["fta"] + row["tov"]) / (p_min / 48.0 * 100.0)) * 100.0 if p_min > 0 else 20.0
        usg = max(10.0, min(42.0, usg))

        player_records.append({
            "player_id": pid,
            "player_name": row["player_name"],
            "team_abbrev": row["team_abbrev"],
            "position": pos_group,
            "height_inches": height_inches,
            "games_played": int(row["games"]),
            "minutes_total": p_min,
            "usg_pct": round(usg, 1),
            "true_ast_pct": ast_pct,
            "true_orb_pct": orb_pct,
            "true_dreb_pct": dreb_pct,
            "stock_rate": stock_rate,
            "self_creation_rate": sc_rate,
            "rim_pressure_rate": rim_rate,
            "three_point_rate": round(three_pt_rate, 4),
            "deflections_100": deflections_100,
            "screen_pts_100": screen_pts_100,
            "offensive_epm": o_epm,
            "defensive_epm": d_epm,
            "net_epm": net_epm,
            "smoe_per_100": smoe,
        })

    df_players = pd.DataFrame(player_records)
    if df_players.empty:
        return {}

    # 1. Classify Archetypes
    classified_players: Dict[str, Any] = {}
    for r in player_records:
        off_role, off_desc = classify_offensive_archetype(r)
        def_role, def_desc = classify_defensive_archetype(r)
        pid_str = str(r["player_id"])

        classified_players[pid_str] = {
            "player_id": r["player_id"],
            "player_name": r["player_name"],
            "team_abbrev": r["team_abbrev"],
            "position": r["position"],
            "archetype": {
                "offensive_role": off_role,
                "offensive_description": off_desc,
                "defensive_role": def_role,
                "defensive_description": def_desc,
            },
        }

    # 2. Similarity Vectors
    features_to_scale = [
        "height_inches",
        "usg_pct",
        "self_creation_rate",
        "rim_pressure_rate",
        "three_point_rate",
        "true_ast_pct",
        "true_orb_pct",
        "true_dreb_pct",
        "stock_rate",
        "deflections_100",
        "net_epm",
    ]

    sim_map = compute_player_similarities(df_players, features_to_scale, top_n=5)

    for pid_str, p_obj in classified_players.items():
        pid = int(pid_str)
        p_obj["similar_players"] = sim_map.get(pid, [])

    return classified_players


def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: Archetype & Similarity Engine")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Computing Archetypes & Similarities for Season: {season} ---")
        profiles = process_season_archetypes(season)
        if not profiles:
            continue

        payload = {
            "season": season,
            "players_evaluated": len(profiles),
            "players": profiles,
        }

        out_path = os.path.join("data", "processed", "features", f"archetypes_{season}.json")
        write_json(out_path, payload)
        logger.info(f"Saved {len(profiles)} player archetype & similarity profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Archetype & Similarity modeling complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()
