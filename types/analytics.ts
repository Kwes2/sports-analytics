/**
 * TypeScript Data Contracts for NBA Analytics Platform
 * Defines shapes for Tier 1 (Directory Index), Tier 2 (Full Profiles),
 * Tier 3 (Leaderboards), and Tier 4 (Matchup Simulator).
 */

// ---------------------------------------------------------------------------
// Base Common Types
// ---------------------------------------------------------------------------
export type PositionGroup = 'Guard' | 'Forward' | 'Center';
export type Conference = 'East' | 'West';
export type ShotZoneName =
  | 'Restricted Area'
  | 'In The Paint (Non-RA)'
  | 'Mid-Range'
  | 'Left Corner 3'
  | 'Right Corner 3'
  | 'Above the Break 3'
  | 'Backcourt';

export interface TeamColors {
  primary: string;
  secondary: string;
  accent?: string;
}

export interface TeamIdentity {
  team_id: number;
  team_name: string;
  team_abbrev: string;
  conference: Conference;
  division: string;
  logo_url: string;
  colors: TeamColors;
  overall_elo?: number;
}

// ---------------------------------------------------------------------------
// Tier 1: Directory Index Payloads (~75 KB)
// ---------------------------------------------------------------------------
export interface PlayerIndexItem {
  player_id: number;
  player_name: string;
  team_id: number;
  team_abbrev: string;
  position: PositionGroup;
  headshot_url: string;
  games_played: number;
  minutes_per_game: number;
  usage_pct: number;
  true_shooting_pct: number | null;
  effective_fg_pct: number | null;
  pts_per_100: number;
  ast_per_100: number;
  reb_per_100: number;
  net_epm: number | null;
  offensive_epm: number | null;
  defensive_epm: number | null;
  archetype?: string;
  percentile_ranks: {
    net_epm: number | null;
    true_shooting: number | null;
    rim_pressure: number | null;
    self_creation: number | null;
  };
}

export interface TeamIndexItem extends TeamIdentity {
  games_played: number;
  pace: number;
  offensive_rating: number;
  defensive_rating: number;
  net_rating: number;
  overall_elo: number;
  offensive_elo: number;
  defensive_elo: number;
  percentile_ranks: {
    net_rating: number | null;
    overall_elo: number | null;
    rim_denial: number | null;
  };
}

// ---------------------------------------------------------------------------
// Tier 2: Deep Entity Profiles (~15 KB each)
// ---------------------------------------------------------------------------
export interface ZoneShotStats {
  attempts: number;
  made: number;
  frequency?: number;
  fg_pct: number;
  baseline_fg_pct?: number;
  delta_fg_pct?: number | null;
  status?: 'HOT' | 'COLD' | 'NEUTRAL' | 'INSUFFICIENT_VOLUME';
}

export interface ShotDensityBin {
  x: number;
  y: number;
  fga: number;
  fgm: number;
  fg_pct: number;
  efg_pct: number;
}

