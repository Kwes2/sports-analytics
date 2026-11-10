"""
percentiles.py - Computes absolute ranks and percentile distributions 
across league-wide and position-specific pools, respecting metric polarity.
"""

from stat_metadata import get_stat_meta

def compute_percentile(val, all_vals, higher_is_better=True):
    if not all_vals:
        return 50.0
    
    # Sort values based on polarity
    sorted_vals = sorted(all_vals)
    if not higher_is_better:
        sorted_vals = sorted(all_vals, reverse=True)

    less = sum(1 for x in all_vals if (x < val if higher_is_better else x > val))
    equal = sum(1 for x in all_vals if x == val)
    pct = ((less + 0.5 * equal) / len(all_vals)) * 100
    return round(pct, 1)


def compute_rank(val, all_vals, higher_is_better=True):
    if not all_vals or val is None:
        return 1
    
    # Rank 1 is best. If higher_is_better, sort descending. Else sort ascending.
    sorted_vals = sorted(all_vals, reverse=higher_is_better)
    
    # Find position (1-based index of first occurrence or exact match)
    for idx, x in enumerate(sorted_vals):
        if x == val:
            return idx + 1
            
    # Fallback if float mismatch
    if higher_is_better:
        better_count = sum(1 for x in all_vals if x > val)
    else:
        better_count = sum(1 for x in all_vals if x < val)
    return better_count + 1


def build_stat_pools(players_dict, stat_keys):
    league_pools = {k: [] for k in stat_keys}
    pos_pools = {}

    for p in players_dict.values():
        pos = p["pos"]
        if pos not in pos_pools:
            pos_pools[pos] = {k: [] for k in stat_keys}

        combined_stats = {
            **p["averages"],
            **p["advanced"],
            **p["on_off"],
            **p["passing_profile"],
            **p["prf_metrics"],
            **p["influence_metrics"]
        }

        for k in stat_keys:
            val = combined_stats.get(k, 0.0)
            league_pools[k].append(val)
            pos_pools[pos][k].append(val)

    return league_pools, pos_pools


def build_shot_pools(players_dict, zones):
    vol_pools = {z: [] for z in zones}
    eff_pools = {z: [] for z in zones}

    for p in players_dict.values():
        for z in zones:
            z_data = p.get("zone_shots", {}).get(z, {"fga": 0, "fgm": 0})
            fga = z_data["fga"]
            fgm = z_data["fgm"]
            vol_pools[z].append(fga)
            if fga >= 2:
                eff_pools[z].append(round(fgm / fga * 100, 1))

    return vol_pools, eff_pools


def compute_player_rankings_and_percentiles(combined_stats, league_pools, pos_pools, pos, stat_keys):
    """
    Computes league rank, league percentile, position rank, and position percentile
    for all specified stat keys, respecting stat polarity.
    """
    rankings = {}
    
    for k in stat_keys:
        val = combined_stats.get(k, 0.0)
        meta = get_stat_meta(k)
        hib = meta.get("higher_is_better", True)

        l_pool = league_pools.get(k, [val])
        p_pool = pos_pools.get(pos, {}).get(k, [val])

        l_rank = compute_rank(val, l_pool, higher_is_better=hib)
        l_pct = compute_percentile(val, l_pool, higher_is_better=hib)

        p_rank = compute_rank(val, p_pool, higher_is_better=hib)
        p_pct = compute_percentile(val, p_pool, higher_is_better=hib)

        rankings[k] = {
            "value": val,
            "league_rank": l_rank,
            "league_total": len(l_pool),
            "league_percentile": l_pct,
            "pos_rank": p_rank,
            "pos_total": len(p_pool),
            "pos_percentile": p_pct
        }

    return rankings