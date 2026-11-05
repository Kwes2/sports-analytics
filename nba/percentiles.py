def compute_percentile(val, all_vals):
    """Calculates pure numerical percentile rank (0 to 100) with tie handling."""
    if not all_vals:
        return 50.0
    less = sum(1 for x in all_vals if x < val)
    equal = sum(1 for x in all_vals if x == val)
    pct = ((less + 0.5 * equal) / len(all_vals)) * 100
    return round(pct, 1)


def build_stat_pools(players_dict, stat_keys):
    """Builds distribution arrays for league-wide and position-specific metrics."""
    league_pools = {k: [] for k in stat_keys}
    pos_pools = {}

    for p in players_dict.values():
        pos = p["pos"]
        if pos not in pos_pools:
            pos_pools[pos] = {k: [] for k in stat_keys}

        combined_stats = {**p["averages"], **p["advanced"]}

        for k in stat_keys:
            val = combined_stats.get(k, 0.0)
            league_pools[k].append(val)
            pos_pools[pos][k].append(val)

    return league_pools, pos_pools


def build_shot_pools(players_dict, zones):
    """Builds distribution arrays for zone efficiency and volume."""
    vol_pools = {z: [] for z in zones}
    eff_pools = {z: [] for z in zones}

    for p in players_dict.values():
        for z in zones:
            fga = p["zone_shots"][z]["fga"]
            fgm = p["zone_shots"][z]["fgm"]
            vol_pools[z].append(fga)
            if fga >= 2:
                eff_pools[z].append(round(fgm / fga * 100, 1))

    return vol_pools, eff_pools