export interface PlayerFullProfile {
  player_id: number;
  player_name: string;
  team_id: number;
  team_abbrev: string;
  position: PositionGroup;
  headshot_url: string;
  bio: {
    raw_position: string;
    height: string | null;
    weight: string | null;
    age: number | null;
  };
  games_played: number;
  minutes_total: number;
  minutes_per_game: number;
  usage_pct: number;
  true_shooting_pct: number | null;
  effective_fg_pct: number | null;
  ast_tov_ratio: number;
  per_100_possessions: {
    points: number;
    rebounds: number;
    assists: number;
    turnovers: number;
    steals: number;
    blocks: number;
  };
  effective_plus_minus: {
    offensive_epm?: number;
    defensive_epm?: number;
    net_epm?: number;
  };
  relative_plus_minus: {
    stint_possessions?: number;
    actual_net_margin_per_100?: number;
    expected_net_margin_per_100?: number;
    relative_plus_minus?: number;
  };
  oliver_floor_rates: {
    true_ast_pct?: number;
    true_orb_pct?: number;
    true_dreb_pct?: number;
    stock_rate_per_100?: number;
    foul_drawing_premium?: number;
  };
  hustle_tracking: {
    minutes_evaluated?: number;
    deflections_total?: number;
    deflections_per_100?: number;
    screen_assists_total?: number;
    screen_assists_per_100?: number;
    screen_assist_pts_per_100?: number;
    charges_drawn_per_100?: number;
    loose_balls_recovered_per_100?: number;
    box_outs_per_100?: number;
  };
  assist_network_profile: {
    passer_profile: {
      assists_delivered?: number;
      assisted_points_created?: number;
      points_per_assist?: number | null;
      three_pt_assist_share?: number | null;
      rim_assist_share?: number | null;
      top_assisted_targets?: Array<{
        target_id: number;
        target_name: string;
        assists_received: number;
      }>;
    };
    finisher_profile: {
      assisted_baskets_finished?: number;
      points_from_assists?: number;
      primary_feeders?: Array<{
        feeder_id: number;
        feeder_name: string;
        feeds_delivered: number;
      }>;
    };
  };
  shot_making_and_creation: {
    fga: number;
    shot_quality_xefg?: number;
    smoe_total?: number;
    smoe_per_100?: number;
    creation_profile?: {
      self_created_fga?: number;
      self_creation_rate?: number;
      self_created_efg?: number | null;
      self_created_smoe_per_100?: number | null;
      assisted_fga?: number;
      assisted_efg?: number | null;
      creation_efficiency_tax?: number | null;
    };
    rim_pressure?: {
      rim_attempts?: number;
      rim_pressure_rate?: number;
      rim_fg_pct?: number | null;
      rim_finishing_premium?: number | null;
    };
    corner_3_specialist_premium?: number | null;
    hot_cold_zones?: Record<string, ZoneShotStats>;
    shot_density_bins?: ShotDensityBin[];
  };
  game_flow_and_clutch: {
    quarter_splits?: {
      q1_fga?: number;
      q1_efg?: number | null;
      q1_jumpstart_rating?: number | null;
      q4_fga?: number;
      q4_efg?: number | null;
      q4_production_rating?: number | null;
    };
    clutch_execution?: {
      clutch_fga?: number;
      clutch_efg?: number | null;
      non_clutch_efg?: number | null;
      clutch_execution_gap?: number | null;
    };
  };
  consistency_and_schedule: {
    volatility_profile?: {
      scoring_volatility_index_svi?: number | null;
      scoring_floor_pts_100?: number | null;
      scoring_ceiling_pts_100?: number | null;
      sub_zero_game_rate?: number | null;
      sub_zero_games_count?: number;
      explosion_game_rate?: number | null;
      explosion_games_count?: number;
    };
    schedule_rest_splits?: {
      b2b_degradation_ts?: number | null;
      splits?: Record<string, any>;
    };
    venue_splits?: {
      road_dropoff_ts?: number | null;
      home?: any;
      away?: any;
    };
  };
  percentile_ranks: {
    league_wide: Record<string, number | null>;
    positional_peer: {
      position_group: PositionGroup;
      true_shooting?: number | null;
      net_epm?: number | null;
      rim_pressure?: number | null;
      playmaking_load?: number | null;
      rebound_dominance?: number | null;
      usage_to_efficiency_ratio?: number | null;
    };
  };
  archetype?: {
    offensive_role: string;
    defensive_role: string;
    description?: string;
    offensive_description?: string;
    defensive_description?: string;
  };
  similar_players?: Array<{
    player_id: number;
    player_name: string;
    team_abbrev?: string;
    similarity_score_pct: number;
    headshot_url: string;
  }>;
}

