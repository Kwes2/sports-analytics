"""
stat_metadata.py - Centralized metadata registry for all NBA statistical metrics.
Defines category groupings, display names, tooltips, formats, polarity, and column presets.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

STAT_METADATA = {
    # -------------------------------------------------------------
    # BASIC OUTPUT STATS
    # -------------------------------------------------------------
    "starter": {
        "name": "Starter",
        "category": "Basic",
        "tooltip": "Started game (1 = Starter, 0 = Bench)",
        "format": "int",
        "higher_is_better": True
    },
    "gp": {
        "name": "Games Played",
        "category": "Basic",
        "tooltip": "Total games played in the selected time period",
        "format": "int",
        "higher_is_better": True
    },
    "gs": {
        "name": "Games Started",
        "category": "Basic",
        "tooltip": "Total games started in the selected time period",
        "format": "int",
        "higher_is_better": True
    },
    "min_pg": {
        "name": "Minutes Per Game",
        "category": "Basic",
        "tooltip": "Average minutes played per contest",
        "format": "float1",
        "higher_is_better": True
    },
    "pts_pg": {
        "name": "Points Per Game",
        "category": "Basic",
        "tooltip": "Average points scored per game",
        "format": "float1",
        "higher_is_better": True
    },
    "reb_pg": {
        "name": "Rebounds Per Game",
        "category": "Basic",
        "tooltip": "Total rebounds (offensive + defensive) per game",
        "format": "float1",
        "higher_is_better": True
    },
    "ast_pg": {
        "name": "Assists Per Game",
        "category": "Basic",
        "tooltip": "Average assists credited per game",
        "format": "float1",
        "higher_is_better": True
    },
    "stl_pg": {
        "name": "Steals Per Game",
        "category": "Basic",
        "tooltip": "Average steals credited per game",
        "format": "float1",
        "higher_is_better": True
    },
    "blk_pg": {
        "name": "Blocks Per Game",
        "category": "Basic",
        "tooltip": "Average shots blocked per game",
        "format": "float1",
        "higher_is_better": True
    },
    "to_pg": {
        "name": "Turnovers Per Game",
        "category": "Basic",
        "tooltip": "Average turnovers committed per game",
        "format": "float1",
        "higher_is_better": False
    },
    "pf_pg": {
        "name": "Personal Fouls Per Game",
        "category": "Basic",
        "tooltip": "Average personal fouls committed per game",
        "format": "float1",
        "higher_is_better": False
    },
    "plus_minus_pg": {
        "name": "Plus-Minus Per Game",
        "category": "Basic",
        "tooltip": "Average point differential while the player was on court",
        "format": "float1",
        "higher_is_better": True
    },
    "fgm_pg": {
        "name": "Field Goals Made Per Game",
        "category": "Basic",
        "tooltip": "Average field goals made per game",
        "format": "float1",
        "higher_is_better": True
    },
    "fga_pg": {
        "name": "Field Goal Attempts Per Game",
        "category": "Basic",
        "tooltip": "Average field goals attempted per game",
        "format": "float1",
        "higher_is_better": True
    },
    "fg_pct": {
        "name": "Field Goal %",
        "category": "Basic",
        "tooltip": "Percentage of field goals made (FGM / FGA)",
        "format": "pct1",
        "higher_is_better": True
    },
    "fg3m_pg": {
        "name": "3-Pointers Made Per Game",
        "category": "Basic",
        "tooltip": "Average 3-point field goals made per game",
        "format": "float1",
        "higher_is_better": True
    },
    "fg3a_pg": {
        "name": "3-Point Attempts Per Game",
        "category": "Basic",
        "tooltip": "Average 3-point field goals attempted per game",
        "format": "float1",
        "higher_is_better": True
    },
    "fg3_pct": {
        "name": "3-Point %",
        "category": "Basic",
        "tooltip": "Percentage of 3-point attempts made (3PM / 3PA)",
        "format": "pct1",
        "higher_is_better": True
    },
    "ftm_pg": {
        "name": "Free Throws Made Per Game",
        "category": "Basic",
        "tooltip": "Average free throws made per game",
        "format": "float1",
        "higher_is_better": True
    },
    "fta_pg": {
        "name": "Free Throw Attempts Per Game",
        "category": "Basic",
        "tooltip": "Average free throws attempted per game",
        "format": "float1",
        "higher_is_better": True
    },
    "ft_pct": {
        "name": "Free Throw %",
        "category": "Basic",
        "tooltip": "Percentage of free throw attempts made (FTM / FTA)",
        "format": "pct1",
        "higher_is_better": True
    },
    "oreb_pg": {
        "name": "Offensive Rebounds Per Game",
        "category": "Basic",
        "tooltip": "Average offensive rebounds secured per game",
        "format": "float1",
        "higher_is_better": True
    },
    "dreb_pg": {
        "name": "Defensive Rebounds Per Game",
        "category": "Basic",
        "tooltip": "Average defensive rebounds secured per game",
        "format": "float1",
        "higher_is_better": True
    },
    "stocks_pg": {
        "name": "Stocks Per Game",
        "category": "Basic",
        "tooltip": "Combined steals + blocks per game",
        "format": "float1",
        "higher_is_better": True
    },

    # -------------------------------------------------------------
    # ADVANCED EFFICIENCY & BOX SCORE VALUE
    # -------------------------------------------------------------
    "trb_pct": {
        "name": "Total Rebound % (TRB%)",
        "category": "Advanced",
        "tooltip": "Estimate of the percentage of available rebounds a player grabbed while on the court",
        "format": "pct1",
        "higher_is_better": True
    },
    "ts_pct": {
        "name": "True Shooting %",
        "category": "Advanced",
        "tooltip": "Scoring efficiency measure taking 2s, 3s, and FTs into account: PTS / (2 * (FGA + 0.44 * FTA))",
        "format": "pct1",
        "higher_is_better": True
    },
    "efg_pct": {
        "name": "Effective Field Goal %",
        "category": "Advanced",
        "tooltip": "Field goal percentage adjusted for the extra point value of 3-pointers: (FGM + 0.5 * 3PM) / FGA",
        "format": "pct1",
        "higher_is_better": True
    },
    "usg_pct": {
        "name": "Usage Rate %",
        "category": "Advanced",
        "tooltip": "Estimate of the percentage of team plays used by a player while on the floor",
        "format": "pct1",
        "higher_is_better": True
    },
    "tov_pct": {
        "name": "Turnover Rate %",
        "category": "Advanced",
        "tooltip": "Turnovers committed per 100 individual offensive plays used",
        "format": "pct1",
        "higher_is_better": False
    },
    "ast_to_ratio": {
        "name": "Assist-to-Turnover Ratio",
        "category": "Advanced",
        "tooltip": "Ratio of assists credited to turnovers committed",
        "format": "float2",
        "higher_is_better": True
    },
    "three_par": {
        "name": "3-Point Attempt Rate",
        "category": "Advanced",
        "tooltip": "Percentage of total field goal attempts that are 3-pointers",
        "format": "pct1",
        "higher_is_better": True
    },
    "ft_rate": {
        "name": "Free Throw Rate",
        "category": "Advanced",
        "tooltip": "Ratio of free throw attempts to field goal attempts (FTA / FGA)",
        "format": "pct1",
        "higher_is_better": True
    },
    "ppsa": {
        "name": "Points Per Shot Attempt",
        "category": "Advanced",
        "tooltip": "Scoring output generated per field goal attempted (PTS / FGA)",
        "format": "float2",
        "higher_is_better": True
    },
    "gmsc_avg": {
        "name": "Average Game Score",
        "category": "Advanced",
        "tooltip": "John Hollinger's single-game overall box score efficiency rating",
        "format": "float1",
        "higher_is_better": True
    },
    "per": {
        "name": "Player Efficiency Rating (PER)",
        "category": "Advanced",
        "tooltip": "Per-minute statistical production rating scaled to a league average of 15.0",
        "format": "float1",
        "higher_is_better": True
    },
    "bpm": {
        "name": "Box Plus-Minus (BPM 2.0)",
        "category": "Advanced",
        "tooltip": "Net points contributed per 100 possessions above a league-average player (+0.0 is league average)",
        "format": "float1",
        "higher_is_better": True
    },
    "vorp": {
        "name": "Value Over Replacement Player (VORP)",
        "category": "Advanced",
        "tooltip": "Estimated cumulative points contributed above a replacement level player (-2.0 BPM)",
        "format": "float2",
        "higher_is_better": True
    },

    # -------------------------------------------------------------
    # SHOOTING & QUALITY
    # -------------------------------------------------------------
    "xefg_pct": {
        "name": "Expected eFG %",
        "category": "Shooting",
        "tooltip": "Expected effective FG% based purely on the league-wide difficulty of locations taken",
        "format": "pct1",
        "higher_is_better": True
    },
    "smoe": {
        "name": "Shot-Making Over Expected (SMOE)",
        "category": "Shooting",
        "tooltip": "Actual eFG% minus Expected eFG%. Measures finishing ability independent of shot diet",
        "format": "float1",
        "higher_is_better": True
    },
    "mei": {
        "name": "Moreyball Efficiency Index",
        "category": "Shooting",
        "tooltip": "Percentage of shot possessions ending in high-efficiency areas (Rim, 3PT, or Free Throw line)",
        "format": "pct1",
        "higher_is_better": True
    },
    "corner3_pct": {
        "name": "Corner 3PT %",
        "category": "Shooting",
        "tooltip": "Field goal percentage on 3-point attempts from the left/right corners",
        "format": "pct1",
        "higher_is_better": True
    },
    "corner3_fga_pg": {
        "name": "Corner 3 Attempts Per Game",
        "category": "Shooting",
        "tooltip": "Corner 3-point field goal attempts per game",
        "format": "float1",
        "higher_is_better": True
    },
    "atb3_pct": {
        "name": "Above-the-Break 3PT %",
        "category": "Shooting",
        "tooltip": "Field goal percentage on 3-point attempts above the break (wings and top of the key)",
        "format": "pct1",
        "higher_is_better": True
    },
    "atb3_fga_pg": {
        "name": "Above-the-Break 3A Per Game",
        "category": "Shooting",
        "tooltip": "Above-the-break 3-point field goal attempts per game",
        "format": "float1",
        "higher_is_better": True
    },
    "ast_fg_pct": {
        "name": "Assisted FG %",
        "category": "Shooting",
        "tooltip": "Percentage of player's made field goals that were assisted by a teammate",
        "format": "pct1",
        "higher_is_better": True
    },
    "unast_fg_pct": {
        "name": "Unassisted (Self-Created) FG %",
        "category": "Shooting",
        "tooltip": "Percentage of player's made field goals created independently without an assist",
        "format": "pct1",
        "higher_is_better": True
    },
    "ast_3p_pct": {
        "name": "Assisted 3PT %",
        "category": "Shooting",
        "tooltip": "Percentage of player's made 3-pointers that were assisted (catch-and-shoot looks)",
        "format": "pct1",
        "higher_is_better": True
    },
    "unast_3p_pct": {
        "name": "Unassisted 3PT %",
        "category": "Shooting",
        "tooltip": "Percentage of player's made 3-pointers that were unassisted (pull-ups / off the dribble)",
        "format": "pct1",
        "higher_is_better": True
    },
    "rim_fg_pct": {
        "name": "Rim FG % (0-4 ft)",
        "category": "Shooting",
        "tooltip": "Field goal percentage on attempts within 4 feet of the basket",
        "format": "pct1",
        "higher_is_better": True
    },
    "rim_fga_pg": {
        "name": "Rim Attempts Per Game",
        "category": "Shooting",
        "tooltip": "Attempts per game within 4 feet of the rim",
        "format": "float1",
        "higher_is_better": True
    },
    "rim_share": {
        "name": "Rim Attempt Share %",
        "category": "Shooting",
        "tooltip": "Percentage of player's total shots taken within 4 feet of the rim",
        "format": "pct1",
        "higher_is_better": True
    },
    "mid_fg_pct": {
        "name": "Mid-Range FG % (4-14 ft)",
        "category": "Shooting",
        "tooltip": "Field goal percentage on attempts between 4 and 14 feet",
        "format": "pct1",
        "higher_is_better": True
    },
    "mid_fga_pg": {
        "name": "Mid-Range Attempts Per Game",
        "category": "Shooting",
        "tooltip": "Attempts per game between 4 and 14 feet",
        "format": "float1",
        "higher_is_better": True
    },
    "mid_share": {
        "name": "Mid-Range Attempt Share %",
        "category": "Shooting",
        "tooltip": "Percentage of player's total shots taken between 4 and 14 feet",
        "format": "pct1",
        "higher_is_better": True
    },
    "three_fg_pct": {
        "name": "Perimeter / 3PT FG % (14+ ft)",
        "category": "Shooting",
        "tooltip": "Field goal percentage on long-range attempts (14+ feet and 3PT)",
        "format": "pct1",
        "higher_is_better": True
    },
    "three_fga_pg": {
        "name": "Perimeter Attempts Per Game",
        "category": "Shooting",
        "tooltip": "Attempts per game from 14+ feet and 3PT range",
        "format": "float1",
        "higher_is_better": True
    },
    "three_share": {
        "name": "Perimeter Attempt Share %",
        "category": "Shooting",
        "tooltip": "Percentage of player's total shots taken from 14+ feet and 3PT range",
        "format": "pct1",
        "higher_is_better": True
    },

    # -------------------------------------------------------------
    # PASSING & PLAYMAKING QUALITY
    # -------------------------------------------------------------
    "pts_created_pg": {
        "name": "Points Created Per Game",
        "category": "Passing",
        "tooltip": "Points scored by teammates directly off this player's assists per game",
        "format": "float1",
        "higher_is_better": True
    },
    "prf_pg": {
        "name": "Points Responsible For (PRF)",
        "category": "Passing",
        "tooltip": "Direct points scored per game plus points created off assists per game",
        "format": "float1",
        "higher_is_better": True
    },
    "xprf_pg": {
        "name": "Expected Points Responsible For (xPRF)",
        "category": "Passing",
        "tooltip": "Expected total points generated from volume: (FGA * xFG%) + (3PA * x3P%) + (FTA * xFT%) + Expected Assist Points per game",
        "format": "float1",
        "higher_is_better": True
    },
    "prfoe_pg": {
        "name": "Points Responsible For Over Expected (PRFOE)",
        "category": "Passing",
        "tooltip": "Actual PRF/G minus Expected PRF/G. Measures individual scoring & playmaking shot-making talent above opportunity baseline",
        "format": "float1",
        "higher_is_better": True
    },
    "pct_team_prf": {
        "name": "% of Team Points Accounted For",
        "category": "Passing",
        "tooltip": "Share of the team's total game scoring directly created by this player",
        "format": "pct1",
        "higher_is_better": True
    },
    "pts_per_ast": {
        "name": "Points Per Assist",
        "category": "Passing",
        "tooltip": "Average points scored per credited assist",
        "format": "float2",
        "higher_is_better": True
    },
    "xpts_per_ast": {
        "name": "Expected Points Per Assist",
        "category": "Passing",
        "tooltip": "Baseline points expected per assist given the shooting zones of targets",
        "format": "float2",
        "higher_is_better": True
    },
    "paoe": {
        "name": "Points Per Assist Over Expected (PAOE)",
        "category": "Passing",
        "tooltip": "Points per assist minus expected points per assist (shot-creation quality added)",
        "format": "float2",
        "higher_is_better": True
    },
    "points_added_pg": {
        "name": "Points Added Per Game",
        "category": "Passing",
        "tooltip": "Net points generated per game above the league baseline across all assisted shots",
        "format": "float2",
        "higher_is_better": True
    },
    "rim_ast_pct": {
        "name": "Rim Assist Share %",
        "category": "Passing",
        "tooltip": "Percentage of player's total assists that set up baskets at the rim (0-4 ft)",
        "format": "pct1",
        "higher_is_better": True
    },
    "three_ast_pct": {
        "name": "3-Point Assist Share %",
        "category": "Passing",
        "tooltip": "Percentage of player's total assists that set up 3-point field goals",
        "format": "pct1",
        "higher_is_better": True
    },

    # -------------------------------------------------------------
    # RATINGS, RAPM & ON/OFF DIFFERENTIALS
    # -------------------------------------------------------------
    "net_rapm": {
        "name": "Net RAPM",
        "category": "Ratings",
        "tooltip": "Regularized Adjusted Plus-Minus: Isolated net impact per 100 possessions via 10-man ridge regression",
        "format": "float2",
        "higher_is_better": True
    },
    "orapm": {
        "name": "Offensive RAPM",
        "category": "Ratings",
        "tooltip": "Isolated offensive scoring contribution per 100 possessions above league average",
        "format": "float2",
        "higher_is_better": True
    },
    "drapm": {
        "name": "Defensive RAPM",
        "category": "Ratings",
        "tooltip": "Isolated defensive suppression per 100 possessions (higher = better defense)",
        "format": "float2",
        "higher_is_better": True
    },

    # Team On/Off Ratings
    "team_on_ortg": {
        "name": "Team On Offensive Rating",
        "category": "Ratings",
        "tooltip": "Team points scored per 100 possessions while player is ON the court",
        "format": "float1",
        "higher_is_better": True
    },
    "team_on_drtg": {
        "name": "Team On Defensive Rating",
        "category": "Ratings",
        "tooltip": "Opponent points scored per 100 possessions while player is ON the court",
        "format": "float1",
        "higher_is_better": False
    },
    "team_on_net_rtg": {
        "name": "Team On Net Rating",
        "category": "Ratings",
        "tooltip": "Team Net Rating (ORtg - DRtg) while player is ON the court",
        "format": "float1",
        "higher_is_better": True
    },
    "team_off_ortg": {
        "name": "Team Off Offensive Rating",
        "category": "Ratings",
        "tooltip": "Team points scored per 100 possessions while player is OFF the court",
        "format": "float1",
        "higher_is_better": True
    },
    "team_off_drtg": {
        "name": "Team Off Defensive Rating",
        "category": "Ratings",
        "tooltip": "Opponent points scored per 100 possessions while player is OFF the court",
        "format": "float1",
        "higher_is_better": False
    },
    "team_off_net_rtg": {
        "name": "Team Off Net Rating",
        "category": "Ratings",
        "tooltip": "Team Net Rating (ORtg - DRtg) while player is OFF the court",
        "format": "float1",
        "higher_is_better": True
    },
    "team_diff_ortg": {
        "name": "Team Diff Offensive Rating",
        "category": "Ratings",
        "tooltip": "Team Offensive Rating ON minus OFF the court",
        "format": "float1",
        "higher_is_better": True
    },
    "team_diff_drtg": {
        "name": "Team Diff Defensive Rating",
        "category": "Ratings",
        "tooltip": "Team Defensive Rating ON minus OFF the court (negative = better defense on-court)",
        "format": "float1",
        "higher_is_better": False
    },
    "team_diff_net_rtg": {
        "name": "Team Diff Net Rating",
        "category": "Ratings",
        "tooltip": "Team Net Rating ON minus OFF the court (Net On/Off impact)",
        "format": "float1",
        "higher_is_better": True
    },

    # Opponent On/Off Ratings
    "opp_on_ortg": {
        "name": "Opponent On Offensive Rating",
        "category": "Ratings",
        "tooltip": "Opponent points scored per 100 possessions while player is ON the court",
        "format": "float1",
        "higher_is_better": False
    },
    "opp_on_drtg": {
        "name": "Opponent On Defensive Rating",
        "category": "Ratings",
        "tooltip": "Team points allowed by opponent per 100 possessions while player is ON the court",
        "format": "float1",
        "higher_is_better": True
    },
    "opp_on_net_rtg": {
        "name": "Opponent On Net Rating",
        "category": "Ratings",
        "tooltip": "Opponent Net Rating while player is ON the court",
        "format": "float1",
        "higher_is_better": False
    },
    "opp_off_ortg": {
        "name": "Opponent Off Offensive Rating",
        "category": "Ratings",
        "tooltip": "Opponent points scored per 100 possessions while player is OFF the court",
        "format": "float1",
        "higher_is_better": False
    },
    "opp_off_drtg": {
        "name": "Opponent Off Defensive Rating",
        "category": "Ratings",
        "tooltip": "Team points allowed by opponent per 100 possessions while player is OFF the court",
        "format": "float1",
        "higher_is_better": True
    },
    "opp_off_net_rtg": {
        "name": "Opponent Off Net Rating",
        "category": "Ratings",
        "tooltip": "Opponent Net Rating while player is OFF the court",
        "format": "float1",
        "higher_is_better": False
    },
    "opp_diff_ortg": {
        "name": "Opponent Diff Offensive Rating",
        "category": "Ratings",
        "tooltip": "Opponent Offensive Rating ON minus OFF (negative = suppressed opponent offense)",
        "format": "float1",
        "higher_is_better": False
    },
    "opp_diff_drtg": {
        "name": "Opponent Diff Defensive Rating",
        "category": "Ratings",
        "tooltip": "Opponent Defensive Rating ON minus OFF",
        "format": "float1",
        "higher_is_better": True
    },
    "opp_diff_net_rtg": {
        "name": "Opponent Diff Net Rating",
        "category": "Ratings",
        "tooltip": "Opponent Net Rating ON minus OFF the court",
        "format": "float1",
        "higher_is_better": False
    }
}

# Standardized Column Presets for Table Viewers
PRESET_COLUMNS = {
    "standard": [
        "player", "team", "pos", "gp", "gs", "min_pg", "pts_pg", "prf_pg",
        "reb_pg", "ast_pg", "stl_pg", "blk_pg", "fg_pct", "fg3_pct", "ft_pct"
    ],
    "advanced": [
        "player", "team", "pos", "gp", "min_pg", "pts_pg", "prf_pg", "xprf_pg", "prfoe_pg",
        "trb_pct", "ts_pct", "efg_pct", "xefg_pct", "smoe", "mei", "usg_pct", "tov_pct", "ast_to_ratio", "ppsa", "gmsc_avg"
    ],
    "ratings": [
        "player", "team", "pos", "gp", "min_pg",
        "net_rapm", "orapm", "drapm", "bpm", "vorp", "per",
        "team_on_ortg", "team_on_drtg", "team_on_net_rtg",
        "team_off_ortg", "team_off_drtg", "team_off_net_rtg",
        "team_diff_ortg", "team_diff_drtg", "team_diff_net_rtg",
        "opp_on_ortg", "opp_on_drtg", "opp_on_net_rtg",
        "opp_off_ortg", "opp_off_drtg", "opp_off_net_rtg",
        "opp_diff_ortg", "opp_diff_drtg", "opp_diff_net_rtg"
    ],
    "passing": [
        "player", "team", "pos", "gp", "ast_pg", "pts_created_pg", "prf_pg", "xprf_pg", "prfoe_pg",
        "pct_team_prf", "pts_per_ast", "xpts_per_ast", "paoe", "points_added_pg", "rim_ast_pct", "three_ast_pct"
    ],
    "shooting": [
        "player", "team", "pos", "gp", "fga_pg", "fg_pct", "xefg_pct", "smoe", "mei",
        "corner3_pct", "corner3_fga_pg", "atb3_pct", "atb3_fga_pg",
        "ast_fg_pct", "unast_fg_pct", "ast_3p_pct", "unast_3p_pct",
        "rim_fg_pct", "rim_fga_pg", "rim_share", "mid_fg_pct", "mid_fga_pg", "mid_share", "three_fg_pct", "three_fga_pg", "three_share"
    ]
}


def get_stat_meta(key: str) -> dict:
    if key in STAT_METADATA:
        return STAT_METADATA[key]

    clean_name = key.replace("_", " ").title()
    if clean_name.endswith(" Pg"):
        clean_name = clean_name[:-3] + " Per Game"
    elif clean_name.endswith(" Pct"):
        clean_name = clean_name[:-4] + " %"

    return {
        "name": clean_name,
        "category": "Miscellaneous",
        "tooltip": f"{clean_name} metric",
        "format": "float1",
        "higher_is_better": True
    }


def export_metadata_json(output_path=None):
    if output_path is None:
        output_path = DATA_DIR / "stat_definitions.json"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(STAT_METADATA, f, indent=2)
    print(f"Stat metadata exported to {output_path}")


if __name__ == "__main__":
    export_metadata_json()