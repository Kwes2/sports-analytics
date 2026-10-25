// app/player/[id]/PlayerProfileClient.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { PlayerFullProfile } from "@/types/analytics";
import {
  Trophy,
  Zap,
  Shield,
  Target,
  Crosshair,
  Activity,
  Users,
  Flame,
  Clock,
  Sparkles,
} from "lucide-react";

export default function PlayerProfileClient({
  player,
}: {
  player: PlayerFullProfile;
}) {
  const [activeTab, setActiveTab] = useState<"overview" | "shooting" | "playmaking" | "context">("overview");
  const [percentileMode, setPercentileMode] = useState<"league" | "position">("league");

  const epm = player.effective_plus_minus;
  const oliver = player.oliver_floor_rates;
  const shotMaking = player.shot_making_and_creation;
  const passer = player.assist_network_profile?.passer_profile;
  const finisher = player.assist_network_profile?.finisher_profile;
  const volatility = player.consistency_and_schedule?.volatility_profile;
  const rest = player.consistency_and_schedule?.schedule_rest_splits;
  const archetype = player.archetype;
  const similar = player.similar_players || [];

  const lwRanks = player.percentile_ranks?.league_wide || {};
  const posRanks = player.percentile_ranks?.positional_peer || ({} as any);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="overflow-hidden rounded-2xl border border-surface-border bg-surface p-6 sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col sm:flex-row items-center gap-6 text-center sm:text-left">
            <img
              src={player.headshot_url}
              alt={player.player_name}
              className="h-24 w-24 rounded-full bg-surface-elevated object-cover border-2 border-surface-border shadow-lg"
              onError={(e) => {
                (e.target as HTMLElement).style.display = "none";
              }}
            />
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
                <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
                  {player.player_name}
                </h1>
                <span className="font-mono text-xs px-2.5 py-0.5 rounded bg-surface-elevated text-gray-300 border border-surface-border">
                  {player.team_abbrev} · {player.position}
                </span>
              </div>
              <div className="text-xs font-mono text-gray-400 flex flex-wrap items-center justify-center sm:justify-start gap-3">
                <span>Height: {player.bio.height || "-"}</span>
                <span>Weight: {player.bio.weight ? `${player.bio.weight} lbs` : "-"}</span>
                <span>Age: {player.bio.age || "-"}</span>
                <span>Games: {player.games_played}</span>
                <span>MPG: {player.minutes_per_game}</span>
              </div>
              {/* Archetype Badges */}
              {archetype && (
                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 pt-1">
                  <span className="inline-flex items-center gap-1 rounded-md bg-accent/10 border border-accent/30 px-2.5 py-1 text-xs font-mono font-bold text-accent">
                    <Sparkles className="h-3 w-3" /> {archetype.offensive_role}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-md bg-emerald/10 border border-emerald/30 px-2.5 py-1 text-xs font-mono font-bold text-emerald">
                    <Shield className="h-3 w-3" /> {archetype.defensive_role}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Quick EPM Metric Badge */}
          <div className="flex items-center justify-center gap-4 bg-surface-elevated/70 border border-surface-border rounded-xl p-4 font-mono text-center">
            <div>
              <div className="text-[10px] text-gray-400 tracking-wider">OFF EPM</div>
              <div className="text-lg font-bold text-accent">
                {epm.offensive_epm ? (epm.offensive_epm > 0 ? `+${epm.offensive_epm.toFixed(1)}` : epm.offensive_epm.toFixed(1)) : "-"}
              </div>
            </div>
            <div className="h-8 w-px bg-surface-border" />
            <div>
              <div className="text-[10px] text-gray-400 tracking-wider">DEF EPM</div>
              <div className="text-lg font-bold text-emerald">
                {epm.defensive_epm ? (epm.defensive_epm > 0 ? `+${epm.defensive_epm.toFixed(1)}` : epm.defensive_epm.toFixed(1)) : "-"}
              </div>
            </div>
            <div className="h-8 w-px bg-surface-border" />
            <div>
              <div className="text-[10px] text-gray-400 tracking-wider">NET EPM</div>
              <div className="text-xl font-black text-amber-400">
                {epm.net_epm ? (epm.net_epm > 0 ? `+${epm.net_epm.toFixed(1)}` : epm.net_epm.toFixed(1)) : "-"}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-surface-border pb-2 overflow-x-auto text-xs font-mono">
        {[
          { id: "overview", label: "Overview & Percentiles" },
          { id: "shooting", label: "Shot Chart & Hexbins" },
          { id: "playmaking", label: "Assist Network & Synergy" },
          { id: "context", label: "Volatility & Comps" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`rounded-lg px-4 py-2 transition-colors ${
              activeTab === tab.id
                ? "bg-accent text-black font-bold"
                : "bg-surface border border-surface-border text-gray-400 hover:text-white hover:bg-surface-elevated"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Overview & Percentiles */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Per-100 Possession Boxscore Cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 font-mono">
            <StatCard label="PTS / 100" value={player.per_100_possessions.points} accent />
            <StatCard label="AST / 100" value={player.per_100_possessions.assists} />
            <StatCard label="REB / 100" value={player.per_100_possessions.rebounds} />
            <StatCard label="TRUE SHOOTING" value={player.true_shooting_pct ? `${(player.true_shooting_pct * 100).toFixed(1)}%` : "-"} />
            <StatCard label="USAGE RATE" value={`${player.usage_pct}%`} />
            <StatCard label="AST / TOV" value={player.ast_tov_ratio.toFixed(2)} />
          </div>

          {/* Percentiles Matrix */}
          <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-gold" /> Empirical Percentile Ranks (0 to 100th)
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Empirical rankings free of arbitrary fantasy weights.
                </p>
              </div>

              {/* Mode Toggle */}
              <div className="flex items-center gap-1 bg-surface-elevated p-1 rounded-lg border border-surface-border font-mono text-xs">
                <button
                  onClick={() => setPercentileMode("league")}
                  className={`px-3 py-1 rounded transition-colors ${
                    percentileMode === "league" ? "bg-accent text-black font-bold" : "text-gray-400 hover:text-white"
                  }`}
                >
                  League-Wide
                </button>
                <button
                  onClick={() => setPercentileMode("position")}
                  className={`px-3 py-1 rounded transition-colors ${
                    percentileMode === "position" ? "bg-accent text-black font-bold" : "text-gray-400 hover:text-white"
                  }`}
                >
                  vs {player.position}s
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <PercentileBar label="True Shooting %" value={percentileMode === "league" ? lwRanks.true_shooting : posRanks.true_shooting} />
              <PercentileBar label="Net EPM (Total Impact)" value={percentileMode === "league" ? lwRanks.net_epm : posRanks.net_epm} />
              <PercentileBar label="Rim Pressure Rate" value={percentileMode === "league" ? lwRanks.rim_pressure_rate : posRanks.rim_pressure} />
              <PercentileBar label="Playmaking Load (True AST%)" value={percentileMode === "league" ? lwRanks.true_ast_pct : posRanks.playmaking_load} />
              <PercentileBar label="Usage Rate" value={percentileMode === "league" ? lwRanks.usage : posRanks.usage_to_efficiency_ratio} />
              <PercentileBar label="Defensive Rebounding" value={percentileMode === "league" ? lwRanks.true_dreb_pct : posRanks.rebound_dominance} />
              <PercentileBar label="Self-Creation Rate" value={lwRanks.self_creation_rate} />
              <PercentileBar label="Stock Rate (STL+BLK)" value={lwRanks.stock_rate} />
            </div>
          </div>

          {/* Oliver True Floor Rates */}
          <div className="rounded-xl border border-surface-border bg-surface p-6">
            <h3 className="text-base font-bold text-white mb-4">Dean Oliver Floor Share Rates</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-xs">
              <div className="p-3 bg-surface-elevated rounded-lg border border-surface-border">
                <div className="text-gray-400">TRUE AST%</div>
                <div className="text-lg font-bold text-accent mt-1">{oliver.true_ast_pct ? `${oliver.true_ast_pct.toFixed(1)}%` : "-"}</div>
              </div>
              <div className="p-3 bg-surface-elevated rounded-lg border border-surface-border">
                <div className="text-gray-400">OFF REB%</div>
                <div className="text-lg font-bold text-white mt-1">{oliver.true_orb_pct ? `${oliver.true_orb_pct.toFixed(1)}%` : "-"}</div>
              </div>
              <div className="p-3 bg-surface-elevated rounded-lg border border-surface-border">
                <div className="text-gray-400">DEF REB%</div>
                <div className="text-lg font-bold text-white mt-1">{oliver.true_dreb_pct ? `${oliver.true_dreb_pct.toFixed(1)}%` : "-"}</div>
              </div>
              <div className="p-3 bg-surface-elevated rounded-lg border border-surface-border">
                <div className="text-gray-400">FOUL DRAW (FTA/PF)</div>
                <div className="text-lg font-bold text-amber-400 mt-1">{oliver.foul_drawing_premium ? oliver.foul_drawing_premium.toFixed(2) : "-"}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Shooting & 2D Court Density Hexbin Chart */}
      {activeTab === "shooting" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 2D Court Density Canvas/SVG */}
            <div className="lg:col-span-2 rounded-xl border border-surface-border bg-surface p-6 flex flex-col items-center">
              <div className="w-full flex items-center justify-between border-b border-surface-border pb-3 mb-4">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Target className="h-4 w-4 text-accent" /> 2D Spatial Shot Density Bins
                </h3>
                <span className="text-xs font-mono text-gray-400">
                  {shotMaking.shot_density_bins?.length || 0} Spatial Grid Cells
                </span>
              </div>

              {/* Regulation Half-Court SVG representation */}
              <div className="relative w-full max-w-[500px] aspect-[500/470] bg-[#0c121d] rounded-xl border border-surface-border overflow-hidden p-2">
                <svg viewBox="-250 -50 500 470" className="w-full h-full">
                  {/* Court Lines */}
                  <rect x="-250" y="-50" width="500" height="470" fill="none" stroke="#1f2937" strokeWidth="2" />
                  {/* Key */}
                  <rect x="-80" y="-50" width="160" height="190" fill="none" stroke="#28344a" strokeWidth="2" />
                  {/* Restricted Area */}
                  <path d="M -40 -10 A 40 40 0 0 0 40 -10" fill="none" stroke="#28344a" strokeWidth="2" />
                  {/* 3PT Line */}
                  <path d="M -220 -50 L -220 90 A 237.5 237.5 0 0 0 220 90 L 220 -50" fill="none" stroke="#28344a" strokeWidth="2" />
                  {/* Rim */}
                  <circle cx="0" cy="0" r="7.5" fill="none" stroke="#f59e0b" strokeWidth="2" />

                  {/* Density Bins */}
                  {shotMaking.shot_density_bins?.map((bin, i) => {
                    const radius = Math.min(18, Math.max(4, Math.sqrt(bin.fga) * 2.8));
                    // Color based on efg_pct
                    const isHot = bin.efg_pct >= 0.55;
                    const isCold = bin.efg_pct <= 0.40;
                    const fill = isHot ? "#ef4444" : isCold ? "#38bdf8" : "#94a3b8";

                    return (
                      <circle
                        key={i}
                        cx={bin.x}
                        cy={bin.y}
                        r={radius}
                        fill={fill}
                        opacity={0.7}
                        className="transition-all hover:opacity-100 hover:stroke-white hover:stroke-2 cursor-pointer"
                      >
                        <title>{`${bin.fga} FGA (${(bin.efg_pct * 100).toFixed(1)}% eFG)`}</title>
                      </circle>
                    );
                  })}
                </svg>
              </div>

              <div className="flex items-center gap-6 mt-4 text-xs font-mono text-gray-400">
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-crimson" /> Above Average (Hot)</span>
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-slate-400" /> Neutral</span>
                <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-accent" /> Below Average (Cold)</span>
              </div>
            </div>

            {/* Creation & Finishing Summary */}
            <div className="space-y-4">
              <div className="rounded-xl border border-surface-border bg-surface p-5 space-y-3 font-mono text-xs">
                <h4 className="font-bold text-white text-sm pb-2 border-b border-surface-border">Shot Creation Profile</h4>
                <div className="flex justify-between">
                  <span className="text-gray-400">Self-Creation Rate:</span>
                  <span className="font-bold text-white">{shotMaking.creation_profile?.self_creation_rate ? `${(shotMaking.creation_profile.self_creation_rate * 100).toFixed(1)}%` : "-"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Creation Efficiency Tax:</span>
                  <span className="text-amber-400">{shotMaking.creation_profile?.creation_efficiency_tax ? `${(shotMaking.creation_profile.creation_efficiency_tax * 100).toFixed(1)}%` : "-"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Rim Pressure Rate:</span>
                  <span className="font-bold text-white">{shotMaking.rim_pressure?.rim_pressure_rate ? `${(shotMaking.rim_pressure.rim_pressure_rate * 100).toFixed(1)}%` : "-"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Rim Finishing Premium:</span>
                  <span className="text-emerald">{shotMaking.rim_pressure?.rim_finishing_premium ? `${(shotMaking.rim_pressure.rim_finishing_premium * 100).toFixed(1)}%` : "-"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">SMOE / 100 Shots:</span>
                  <span className="font-bold text-accent">{shotMaking.smoe_per_100 ? `${shotMaking.smoe_per_100 > 0 ? "+" : ""}${shotMaking.smoe_per_100.toFixed(1)} PTS` : "-"}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Playmaking & Assist Network */}
      {activeTab === "playmaking" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Top Targets */}
          <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-surface-border pb-3">
              <Users className="h-4 w-4 text-accent" /> Top Assisted Targets (Who they feed)
            </h3>
            {passer?.top_assisted_targets?.length ? (
              <div className="space-y-3 font-mono text-xs">
                {passer.top_assisted_targets.map((t, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-surface-elevated border border-surface-border">
                    <span className="text-white font-semibold">{t.target_name}</span>
                    <span className="text-accent font-bold">{t.assists_received} Assists</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-500 font-mono">No target feeds recorded.</p>
            )}

            <div className="pt-3 border-t border-surface-border/60 text-xs font-mono space-y-2">
              <div className="flex justify-between text-gray-400">
                <span>Points Generated Per Assist:</span>
                <span className="text-white font-bold">{passer?.points_per_assist ? `${passer.points_per_assist} PTS` : "-"}</span>
              </div>
              <div className="flex justify-between text-gray-400">
                <span>3PT Assist Share:</span>
                <span className="text-white">{passer?.three_pt_assist_share ? `${(passer.three_pt_assist_share * 100).toFixed(1)}%` : "-"}</span>
              </div>
            </div>
          </div>

          {/* Primary Feeders */}
          <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-surface-border pb-3">
              <Zap className="h-4 w-4 text-gold" /> Primary Feeders (Who sets them up)
            </h3>
            {finisher?.primary_feeders?.length ? (
              <div className="space-y-3 font-mono text-xs">
                {finisher.primary_feeders.map((f, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-surface-elevated border border-surface-border">
                    <span className="text-white font-semibold">{f.feeder_name}</span>
                    <span className="text-gold font-bold">{f.feeds_delivered} Feeds Received</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-500 font-mono">No feeder passes recorded.</p>
            )}

            <div className="pt-3 border-t border-surface-border/60 text-xs font-mono">
              <div className="flex justify-between text-gray-400">
                <span>Total Points Scored Off Assists:</span>
                <span className="text-white font-bold">{finisher?.points_from_assists || 0} PTS</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Context, Volatility & Comps */}
      {activeTab === "context" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Scoring Floor & Ceiling */}
            <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-4 font-mono text-xs">
              <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-surface-border pb-3">
                <Activity className="h-4 w-4 text-emerald" /> Scoring Volatility & Consistency
              </h3>
              <div className="flex justify-between">
                <span className="text-gray-400">Scoring Volatility Index (SVI):</span>
                <span className="text-white font-bold">{volatility?.scoring_volatility_index_svi ?? "-"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Scoring Floor (10th Percentile):</span>
                <span className="text-emerald font-bold">{volatility?.scoring_floor_pts_100 ? `${volatility.scoring_floor_pts_100} PTS/100` : "-"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Scoring Ceiling (90th Percentile):</span>
                <span className="text-amber-400 font-bold">{volatility?.scoring_ceiling_pts_100 ? `${volatility.scoring_ceiling_pts_100} PTS/100` : "-"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Sub-Zero Game Rate (TS &lt; 50%):</span>
                <span className="text-crimson font-bold">{volatility?.sub_zero_game_rate ? `${(volatility.sub_zero_game_rate * 100).toFixed(1)}%` : "-"}</span>
              </div>
            </div>

            {/* Schedule & Rest Splits */}
            <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-4 font-mono text-xs">
              <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-surface-border pb-3">
                <Clock className="h-4 w-4 text-accent" /> Schedule & Rest Degradation
              </h3>
              <div className="flex justify-between">
                <span className="text-gray-400">Back-to-Back Degradation (B2B ΔTS%):</span>
                <span className={rest?.b2b_degradation_ts && rest.b2b_degradation_ts < 0 ? "text-crimson font-bold" : "text-emerald font-bold"}>
                  {rest?.b2b_degradation_ts ? `${(rest.b2b_degradation_ts * 100).toFixed(1)}%` : "-"}
                </span>
              </div>
              <p className="text-[11px] text-gray-500 pt-2">
                Measures true shooting efficiency drop-off on 0 days rest compared to 2+ days of rest.
              </p>
            </div>
          </div>

          {/* Similar Players Comps */}
          {similar.length > 0 && (
            <div className="rounded-xl border border-surface-border bg-surface p-6 space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2 border-b border-surface-border pb-3">
                <Sparkles className="h-4 w-4 text-gold" /> Similar Players (Cosine Vector Match)
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {similar.map((comp) => (
                  <Link
                    key={comp.player_id}
                    href={`/player/${comp.player_id}`}
                    className="flex items-center gap-3 p-3 rounded-lg bg-surface-elevated border border-surface-border hover:border-accent transition-colors"
                  >
                    <img
                      src={comp.headshot_url}
                      alt={comp.player_name}
                      className="h-10 w-10 rounded-full bg-surface object-cover border border-surface-border"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = "none";
                      }}
                    />
                    <div>
                      <div className="text-xs font-bold text-white">{comp.player_name}</div>
                      <div className="text-[10px] font-mono text-accent font-semibold">{comp.similarity_score_pct}% Match</div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: any; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface p-4">
      <div className="text-[10px] text-gray-400 tracking-wider truncate">{label}</div>
      <div className={`text-xl font-black mt-1 ${accent ? "text-accent" : "text-white"}`}>
        {value ?? "-"}
      </div>
    </div>
  );
}

function PercentileBar({ label, value }: { label: string; value?: number | null }) {
  const val = value ?? 0;
  const color = val >= 75 ? "bg-amber-400" : val >= 50 ? "bg-accent" : "bg-gray-500";

  return (
    <div className="space-y-1 font-mono text-xs">
      <div className="flex justify-between">
        <span className="text-gray-300">{label}</span>
        <span className="font-bold text-white">{value !== null && value !== undefined ? `${value.toFixed(0)}th` : "-"}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-surface-elevated overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${Math.min(100, Math.max(0, val))}%` }} />
      </div>
    </div>
  );
}