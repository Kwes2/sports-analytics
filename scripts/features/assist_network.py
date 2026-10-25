"""
scripts/features/assist_network.py
NBA Analytics Platform - Play-by-Play Directed Assist Network & Chemistry Engine

Extracts directed passer-to-scorer pairs from PBP data using:
1. assist_person_id (if present)
2. Robust regex parser on event descriptions: '(PlayerName X AST)'
3. Game-level roster & bio name resolution

Computes:
- Top Synergy Duos & Chemistry Reciprocity Index
- Assisted Points Created & Points Per Assist (Pts/AST)
- 3PT vs Rim Assist Breakdown
- Top Assisted Targets & Primary Feeders
"""

import glob
import json
import logging
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AssistNetwork")

SEASONS = ["2026-27", "2025-26"]

# Regex matches '(Edgecombe 1 AST)', '(James 2 AST)', '(A. Nesmith 3 AST)'
AST_REGEX = re.compile(r"\(([A-Za-z0-9\.\'\-\s]+?)\s+\d+\s+AST\)", re.IGNORECASE)
RIM_KEYWORDS = ["dunk", "layup", "cutting", "alley oop", "putback", "tip", "hook"]


def load_json(filepath: str) -> Any:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath: str, data: Any) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, filepath)


def is_rim_shot(action_type: str, sub_type: str) -> bool:
    text = f"{action_type} {sub_type}".lower()
    return any(kw in text for kw in RIM_KEYWORDS)


def clean_name(name: str) -> str:
    """Normalize player names for matching."""
    return re.sub(r"[^a-zA-Z]", "", name).lower()


