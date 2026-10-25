// app/simulator/SimulatorClient.tsx
"use client";

import { useState } from "react";
import { TeamIndexItem, MatchupSimulation } from "@/types/analytics";
import { Crosshair, Trophy, Zap, Shield, Flame } from "lucide-react";

export default function SimulatorClient({
  teams,
  initialSimulation,
}: {
  teams: TeamIndexItem[];
  initialSimulation: MatchupSimulation | null;
}) {
  const [homeAbbrev, setHomeAbbrev] = useState<string>("BOS");
  const [awayAbbrev, setAwayAbbrev] = useState<string>("LAL");
  const [simulation, setSimulation] = useState<MatchupSimulation | null>(initialSimulation);

  const handleSimulate = (home: string, away: string) => {
    if (home === away) return;
    setHomeAbbrev(home);
    setAwayAbbrev(away);

    const homeTeam = teams.find((t) => t.team_abbrev === home);
    const awayTeam = teams.find((t) => t.team_abbrev === away);

    if (homeTeam && awayTeam) {
      const leaguePace = 98.0;
      const leagueOrtg = 115.0;

      const expPace = (homeTeam.pace * awayTeam.pace) / leaguePace;
      const projHomeOrtg = homeTeam.offensive_rating + (awayTeam.defensive_rating - leagueOrtg) + 1.8;
      const projAwayOrtg = awayTeam.offensive_rating + (homeTeam.defensive_rating - leagueOrtg);

      const projHomePts = Math.round(((projHomeOrtg * expPace) / 100) * 10) / 10;
      const projAwayPts = Math.round(((projAwayOrtg * expPace) / 100) * 10) / 10;

      const eloDiff = homeTeam.overall_elo + 65.0 - awayTeam.overall_elo;
      const homeWinProb = Math.round((1.0 / (1.0 + Math.pow(10, -eloDiff / 400))) * 1000) / 1000;

      setSimulation({
        matchup_id: `${home}_vs_${away}`,
        home_team: {
          team_id: homeTeam.team_id,
          team_name: homeTeam.team_name,
          team_abbrev: homeTeam.team_abbrev,
          overall_elo: homeTeam.overall_elo,
        } as any,
        away_team: {
          team_id: awayTeam.team_id,
          team_name: awayTeam.team_name,
          team_abbrev: awayTeam.team_abbrev,
          overall_elo: awayTeam.overall_elo,
        } as any,
        predicted_pace: Math.round(expPace * 10) / 10,
        home_win_probability: homeWinProb,
        away_win_probability: Math.round((1.0 - homeWinProb) * 1000) / 1000,
        predicted_score: {
          home: projHomePts,
          away: projAwayPts,
          margin: Math.round((projHomePts - projAwayPts) * 10) / 10,
        },
        tactical_clashes: {
          rim_pressure_vs_denial: {
            edge: homeWinProb > 0.55 ? "home" : "away",
          } as any,
          perimeter_spacing_clash: {
            edge: "home",
          } as any,
          possession_turnover_battle: {
            edge: "home",
          } as any,
        },
      });
    }
  };

  const homeWinPct = simulation ? Math.round(simulation.home_win_probability * 100) : 50;
  const awayWinPct = 100 - homeWinPct;

  return (
    <div className="space-y-8">
      {/* Team Selectors Bar */}
      <div className="rounded-2xl border border-surface-border bg-surface p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 items-center">
          {/* Away Team Picker */}
          <div className="space-y-2">
            <label className="text-xs font-mono font-bold text-gray-400 block">
              AWAY TEAM (VISITOR)
            </label>
            <select
              value={awayAbbrev}
              onChange={(e) => handleSimulate(homeAbbrev, e.target.value)}
              className="w-full rounded-xl border border-surface-border bg-surface-elevated p-3 text-sm font-mono font-bold text-white focus:border-accent focus:outline-none"
            >
              {teams.map((t) => (
                <option key={t.team_abbrev} value={t.team_abbrev} disabled={t.team_abbrev === homeAbbrev}>
                  {t.team_name} ({t.team_abbrev})
                </option>
              ))}
            </select>
          </div>

          {/* Home Team Picker */}
          <div className="space-y-2">
            <label className="text-xs font-mono font-bold text-gray-400 block">
              HOME TEAM (HOST)
            </label>
            <select
              value={homeAbbrev}
              onChange={(e) => handleSimulate(e.target.value, awayAbbrev)}
              className="w-full rounded-xl border border-surface-border bg-surface-elevated p-3 text-sm font-mono font-bold text-white focus:border-accent focus:outline-none"
            >
              {teams.map((t) => (
                <option key={t.team_abbrev} value={t.team_abbrev} disabled={t.team_abbrev === awayAbbrev}>
                  {t.team_name} ({t.team_abbrev})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {simulation && (
        <div className="space-y-6">
          {/* Projected Scoreboard */}
          <div className="rounded-2xl border border-surface-border bg-surface p-6 sm:p-8 space-y-6">
            <div className="flex items-center justify-between text-xs font-mono text-gray-400 border-b border-surface-border/80 pb-3">
              <span>SIMULATED MATCHUP</span>
              <span className="flex items-center gap-1.5 bg-surface-elevated px-2.5 py-1 rounded border border-surface-border text-white">
                <Zap className="h-3.5 w-3.5 text-amber-400" />
                Projected Pace: {simulation.predicted_pace}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 items-center text-center">
              {/* Away */}
              <div className="flex flex-col items-center space-y-2">
                <img
                  src={`https://cdn.nba.com/logos/nba/${simulation.away_team.team_id}/global/L/logo.svg`}
                  alt={simulation.away_team.team_abbrev}
                  className="h-16 w-16 object-contain"
                />
                <h3 className="text-lg font-black text-white">{simulation.away_team.team_name}</h3>
                <span className="text-xs font-mono text-gray-400">Elo: {simulation.away_team.overall_elo?.toFixed(1) || "-"}</span>
                <span className="text-3xl sm:text-4xl font-mono font-black text-white pt-2">
                  {simulation.predicted_score.away}
                </span>
              </div>

              {/* Spread & Margin */}
              <div className="space-y-2 font-mono">
                <div className="text-xs text-gray-400">PROJECTED SPREAD</div>
                <div className="text-2xl font-black text-accent">
                  {simulation.predicted_score.margin > 0
                    ? `${simulation.home_team.team_abbrev} -${simulation.predicted_score.margin}`
                    : `${simulation.away_team.team_abbrev} -${Math.abs(simulation.predicted_score.margin)}`}
                </div>
                <div className="text-xs text-gray-500">
                  Total: {Math.round(simulation.predicted_score.home + simulation.predicted_score.away)} PTS
                </div>
              </div>

              {/* Home */}
              <div className="flex flex-col items-center space-y-2">
                <img
                  src={`https://cdn.nba.com/logos/nba/${simulation.home_team.team_id}/global/L/logo.svg`}
                  alt={simulation.home_team.team_abbrev}
                  className="h-16 w-16 object-contain"
                />
                <h3 className="text-lg font-black text-white">{simulation.home_team.team_name}</h3>
                <span className="text-xs font-mono text-gray-400">Elo: {simulation.home_team.overall_elo?.toFixed(1) || "-"}</span>
                <span className="text-3xl sm:text-4xl font-mono font-black text-white pt-2">
                  {simulation.predicted_score.home}
                </span>
              </div>
            </div>

            {/* Win Probability Bar */}
            <div className="space-y-2 pt-4 border-t border-surface-border font-mono text-xs">
              <div className="flex justify-between font-bold">
                <span className="text-gray-300">{simulation.away_team.team_abbrev} {awayWinPct}%</span>
                <span className="text-gray-400">WIN PROBABILITY</span>
                <span className="text-accent">{simulation.home_team.team_abbrev} {homeWinPct}%</span>
              </div>
              <div className="h-3 w-full rounded-full bg-surface-elevated overflow-hidden flex">
                <div className="h-full bg-gray-500 transition-all duration-500" style={{ width: `${awayWinPct}%` }} />
                <div className="h-full bg-accent transition-all duration-500" style={{ width: `${homeWinPct}%` }} />
              </div>
            </div>
          </div>

          {/* Tactical Clashes */}
          <div className="rounded-2xl border border-surface-border bg-surface p-6 space-y-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Crosshair className="h-4 w-4 text-accent" /> Key Tactical Clashes
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-xs">
              <div className="p-4 rounded-xl bg-surface-elevated border border-surface-border space-y-1">
                <div className="text-gray-400 flex items-center gap-1.5"><Flame className="h-3.5 w-3.5 text-crimson" /> The Rim Battle</div>
                <div className="text-sm font-bold text-white mt-1">Rim Pressure vs Denial</div>
                <div className="text-accent font-semibold pt-1">
                  Advantage: {simulation.tactical_clashes?.rim_pressure_vs_denial?.edge === "home" ? simulation.home_team.team_abbrev : simulation.away_team.team_abbrev}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-surface-elevated border border-surface-border space-y-1">
                <div className="text-gray-400 flex items-center gap-1.5"><Zap className="h-3.5 w-3.5 text-amber-400" /> Perimeter Spacing</div>
                <div className="text-sm font-bold text-white mt-1">3PT Creation War</div>
                <div className="text-accent font-semibold pt-1">
                  Advantage: {simulation.tactical_clashes?.perimeter_spacing_clash?.edge === "home" ? simulation.home_team.team_abbrev : simulation.away_team.team_abbrev}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-surface-elevated border border-surface-border space-y-1">
                <div className="text-gray-400 flex items-center gap-1.5"><Shield className="h-3.5 w-3.5 text-emerald" /> Possession Ledger</div>
                <div className="text-sm font-bold text-white mt-1">Rebound & Turnover War</div>
                <div className="text-accent font-semibold pt-1">
                  Advantage: {(simulation.tactical_clashes as any)?.possession_turnover_battle?.edge === "home" || (simulation.tactical_clashes as any)?.possession_turnover_war?.edge === "home" ? simulation.home_team.team_abbrev : simulation.away_team.team_abbrev}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}