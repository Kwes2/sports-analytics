import math

ZONES = ["0-4 ft", "4-14 ft", "14+ ft"]


def classify_shot_distance(x, y):
    """Calculates Euclidean distance to basket at (25.0, 5.25)."""
    dist = math.sqrt((float(x) - 25.0) ** 2 + (float(y) - 5.25) ** 2)
    if dist <= 4.0:
        return "0-4 ft"
    elif dist <= 14.0:
        return "4-14 ft"
    else:
        return "14+ ft"


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


def process_game_shots(plays, home_team_id, away_team_id):
    """
    Parses play-by-play events for valid shot coordinates.
    Returns:
      team_shots: {team_id: {"0-4 ft": {"fgm", "fga"}, ...}}
      player_shots: {shooter_id: {"0-4 ft": {"fgm", "fga"}, ...}}
    """
    team_shots = {
        str(home_team_id): init_zone_dict(),
        str(away_team_id): init_zone_dict()
    }
    player_shots = {}

    for play in plays:
        coord = play.get("coordinate")
        text = play.get("text", "")
        is_shooting = play.get("shootingPlay", False)

        if coord and ("x" in coord and "y" in coord) and (is_shooting or "shot" in text.lower() or "jumper" in text.lower() or "layup" in text.lower() or "dunk" in text.lower()):
            zone = classify_shot_distance(coord["x"], coord["y"])
            t_id = str(play.get("team", {}).get("id", ""))

            is_made = play.get("scoringPlay", False)
            if "missed" in text.lower() or "blocks" in text.lower():
                is_made = False

            if t_id in team_shots:
                team_shots[t_id][zone]["fga"] += 1
                if is_made:
                    team_shots[t_id][zone]["fgm"] += 1

            shooter_id = extract_shooter_id(play)
            if shooter_id:
                if shooter_id not in player_shots:
                    player_shots[shooter_id] = init_zone_dict()
                player_shots[shooter_id][zone]["fga"] += 1
                if is_made:
                    player_shots[shooter_id][zone]["fgm"] += 1

    return team_shots, player_shots