# ---------------------------------------------------------------------------
# Core Processing
# ---------------------------------------------------------------------------
def process_season_assist_network(season: str) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
    pbp_files = glob.glob(os.path.join("data", "raw", "pbp", season, "*.json"))
    if not pbp_files:
        logger.info(f"No PBP files found for season {season}.")
        return {}, {}, 0

    # 1. Load Bios for Name Lookup
    bio_file = os.path.join("data", "raw", "player_bios", f"{season}.json")
    id_to_full_name: Dict[int, str] = {}
    team_last_name_to_id: Dict[Tuple[int, str], int] = {}

    if os.path.exists(bio_file):
        for b in load_json(bio_file):
            pid = int(b["PLAYER_ID"])
            full_name = b["PLAYER_NAME"]
            tid = int(b.get("TEAM_ID", 0))
            id_to_full_name[pid] = full_name

            # Last name mapping
            parts = full_name.split()
            last_name = parts[-1] if parts else full_name
            team_last_name_to_id[(tid, clean_name(last_name))] = pid
            team_last_name_to_id[(tid, clean_name(full_name))] = pid

    # 2. Graph Accumulators
    team_edges: Dict[int, Dict[Tuple[int, int], Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(lambda: {"count": 0, "points": 0, "3pt": 0, "rim": 0, "mid": 0, "passer_name": "", "scorer_name": ""})
    )
    passer_stats: Dict[int, Dict[str, Any]] = defaultdict(
        lambda: {"name": "", "team_id": 0, "total_ast": 0, "pts_created": 0, "3pt": 0, "rim": 0, "mid": 0, "targets": defaultdict(int)}
    )
    finisher_stats: Dict[int, Dict[str, Any]] = defaultdict(
        lambda: {"name": "", "team_id": 0, "total_feeds": 0, "pts_from_ast": 0, "feeders": defaultdict(int)}
    )

    total_assists_found = 0

    for filepath in pbp_files:
        events = load_json(filepath)
        if not events:
            continue

        # Build game-level lookup from events: (team_id, last_name) -> person_id
        game_player_map: Dict[Tuple[int, str], int] = {}
        game_id_to_name: Dict[int, str] = {}

        for ev in events:
            pid = ev.get("person_id")
            pname = ev.get("player_name")
            tid = ev.get("team_id")
            if pid and pname and tid:
                pid = int(pid)
                tid = int(tid)
                game_id_to_name[pid] = pname
                game_player_map[(tid, clean_name(pname))] = pid

        # Scan events for assists
        for ev in events:
            scorer_id = ev.get("person_id")
            team_id = ev.get("team_id")
            desc = ev.get("description", "") or ""

            if not scorer_id or not team_id:
                continue

            scorer_id = int(scorer_id)
            team_id = int(team_id)

            # Determine Assister:
            # Method A: Direct assist_person_id
            assister_id = ev.get("assist_person_id")
            assister_name = ev.get("assist_player_name")

            # Method B: Regex extraction from description
            if not assister_id:
                match = AST_REGEX.search(desc)
                if match:
                    raw_ast_name = match.group(1).strip()
                    c_name = clean_name(raw_ast_name)
                    # Lookup in game map first, then bio map
                    assister_id = game_player_map.get((team_id, c_name)) or team_last_name_to_id.get((team_id, c_name))
                    assister_name = raw_ast_name

            if not assister_id or int(assister_id) == scorer_id:
                continue

            assister_id = int(assister_id)

            # Shot values
            action_type = str(ev.get("action_type", "")).lower()
            sub_type = str(ev.get("sub_type", "")).lower()
            pts = int(ev.get("points_total", 0))

            is_3p = 1 if ("3pt" in desc.lower() or "3pt" in action_type or "3pt" in sub_type) else 0
            if is_3p:
                shot_pts = 3
            else:
                shot_pts = 2

            is_rim = 1 if (not is_3p and is_rim_shot(action_type, sub_type)) else 0
            is_mid = 1 if (not is_3p and not is_rim) else 0

            # Name formatting
            p_scorer_name = id_to_full_name.get(scorer_id) or game_id_to_name.get(scorer_id) or str(ev.get("player_name", scorer_id))
            p_passer_name = id_to_full_name.get(assister_id) or game_id_to_name.get(assister_id) or str(assister_name or assister_id)

            total_assists_found += 1

            # 1. Team Edge
            edge = team_edges[team_id][(assister_id, scorer_id)]
            edge["count"] += 1
            edge["points"] += shot_pts
            edge["3pt"] += is_3p
            edge["rim"] += is_rim
            edge["mid"] += is_mid
            edge["passer_name"] = p_passer_name
            edge["scorer_name"] = p_scorer_name

            # 2. Passer Stats
            p_data = passer_stats[assister_id]
            p_data["name"] = p_passer_name
            p_data["team_id"] = team_id
            p_data["total_ast"] += 1
            p_data["pts_created"] += shot_pts
            p_data["3pt"] += is_3p
            p_data["rim"] += is_rim
            p_data["mid"] += is_mid
            p_data["targets"][scorer_id] += 1

            # 3. Finisher Stats
            f_data = finisher_stats[scorer_id]
            f_data["name"] = p_scorer_name
            f_data["team_id"] = team_id
            f_data["total_feeds"] += 1
            f_data["pts_from_ast"] += shot_pts
            f_data["feeders"][assister_id] += 1

    logger.info(
        f"Season {season}: Extracted {total_assists_found:,} assisted baskets from {len(pbp_files)} games."
    )

    # -----------------------------------------------------------------------
    # Team Network Compilation
    # -----------------------------------------------------------------------
    team_results = {}
    for tid, edges in team_edges.items():
        total_team_ast = sum(e["count"] for e in edges.values())
        if total_team_ast == 0:
            continue

        sorted_pairs = sorted(edges.items(), key=lambda x: x[1]["count"], reverse=True)
        top_synergy = []
        for (p_id, s_id), meta in sorted_pairs[:8]:
            top_synergy.append({
                "passer_id": p_id,
                "passer_name": meta["passer_name"],
                "scorer_id": s_id,
                "scorer_name": meta["scorer_name"],
                "assists_count": meta["count"],
                "points_created": meta["points"],
                "three_pt_assists": meta["3pt"],
                "rim_assists": meta["rim"],
                "share_of_team_assists": round(meta["count"] / total_team_ast, 4),
            })

        # Reciprocity: 2 * sum(min(A->B, B->A)) / Total Assists
        mutual_ast_sum = 0
        seen_pairs = set()
        for (u, v), meta in edges.items():
            pair_key = tuple(sorted([u, v]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            forward_count = edges.get((u, v), {}).get("count", 0)
            reverse_count = edges.get((v, u), {}).get("count", 0)
            mutual_ast_sum += min(forward_count, reverse_count)

        reciprocity = (2.0 * mutual_ast_sum) / total_team_ast if total_team_ast > 0 else 0.0

        team_results[str(tid)] = {
            "team_id": tid,
            "total_pbp_assists_evaluated": total_team_ast,
            "network_reciprocity_index": round(reciprocity, 4),
            "top_synergy_duos": top_synergy,
        }

    # -----------------------------------------------------------------------
    # Player Network Compilation
    # -----------------------------------------------------------------------
    player_results = {}
    all_player_ids = set(passer_stats.keys()).union(set(finisher_stats.keys()))

    for pid in all_player_ids:
        p_data = passer_stats.get(pid, {})
        f_data = finisher_stats.get(pid, {})

        p_name = p_data.get("name") or f_data.get("name") or id_to_full_name.get(pid, f"Player {pid}")
        tid = p_data.get("team_id") or f_data.get("team_id") or 0

        tot_ast = p_data.get("total_ast", 0)
        pts_created = p_data.get("pts_created", 0)
        pts_per_ast = (pts_created / tot_ast) if tot_ast > 0 else None
        three_share = (p_data.get("3pt", 0) / tot_ast) if tot_ast > 0 else None
        rim_share = (p_data.get("rim", 0) / tot_ast) if tot_ast > 0 else None

        # Top 3 assisted targets
        targets = p_data.get("targets", {})
        sorted_targets = sorted(targets.items(), key=lambda x: x[1], reverse=True)[:3]
        top_targets = [
            {
                "target_id": t_id,
                "target_name": id_to_full_name.get(t_id, f"Player {t_id}"),
                "assists_received": count,
            }
            for t_id, count in sorted_targets
        ]

        # Top 3 primary feeders
        feeders = f_data.get("feeders", {})
        sorted_feeders = sorted(feeders.items(), key=lambda x: x[1], reverse=True)[:3]
        top_feeders = [
            {
                "feeder_id": f_id,
                "feeder_name": id_to_full_name.get(f_id, f"Player {f_id}"),
                "feeds_delivered": count,
            }
            for f_id, count in sorted_feeders
        ]

        player_results[str(pid)] = {
            "player_id": pid,
            "player_name": p_name,
            "team_id": tid,
            "passer_profile": {
                "assists_delivered": tot_ast,
                "assisted_points_created": pts_created,
                "points_per_assist": round(pts_per_ast, 2) if pts_per_ast is not None else None,
                "three_pt_assist_share": round(three_share, 4) if three_share is not None else None,
                "rim_assist_share": round(rim_share, 4) if rim_share is not None else None,
                "top_assisted_targets": top_targets,
            },
            "finisher_profile": {
                "assisted_baskets_finished": f_data.get("total_feeds", 0),
                "points_from_assists": f_data.get("pts_from_ast", 0),
                "primary_feeders": top_feeders,
            },
        }

    return team_results, player_results, len(pbp_files)


def main() -> None:
    logger.info("==================================================")
    logger.info("Feature Generation: PBP Directed Assist Network")
    logger.info("==================================================")

    for season in SEASONS:
        logger.info(f"--- Computing Assist Network for Season: {season} ---")
        teams, players, games_count = process_season_assist_network(season)

        if games_count == 0:
            continue

        payload = {
            "season": season,
            "games_evaluated": games_count,
            "team_count": len(teams),
            "player_count": len(players),
            "teams": teams,
            "players": players,
        }

        out_path = os.path.join("data", "processed", "features", f"assist_network_{season}.json")
        write_json(out_path, payload)
        logger.info(f"Saved {len(teams)} team & {len(players)} player assist network profiles to {out_path}")

    logger.info("==================================================")
    logger.info("Assist network modeling complete.")
    logger.info("==================================================")


if __name__ == "__main__":
    main()