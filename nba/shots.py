import math

ZONES = ["0-4 ft", "4-14 ft", "14+ ft"]
GRANULAR_ZONES = ["rim", "short_mid", "long_mid", "corner_3", "atb_3"]


def classify_shot_distance(x, y):
    dist = math.sqrt((float(x) - 25.0) ** 2 + (float(y) - 5.25) ** 2)
    if dist <= 4.0:
        return "0-4 ft"
    elif dist <= 14.0:
        return "4-14 ft"
    else:
        return "14+ ft"


def classify_shot_granular(x, y, is_three):
    """
    Classifies shots into 5 canonical NBA analytical zones:
    rim, short_mid, long_mid, corner_3, atb_3.
    """
    fx = float(x)
    fy = float(y)
    dist = math.sqrt((fx - 25.0) ** 2 + (fy - 5.25) ** 2)

    if dist <= 4.0:
        return "rim"
    elif is_three:
        # Corner 3: Within 14 ft of baseline and at least 22 ft from center
        if fy <= 14.0 and abs(fx - 25.0) >= 21.5:
            return "corner_3"
        return "atb_3"
    else:
        if dist <= 12.0:
            return "short_mid"
        return "long_mid"


def extract_shooter_id(play):
    participants = play.get("participants", [])
    if participants and isinstance(participants[0], dict):
        primary = participants[0]
        if "athlete" in primary and "id" in primary["athlete"]:
            return str(primary["athlete"]["id"])
        if "id" in primary:
            return str(primary["id"])
    if "athlete" in play and isinstance(play["athlete"], dict):
        return str(play["athlete"].get("id"))
    return None


def init_zone_dict():
    return {z: {"fgm": 0, "fga": 0} for z in ZONES}


def init_granular_dict():
    return {z: {"fgm": 0, "fga": 0, "fg3m": 0} for z in GRANULAR_ZONES}


def process_game_shots(plays, home_team_id, away_team_id):
    team_shots = {
        str(home_team_id): init_zone_dict(),
        str(away_team_id): init_zone_dict()
    }
    player_shots = {}
    player_granular_shots = {}

    for play in plays:
        coord = play.get("coordinate")
        text = play.get("text", "")
        is_shooting = play.get("shootingPlay", False)

        if coord and ("x" in coord and "y" in coord) and (is_shooting or "shot" in text.lower() or "jumper" in text.lower() or "layup" in text.lower() or "dunk" in text.lower()):
            cx = coord["x"]
            cy = coord["y"]
            zone = classify_shot_distance(cx, cy)
            t_id = str(play.get("team", {}).get("id", ""))

            is_made = play.get("scoringPlay", False)
            if "missed" in text.lower() or "blocks" in text.lower():
                is_made = False

            is_three = ("three point" in text.lower() or "3pt" in text.lower())
            g_zone = classify_shot_granular(cx, cy, is_three)

            if t_id in team_shots:
                team_shots[t_id][zone]["fga"] += 1
                if is_made:
                    team_shots[t_id][zone]["fgm"] += 1

            shooter_id = extract_shooter_id(play)
            if shooter_id:
                if shooter_id not in player_shots:
                    player_shots[shooter_id] = init_zone_dict()
                    player_granular_shots[shooter_id] = init_granular_dict()

                player_shots[shooter_id][zone]["fga"] += 1
                player_granular_shots[shooter_id][g_zone]["fga"] += 1

                if is_made:
                    player_shots[shooter_id][zone]["fgm"] += 1
                    player_granular_shots[shooter_id][g_zone]["fgm"] += 1
                    if is_three:
                        player_granular_shots[shooter_id][g_zone]["fg3m"] += 1

    return team_shots, player_shots, player_granular_shots


def compute_shot_quality_metrics(granular_shots, league_granular_efg, fta, tot_fga):
    """
    Computes Expected eFG% (xeFG%), Shot-Making Over Expected (SMOE),
    and Daryl Morey's Moreyball Efficiency Index (MEI).
    """
    total_fga = sum(granular_shots[z]["fga"] for z in GRANULAR_ZONES)
    if total_fga == 0:
        return {"xefg_pct": 0.0, "smoe": 0.0, "mei": 0.0}

    total_fgm = sum(granular_shots[z]["fgm"] for z in GRANULAR_ZONES)
    total_fg3m = sum(granular_shots[z]["fg3m"] for z in GRANULAR_ZONES)

    # Actual eFG% on tracked shots
    actual_efg = round((total_fgm + 0.5 * total_fg3m) / total_fga * 100, 1)

    # Expected eFG% based on where the player took their shots
    expected_makes = sum(
        granular_shots[z]["fga"] * (league_granular_efg.get(z, 50.0) / 100.0)
        for z in GRANULAR_ZONES
    )
    xefg_pct = round(expected_makes / total_fga * 100, 1)

    # Shot-Making Over Expected
    smoe = round(actual_efg - xefg_pct, 1)

    # Moreyball Index: (Rim FGA + 3PT FGA + 0.44 * FTA) / (Total FGA + 0.44 * FTA)
    rim_fga = granular_shots["rim"]["fga"]
    three_fga = granular_shots["corner_3"]["fga"] + granular_shots["atb_3"]["fga"]
    tot_poss_shots = tot_fga + 0.44 * fta

    if tot_poss_shots > 0:
        mei = round((rim_fga + three_fga + 0.44 * fta) / tot_poss_shots * 100, 1)
    else:
        mei = 0.0

    return {
        "xefg_pct": xefg_pct,
        "smoe": smoe,
        "mei": mei
    }