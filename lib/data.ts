// lib/data.ts
import fs from "fs";
import path from "path";
import {
  PlayerIndexItem,
  TeamIndexItem,
  PlayerFullProfile,
  TeamFullProfile,
  SeasonLeaderboards,
  MatchupSimulation,
} from "@/types/analytics";

const DATA_DIR = path.join(process.cwd(), "data", "analytics");
const RAW_DIR = path.join(process.cwd(), "data", "raw");

export const DEFAULT_SEASON = "2026-27";

function readJsonFile<T>(filePath: string): T | null {
  try {
    if (!fs.existsSync(filePath)) return null;
    const raw = fs.readFileSync(filePath, "utf-8").trim();
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch (err) {
    console.error(`Error reading JSON file at ${filePath}:`, err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Tier 1: Directory Indexes
// ---------------------------------------------------------------------------
export function getPlayersIndex(season = DEFAULT_SEASON): PlayerIndexItem[] {
  const filePath = path.join(DATA_DIR, `players_index_${season}.json`);
  return readJsonFile<PlayerIndexItem[]>(filePath) || [];
}

export function getTeamsIndex(season = DEFAULT_SEASON): TeamIndexItem[] {
  const filePath = path.join(DATA_DIR, `teams_index_${season}.json`);
  return readJsonFile<TeamIndexItem[]>(filePath) || [];
}

// ---------------------------------------------------------------------------
// Tier 2: Deep Entity Profiles
// ---------------------------------------------------------------------------
export function getPlayerProfile(id: string | number, season = DEFAULT_SEASON): PlayerFullProfile | null {
  const filePath = path.join(DATA_DIR, "players", season, `${id}.json`);
  return readJsonFile<PlayerFullProfile>(filePath);
}

export function getTeamProfile(abbrev: string, season = DEFAULT_SEASON): TeamFullProfile | null {
  const filePath = path.join(DATA_DIR, "teams", season, `${abbrev.toUpperCase()}.json`);
  return readJsonFile<TeamFullProfile>(filePath);
}

// ---------------------------------------------------------------------------
// Tier 3: Leaderboards
// ---------------------------------------------------------------------------
export function getLeaderboards(season = DEFAULT_SEASON): SeasonLeaderboards | null {
  const filePath = path.join(DATA_DIR, `leaderboards_${season}.json`);
  return readJsonFile<SeasonLeaderboards>(filePath);
}

// ---------------------------------------------------------------------------
// Tier 4: Matchup Projections
// ---------------------------------------------------------------------------
export function getMatchupSimulation(homeAbbrev: string, awayAbbrev: string, season = DEFAULT_SEASON): MatchupSimulation | null {
  const matchupKey = `${homeAbbrev.toUpperCase()}_vs_${awayAbbrev.toUpperCase()}`;
  const filePath = path.join(DATA_DIR, "matchups", season, `${matchupKey}.json`);
  return readJsonFile<MatchupSimulation>(filePath);
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
  const filePath = path.join(RAW_DIR, "game_logs", `team_${season}.json`);
  const rawLogs = readJsonFile<any[]>(filePath);
  if (!rawLogs) return [];

  // Group team logs by GAME_ID
  const gamesMap = new Map<string, any[]>();
  for (const log of rawLogs) {
    const gid = String(log.GAME_ID);
    if (!gamesMap.has(gid)) gamesMap.set(gid, []);
    gamesMap.get(gid)!.push(log);
  }

  const summaries: GameSummary[] = [];

  for (const [gid, logs] of gamesMap.entries()) {
    if (logs.length < 2) continue;

    const teamA = logs[0];
    const teamB = logs[1];
    const isAHome = String(teamA.MATCHUP || "").includes("vs.");
    const homeLog = isAHome ? teamA : teamB;
    const awayLog = isAHome ? teamB : teamA;

    const homeScore = Number(homeLog.PTS || 0);
    const awayScore = Number(awayLog.PTS || 0);

    const homePoss = 0.96 * (homeLog.FGA + 0.44 * homeLog.FTA - homeLog.OREB + homeLog.TOV);
    const minPlayed = Number(homeLog.MIN || 240);
    const pace = (homePoss / (minPlayed / 5)) * 48;

    summaries.push({
      game_id: gid,
      game_date: String(homeLog.GAME_DATE || ""),
      home_team: {
        id: Number(homeLog.TEAM_ID),
        abbrev: String(homeLog.TEAM_ABBREVIATION),
        name: String(homeLog.TEAM_NAME),
        score: homeScore,
        win: homeScore > awayScore,
      },
      away_team: {
        id: Number(awayLog.TEAM_ID),
        abbrev: String(awayLog.TEAM_ABBREVIATION),
        name: String(awayLog.TEAM_NAME),
        score: awayScore,
        win: awayScore > homeScore,
      },
      pace: Math.round(pace * 10) / 10,
    });
  }

  // Sort newest games first
  summaries.sort((a, b) => (b.game_date > a.game_date ? 1 : -1));
  return summaries;
}

export function getSingleGameData(gameId: string, season = DEFAULT_SEASON) {
  const pbpPath = path.join(RAW_DIR, "pbp", season, `${gameId}.json`);
  const playerLogsPath = path.join(RAW_DIR, "game_logs", `player_${season}.json`);

  const pbpEvents = readJsonFile<any[]>(pbpPath) || [];
  const allPlayerLogs = readJsonFile<any[]>(playerLogsPath) || [];

  const boxscore = allPlayerLogs.filter((p) => String(p.GAME_ID) === gameId);

  return {
    game_id: gameId,
    pbp_events: pbpEvents,
    player_boxscore: boxscore,
  };
}