export interface TeamFullProfile extends TeamIdentity {
  games_played: number;
  pace: number;
  ratings: {
    offensive_rating: number;
    defensive_rating: number;
    net_rating: number;
  };
  elo_ratings: {
    offensive_elo: number;
    defensive_elo: number;
    overall_elo: number;
  };
  four_factors: {
    offensive_effective_fg_pct?: number;
    offensive_shot_quality_xefg?: number;
    smoe_per_100?: number;
    defensive_four_factors?: {
      opp_effective_fg_pct?: number;
      defensive_tov_pct_forced?: number;
      defensive_rebound_pct?: number;
      opp_free_throw_rate?: number;
    };
    shot_density_bins?: ShotDensityBin[];
  };
  defensive_spatial_suppression: {
    opp_shot_quality_allowed_xefga?: number;
    defensive_finishing_delta?: number;
    opponent_paint_funnel_rate?: number;
    rim_denial_efficiency?: number;
    defensive_hot_cold_allowed?: Record<string, any>;
  };
  playmaking_and_chemistry: {
    helicentrism_index?: number;
    assist_gini_coefficient?: number;
    playmaking_depth_share?: number;
    network_reciprocity_index?: number;
    top_synergy_duos?: Array<{
      passer_id: number;
      passer_name: string;
      scorer_id: number;
      scorer_name: string;
      assists_count: number;
      points_created: number;
      share_of_team_assists: number;
    }>;
  };
  momentum_and_runs: {
    runs_8_0_per_game?: number;
    runs_10_0_per_game?: number;
    runs_12_0_per_game?: number;
    runs_conceded_per_game?: number;
    net_run_margin_per_game?: number;
  };
  lead_volatility: {
    double_digit_lead_preservation_pct?: number;
    double_digit_deficit_comeback_pct?: number;
    largest_comeback_win?: number;
    largest_blown_lead?: number;
  };
  hustle_and_rotations: {
    team_hustle_per_game?: {
      deflections_per_game?: number;
      screen_assist_pts_per_game?: number;
      charges_drawn_per_game?: number;
    };
    lineup_rotation_profiles?: {
      top_5man_lineups_evaluated?: number;
      best_net_lineup?: any;
      leakiest_net_lineup?: any;
      primary_lineups?: any[];
    };
  };
  possession_ledger: {
    total_extra_possessions?: number;
    possession_margin_per_game?: number;
  };
  game_flow_and_rest: {
    quarter_splits?: any;
    rest_advantage_profile?: any;
  };
  scheme_profile: {
    three_point_attempt_rate?: number;
    free_throw_attempt_rate?: number;
  };
  percentile_ranks?: Record<string, number | null>;
}

// ---------------------------------------------------------------------------\
// Tier 3: Pre-sorted Leaderboards (~35 KB)
// ---------------------------------------------------------------------------\
export interface LeaderboardEntry {
  rank: number;
  player_id: number;
  player_name: string;
  team_abbrev: string;
  position: PositionGroup;
  headshot_url: string;
  value: number;
  secondary_label?: string;
  secondary_value?: number | string;
}

export interface SeasonLeaderboards {
  season: string;
  categories: {
    net_epm: LeaderboardEntry[];
    offensive_epm: LeaderboardEntry[];
    defensive_epm: LeaderboardEntry[];
    self_creation_rate: LeaderboardEntry[];
    rim_pressure_rate: LeaderboardEntry[];
    smoe_per_100: LeaderboardEntry[];
    true_ast_pct: LeaderboardEntry[];
    deflections_per_100: LeaderboardEntry[];
    screen_assist_pts_per_100: LeaderboardEntry[];
    true_shooting_pct: LeaderboardEntry[];
  };
}

// ---------------------------------------------------------------------------\
// Tier 4: Head-to-Head Matchup Prediction (~5 KB)
// ---------------------------------------------------------------------------\
export interface MatchupSimulation {
  matchup_id: string;
  home_team: TeamIdentity;
  away_team: TeamIdentity;
  predicted_pace: number;
  home_win_probability: number;
  away_win_probability: number;
  predicted_score: {
    home: number;
    away: number;
    margin: number;
    total_points?: number;
  };
  tactical_clashes: {
    rim_pressure_vs_denial: {
      home_rim_rate?: number;
      away_rim_denial?: number;
      edge: 'home' | 'away' | 'even';
    };
    perimeter_spacing_clash: {
      home_3pt_rate?: number;
      edge: 'home' | 'away' | 'even';
    };
    possession_turnover_battle?: {
      home_poss_margin?: number;
      away_poss_margin?: number;
      edge: 'home' | 'away' | 'even';
    };
    possession_turnover_war?: {
      edge: 'home' | 'away' | 'even';
    };
  };
}