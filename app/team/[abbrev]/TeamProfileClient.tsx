"use client";

import { useState } from "react";
import { TeamFullProfile } from "@/types/analytics";
import { Shield, Zap, Crosshair } from "lucide-react";

export default function TeamProfileClient({ team }: { team: TeamFullProfile }) {
  const [activeTab, setActiveTab] = useState<"overview" | "defense" | "lineups" | "chemistry">("overview");
  const elo = team.elo_ratings || {}; const ratings = team.ratings || {}; const ff = team.four_factors || {};
  const def = team.defensive_spatial_suppression || {}; const lineups = team.hustle_and_rotations?.lineup_rotation_profiles || {};

  return (
    <div className="space-y-6">
      <div className="overflow-hidden rounded-2xl border border-surface-border bg-surface p-6 sm:p-8 relative" style={{ background: `linear-gradient(135deg, ${team.colors?.primary || "#38BDF8"}15 0%, #111827 70%)` }}>
        <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-6">
            <img src={team.logo_url} alt={team.team_abbrev} className="h-20 w-20 object-contain drop-shadow-md" />
            <div className="space-y-1 text-center sm:text-left">
              <div className="flex items-center justify-center sm:justify-start gap-2">
                <h1 className="text-2xl sm:text-3xl font-black text-white">{team.team_name}</h1>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-surface-elevated text-gray-300 border border-surface-border">{team.team_abbrev}</span>
              </div>
              <p className="text-xs font-mono text-gray-400">{team.conference}ern Conference · {team.division} Division · {team.games_played} Games Evaluated</p>
            </div>
          </div>
          <div className="flex items-center gap-4 bg-surface-elevated/80 border border-surface-border rounded-xl p-4 font-mono text-center">
            <div><div className="text-[10px] text-gray-400">OFFENSE</div><div className="text-lg font-bold text-white">{ratings.offensive_rating ?? "-"}</div></div>
            <div className="h-8 w-px bg-surface-border" />
            <div><div className="text-[10px] text-gray-400">DEFENSE</div><div className="text-lg font-bold text-white">{ratings.defensive_rating ?? "-"}</div></div>
            <div className="h-8 w-px bg-surface-border" />
            <div><div className="text-[10px] text-gray-400">NET RTG</div><div className={`text-lg font-black ${ratings.net_rating > 0 ? "text-emerald" : "text-crimson"}`}>{ratings.net_rating ? (ratings.net_rating > 0 ? `+${ratings.net_rating.toFixed(1)}` : ratings.net_rating.toFixed(1)) : "-"}</div></div>
            <div className="h-8 w-px bg-surface-border" />
            <div><div className="text-[10px] text-gray-400">POWER INDEX</div><div className="text-lg font-bold text-white">{elo.overall_elo?.toFixed(1) || "-"}</div></div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 border-b border-surface-border pb-2 overflow-x-auto text-xs font-mono">
        {[{ id: "overview", label: "Four Factors & Ratings" }, { id: "defense", label: "Defensive Leaks" }, { id: "lineups", label: "5-Man Lineup Synergy" }].map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id as any)} className={`rounded-lg px-4 py-2 transition-colors ${activeTab === tab.id ? "bg-amber-400 text-black font-bold" : "bg-surface border border-surface-border text-gray-400 hover:text-white hover:bg-surface-elevated"}`}>{tab.label}</button>
        ))}
      </div>

      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-xs">
            <MetricCard label="PACE" value={team.pace} subtitle="Possessions / 48m" />
            <MetricCard label="POSSESSION MARGIN" value={team.possession_ledger?.possession_margin_per_game ? `${team.possession_ledger.possession_margin_per_game > 0 ? "+" : ""}${team.possession_ledger.possession_margin_per_game} Poss` : "-"} subtitle="OREB - TOV Advantage" />
            <MetricCard label="3PT ATTEMPT RATE" value={team.scheme_profile?.three_point_attempt_rate ? `${(team.scheme_profile.three_point_attempt_rate * 100).toFixed(1)}%` : "-"} subtitle="Of Total Shot Diet" />
            <MetricCard label="SHOT MAKING (VS EXP)" value={ff.smoe_per_100 ? `${ff.smoe_per_100 > 0 ? "+" : ""}${ff.smoe_per_100.toFixed(1)} PTS` : "-"} subtitle="Per 100 Shots" />
          </div>
          <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2"><Crosshair className="h-4 w-4 text-accent" /> Base Four Factors</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="border-b border-surface-border bg-surface-elevated text-gray-400">
                  <tr><th className="px-4 py-2.5">Factor</th><th className="px-4 py-2.5 text-right">Offense</th><th className="px-4 py-2.5 text-right">Defense (Opponent)</th><th className="px-4 py-2.5 text-right">Net Advantage</th></tr>
                </thead>
                <tbody className="divide-y divide-surface-border/50 text-gray-300">
                  <tr>
                    <td className="px-4 py-3 font-semibold text-white">Effective Field Goal %</td><td className="px-4 py-3 text-right">{ff.offensive_effective_fg_pct ? `${(ff.offensive_effective_fg_pct * 100).toFixed(1)}%` : "-"}</td><td className="px-4 py-3 text-right">{ff.defensive_four_factors?.opp_effective_fg_pct ? `${(ff.defensive_four_factors.opp_effective_fg_pct * 100).toFixed(1)}%` : "-"}</td><td className="px-4 py-3 text-right font-bold text-accent">{ff.offensive_effective_fg_pct && ff.defensive_four_factors?.opp_effective_fg_pct ? `${((ff.offensive_effective_fg_pct - ff.defensive_four_factors.opp_effective_fg_pct) * 100).toFixed(1)}%` : "-"}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === "defense" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono text-xs">
            <div className="rounded-xl border border-surface-border bg-surface p-5 space-y-2"><div className="text-gray-400">PAINT FUNNEL RATE</div><div className="text-2xl font-black text-accent">{def.opponent_paint_funnel_rate ? `${(def.opponent_paint_funnel_rate * 100).toFixed(1)}%` : "-"}</div><p className="text-[11px] text-gray-500">Percentage of paint attacks forced into low-efficiency floaters instead of layups.</p></div>
            <div className="rounded-xl border border-surface-border bg-surface p-5 space-y-2"><div className="text-gray-400">RIM DENIAL</div><div className="text-2xl font-black text-emerald">{def.rim_denial_efficiency ? `${def.rim_denial_efficiency > 0 ? "+" : ""}${(def.rim_denial_efficiency * 100).toFixed(1)}%` : "-"}</div><p className="text-[11px] text-gray-500">How successfully the defense suppresses rim attempt frequency below league average.</p></div>
          </div>
          <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2"><Shield className="h-4 w-4 text-emerald" /> Defensive Zone Containment</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="border-b border-surface-border bg-surface-elevated text-gray-400">
                  <tr><th className="px-4 py-2.5">Court Zone</th><th className="px-4 py-2.5 text-right">Opp FGA</th><th className="px-4 py-2.5 text-right">Opp FG%</th><th className="px-4 py-2.5 text-right">Baseline FG%</th><th className="px-4 py-2.5 text-right">Status</th></tr>
                </thead>
                <tbody className="divide-y divide-surface-border/50 text-gray-300">
                  {Object.entries(def.defensive_hot_cold_allowed || {}).map(([zone, data]: [string, any]) => {
                    const isLeak = data.status === "DEFENSIVE_LEAK";
                    return (
                      <tr key={zone} className="hover:bg-surface-elevated/30 transition-colors">
                        <td className="px-4 py-2.5 font-semibold text-white">{zone}</td>
                        <td className="px-4 py-2.5 text-right">{data.opp_attempts}</td>
                        <td className="px-4 py-2.5 text-right font-bold">{(data.opp_fg_pct * 100).toFixed(1)}%</td>
                        <td className="px-4 py-2.5 text-right text-gray-400">{(data.baseline_fg_pct * 100).toFixed(1)}%</td>
                        <td className="px-4 py-2.5 text-right"><span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${isLeak ? "bg-crimson/10 text-crimson border border-crimson/30" : "bg-emerald/10 text-emerald border border-emerald/30"}`}>{isLeak ? "LEAK ALLOWED" : "CONTAINED"}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === "lineups" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-3 font-mono text-xs"><h3 className="text-sm font-bold text-emerald flex items-center gap-2 border-b border-surface-border pb-3"><Zap className="h-4 w-4" /> Most Dominant 5-Man Unit</h3>{lineups?.best_net_lineup ? (<div className="space-y-2"><div className="text-white font-bold text-sm">{lineups.best_net_lineup.lineup_name}</div><div className="flex justify-between text-gray-400"><span>Minutes: {lineups.best_net_lineup.minutes}</span><span>Plus/Minus: <strong className="text-emerald">+{lineups.best_net_lineup.plus_minus}</strong></span></div><div className="flex justify-between text-gray-400"><span>Net Rating / 48m:</span><span className="text-emerald font-black text-sm">+{lineups.best_net_lineup.net_rating_per_48}</span></div></div>) : <p className="text-gray-500">No qualified lineup data.</p>}</div>
          <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-3 font-mono text-xs"><h3 className="text-sm font-bold text-crimson flex items-center gap-2 border-b border-surface-border pb-3"><Shield className="h-4 w-4" /> Leakiest 5-Man Unit</h3>{lineups?.leakiest_net_lineup ? (<div className="space-y-2"><div className="text-white font-bold text-sm">{lineups.leakiest_net_lineup.lineup_name}</div><div className="flex justify-between text-gray-400"><span>Minutes: {lineups.leakiest_net_lineup.minutes}</span><span>Plus/Minus: <strong className="text-crimson">{lineups.leakiest_net_lineup.plus_minus}</strong></span></div><div className="flex justify-between text-gray-400"><span>Net Rating / 48m:</span><span className="text-crimson font-black text-sm">{lineups.leakiest_net_lineup.net_rating_per_48}</span></div></div>) : <p className="text-gray-500">No qualified lineup data.</p>}</div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, subtitle }: { label: string; value: any; subtitle: string }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface p-4">
      <div className="text-[10px] text-gray-400 tracking-wider truncate">{label}</div>
      <div className="text-xl font-black text-white mt-1">{value}</div>
      <div className="text-[10px] text-gray-500 mt-0.5">{subtitle}</div>
    </div>
  );
}