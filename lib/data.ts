// lib/data.ts
import fs from "fs";
import path from "path";
import Database from "better-sqlite3";
import {
  PlayerIndexItem,
  TeamIndexItem,
  PlayerFullProfile,
  TeamFullProfile,
  MatchupSimulation,
} from "@/types/analytics";

const DB_PATH = path.join(process.cwd(), "data", "nba_analytics.db");

function getDb() {
  return new Database(DB_PATH, { readonly: true });
}

export const DEFAULT_SEASON = "2026-27";

const TEAM_DICT: Record<number, { name: string; abbrev: string }> = {
  1610612737: { name: "Atlanta Hawks", abbrev: "ATL" },
  1610612738: { name: "Boston Celtics", abbrev: "BOS" },
  1610612751: { name: "Brooklyn Nets", abbrev: "BKN" },
  1610612766: { name: "Charlotte Hornets", abbrev: "CHA" },
  1610612741: { name: "Chicago Bulls", abbrev: "CHI" },
  1610612739: { name: "Cleveland Cavaliers", abbrev: "CLE" },
  1610612742: { name: "Dallas Mavericks", abbrev: "DAL" },
  1610612743: { name: "Denver Nuggets", abbrev: "DEN" },
  1610612765: { name: "Detroit Pistons", abbrev: "DET" },
  1610612744: { name: "Golden State Warriors", abbrev: "GSW" },
  1610612745: { name: "Houston Rockets", abbrev: "HOU" },
  1610612754: { name: "Indiana Pacers", abbrev: "IND" },
  1610612746: { name: "LA Clippers", abbrev: "LAC" },
  1610612747: { name: "Los Angeles Lakers", abbrev: "LAL" },
  1610612763: { name: "Memphis Grizzlies", abbrev: "MEM" },
  1610612748: { name: "Miami Heat", abbrev: "MIA" },
  1610612749: { name: "Milwaukee Bucks", abbrev: "MIL" },
  1610612750: { name: "Minnesota Timberwolves", abbrev: "MIN" },
  1610612740: { name: "New Orleans Pelicans", abbrev: "NOP" },
  1610612752: { name: "New York Knicks", abbrev: "NYK" },
  1610612760: { name: "Oklahoma City Thunder", abbrev: "OKC" },
  1610612753: { name: "Orlando Magic", abbrev: "ORL" },
  1610612755: { name: "Philadelphia 76ers", abbrev: "PHI" },
  1610612756: { name: "Phoenix Suns", abbrev: "PHX" },
  1610612757: { name: "Portland Trail Blazers", abbrev: "POR" },
  1610612758: { name: "Sacramento Kings", abbrev: "SAC" },
  1610612759: { name: "San Antonio Spurs", abbrev: "SAS" },
  1610612761: { name: "Toronto Raptors", abbrev: "TOR" },
  1610612762: { name: "Utah Jazz", abbrev: "UTA" },
  1610612764: { name: "Washington Wizards", abbrev: "WAS" },
};

// ---------------------------------------------------------------------------
// Tier 1: Directory Indexes
// ---------------------------------------------------------------------------
export function getPlayersIndex(season = DEFAULT_SEASON): PlayerIndexItem[] {
  const db = getDb();
  try {
    const stmt = db.prepare(`
      SELECT player_id, player_name, team_id, team_abbrev, position, 
             headshot_url, games_played, minutes_per_game, usage_pct, 
             true_shooting_pct, pts_per_100, ast_per_100, reb_per_100, 
             net_epm, offensive_epm, defensive_epm, archetype, full_profile_json
      FROM players 
      WHERE season = ?
      ORDER BY net_epm DESC
    `);
    const rows = stmt.all(season) as any[];
    return rows.map((r) => {
      const full = JSON.parse(r.full_profile_json || "{}");
      return {
        player_id: r.player_id,
        player_name: r.player_name,
        team_id: r.team_id,
        team_abbrev: r.team_abbrev,
        position: r.position,
        headshot_url: r.headshot_url,
        games_played: r.games_played,
        minutes_per_game: r.minutes_per_game,
        usage_pct: r.usage_pct,
        true_shooting_pct: r.true_shooting_pct,
        effective_fg_pct: full.effective_fg_pct || null,
        pts_per_100: r.pts_per_100,
        ast_per_100: r.ast_per_100,
        reb_per_100: r.reb_per_100,
        net_epm: r.net_epm,
        offensive_epm: r.offensive_epm,
        defensive_epm: r.defensive_epm,
        archetype: r.archetype,
        percentile_ranks: full.percentile_ranks?.league_wide || {
          net_epm: null,
          true_shooting: null,
          rim_pressure: null,
          self_creation: null,
        },
      };
    });
  } finally {
    db.close();
  }
}

export function getTeamsIndex(season = DEFAULT_SEASON): TeamIndexItem[] {
  const db = getDb();
  try {
    const stmt = db.prepare(`
      SELECT team_id, team_name, team_abbrev, conference, division, 
             games_played, pace, offensive_rating, defensive_rating, net_rating, 
             overall_elo, offensive_elo, defensive_elo
      FROM teams 
      WHERE season = ?
      ORDER BY net_rating DESC
    `);
    const rows = stmt.all(season) as any[];
    return rows.map((r) => ({
      ...r,
      logo_url: `https://cdn.nba.com/logos/nba/${r.team_id}/global/L/logo.svg`,
      colors: { primary: "#000000", secondary: "#FFFFFF" },
      percentile_ranks: { net_rating: null, overall_elo: null, rim_denial: null },
    }));
  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Tier 2: Deep Entity Profiles
// ---------------------------------------------------------------------------
export function getPlayerProfile(id: string | number, season = DEFAULT_SEASON): PlayerFullProfile | null {
  const db = getDb();
  try {
    const stmt = db.prepare(`SELECT full_profile_json FROM players WHERE player_id = ? AND season = ?`);
    const row = stmt.get(id, season) as any;
    if (!row) return null;
    return JSON.parse(row.full_profile_json) as PlayerFullProfile;
  } finally {
    db.close();
  }
}

export function getTeamProfile(abbrev: string, season = DEFAULT_SEASON): TeamFullProfile | null {
  const db = getDb();
  try {
    const stmt = db.prepare(`SELECT * FROM teams WHERE team_abbrev = ? AND season = ?`);
    const row = stmt.get(abbrev.toUpperCase(), season) as any;
    if (!row) return null;
    return {
      ...row,
      logo_url: `https://cdn.nba.com/logos/nba/${row.team_id}/global/L/logo.svg`,
      colors: { primary: "#38BDF8", secondary: "#161F30" },
      ratings: {
        offensive_rating: row.offensive_rating,
        defensive_rating: row.defensive_rating,
        net_rating: row.net_rating,
      },
      elo_ratings: {
        offensive_elo: row.offensive_elo,
        defensive_elo: row.defensive_elo,
        overall_elo: row.overall_elo,
      },
      four_factors: {},
      defensive_spatial_suppression: {},
      playmaking_and_chemistry: {},
      momentum_and_runs: {},
      lead_volatility: {},
      hustle_and_rotations: {},
      possession_ledger: {},
      game_flow_and_rest: {},
      scheme_profile: {},
    } as TeamFullProfile;
  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Tier 4: Matchup Projections
// ---------------------------------------------------------------------------
export function getMatchupSimulation(homeAbbrev: string, awayAbbrev: string, season = DEFAULT_SEASON): MatchupSimulation | null {
  const teams = getTeamsIndex(season);
  const home = teams.find((t) => t.team_abbrev === homeAbbrev.toUpperCase());
  const away = teams.find((t) => t.team_abbrev === awayAbbrev.toUpperCase());

  if (!home || !away) return null;

  const leaguePace = 98.0;
  const leagueOrtg = 115.0;

  const expPace = (home.pace * away.pace) / leaguePace;
  const projHomeOrtg = home.offensive_rating + (away.defensive_rating - leagueOrtg) + 1.8;
  const projAwayOrtg = away.offensive_rating + (home.defensive_rating - leagueOrtg);

  const projHomePts = Math.round(((projHomeOrtg * expPace) / 100) * 10) / 10;
  const projAwayPts = Math.round(((projAwayOrtg * expPace) / 100) * 10) / 10;

  const eloDiff = home.overall_elo + 65.0 - away.overall_elo;
  const homeWinProb = Math.round((1.0 / (1.0 + Math.pow(10, -eloDiff / 400))) * 1000) / 1000;

  return {
    matchup_id: `${home.team_abbrev}_vs_${away.team_abbrev}`,
    home_team: home as any,
    away_team: away as any,
    predicted_pace: Math.round(expPace * 10) / 10,
    home_win_probability: homeWinProb,
    away_win_probability: Math.round((1.0 - homeWinProb) * 1000) / 1000,
    predicted_score: {
      home: projHomePts,
      away: projAwayPts,
      margin: Math.round((projHomePts - projAwayPts) * 10) / 10,
    },
    tactical_clashes: {
      rim_pressure_vs_denial: { edge: homeWinProb > 0.55 ? "home" : "away" },
      perimeter_spacing_clash: { edge: "home" },
      possession_turnover_battle: { edge: "home" },
    },
  };
}

// ---------------------------------------------------------------------------
// Game Logs & Games Feed (For Home Page & Game Detail)
// ---------------------------------------------------------------------------
export interface GameSummary {
  game_id: string;
  game_date: string;
  home_team: {
    id: number;
    abbrev: string;
    name: string;
    score: number;
    win: boolean;
  };
  away_team: {
    id: number;
    abbrev: string;
    name: string;
    score: number;
    win: boolean;
  };
  pace: number;
}

export function getGamesFeed(season = DEFAULT_SEASON): GameSummary[] {
  const db = getDb();
  try {
    const stmt = db.prepare(`
      SELECT game_id, team_id, matchup, game_date, pts, min, fga, fta, oreb, tov
      FROM game_logs
      WHERE season = ?
    `);
    const rows = stmt.all(season) as any[];
    if (!rows || rows.length === 0) return [];

    const gamesMap = new Map<string, any[]>();
    for (const r of rows) {
      if (!gamesMap.has(r.game_id)) gamesMap.set(r.game_id, []);
      gamesMap.get(r.game_id)!.push(r);
    }

    const summaries: GameSummary[] = [];

    for (const [gid, logs] of gamesMap.entries()) {
      const teamMap = new Map<number, any>();
      for (const l of logs) {
        if (!teamMap.has(l.team_id)) {
          teamMap.set(l.team_id, { pts: 0, matchup: l.matchup, date: l.game_date, fga: 0, fta: 0, oreb: 0, tov: 0, min: 0 });
        }
        const t = teamMap.get(l.team_id)!;
        t.pts += Number(l.pts || 0);
        t.fga += Number(l.fga || 0);
        t.fta += Number(l.fta || 0);
        t.oreb += Number(l.oreb || 0);
        t.tov += Number(l.tov || 0);
        t.min += Number(l.min || 0);
      }

      const tIds = Array.from(teamMap.keys());
      if (tIds.length < 2) continue;

      const tA = teamMap.get(tIds[0])!;
      const tB = teamMap.get(tIds[1])!;
      const isAHome = tA.matchup.includes("vs.");
      const homeT = isAHome ? tA : tB;
      const awayT = isAHome ? tB : tA;
      const homeId = isAHome ? tIds[0] : tIds[1];
      const awayId = isAHome ? tIds[1] : tIds[0];

      const homePoss = 0.96 * (homeT.fga + 0.44 * homeT.fta - homeT.oreb + homeT.tov);
      const pace = homeT.min > 0 ? (homePoss / (homeT.min / 5)) * 48 : 0;

      const homeMeta = TEAM_DICT[homeId] || { name: "Unknown", abbrev: "UNK" };
      const awayMeta = TEAM_DICT[awayId] || { name: "Unknown", abbrev: "UNK" };

      summaries.push({
        game_id: gid,
        game_date: homeT.date,
        home_team: { id: homeId, abbrev: homeMeta.abbrev, name: homeMeta.name, score: homeT.pts, win: homeT.pts > awayT.pts },
        away_team: { id: awayId, abbrev: awayMeta.abbrev, name: awayMeta.name, score: awayT.pts, win: awayT.pts > homeT.pts },
        pace: Math.round(pace * 10) / 10,
      });
    }

    summaries.sort((a, b) => b.game_date.localeCompare(a.game_date));
    return summaries;
  } finally {
    db.close();
  }
}

export function getSingleGameData(gameId: string, season = DEFAULT_SEASON) {
  const db = getDb();
  try {
    const stmt = db.prepare(`SELECT * FROM game_logs WHERE game_id = ? AND season = ?`);
    const boxscore = stmt.all(gameId, season) as any[];
    return {
      game_id: gameId,
      pbp_events: [],
      player_boxscore: boxscore,
    };
  } finally {
    db.close();
  }
}