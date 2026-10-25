// app/leaderboards/LeaderboardsClient.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { SeasonLeaderboards } from "@/types/analytics";
import { Trophy, Award, Zap, Shield, Target, Crosshair, Users, Activity, Flame } from "lucide-react";

interface CategoryMeta {
  key: string;
  label: string;
  unit: string;
  description: string;
  icon: any;
  format: (v: number) => string;
}

const CATEGORIES: CategoryMeta[] = [
  {
    key: "net_epm",
    label: "Net EPM (Total Impact)",
    unit: "EPM",
    description: "Ridge Regularized Adjusted Plus-Minus per 100 possessions.",
    icon: Trophy,
    format: (v) => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)),
  },
  {
    key: "offensive_epm",
    label: "Offensive EPM",
    unit: "OEPM",
    description: "Isolated individual offensive scoring impact per 100 possessions.",
    icon: Zap,
    format: (v) => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)),
  },
  {
    key: "defensive_epm",
    label: "Defensive EPM",
    unit: "DEPM",
    description: "Isolated individual defensive suppression impact per 100 possessions.",
    icon: Shield,
    format: (v) => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)),
  },
  {
    key: "self_creation_rate",
    label: "Self-Creation Rate",
    unit: "%",
    description: "Percentage of shot attempts created off the dribble.",
    icon: Target,
    format: (v) => `${(v * 100).toFixed(1)}%`,
  },
  {
    key: "rim_pressure_rate",
    label: "Rim Pressure Rate",
    unit: "%",
    description: "Share of field goal attempts taken in the restricted area.",
    icon: Flame,
    format: (v) => `${(v * 100).toFixed(1)}%`,
  },
  {
    key: "smoe_per_100",
    label: "SMOE / 100 Shots",
    unit: "PTS",
    description: "Shot Making Over Expected above 1,000-game spatial zone baseline.",
    icon: Crosshair,
    format: (v) => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)),
  },
  {
    key: "true_ast_pct",
    label: "True Assist % (Oliver)",
    unit: "%",
    description: "Percentage of teammate field goals assisted while on the court.",
    icon: Users,
    format: (v) => `${v.toFixed(1)}%`,
  },
  {
    key: "deflections_per_100",
    label: "Deflections / 100 Poss",
    unit: "DEF",
    description: "Perimeter ball disruption events scaled per 100 possessions.",
    icon: Activity,
    format: (v) => v.toFixed(1),
  },
  {
    key: "screen_assist_pts_per_100",
    label: "Screen Assist Points / 100",
    unit: "PTS",
    description: "Points created purely via off-ball and on-ball screening.",
    icon: Award,
    format: (v) => v.toFixed(1),
  },
  {
    key: "true_shooting_pct",
    label: "True Shooting %",
    unit: "%",
    description: "Points scored per true shooting attempt (PTS / 2*(FGA + 0.44*FTA)).",
    icon: Target,
    format: (v) => `${(v * 100).toFixed(1)}%`,
  },
];

export default function LeaderboardsClient({
  leaderboards,
}: {
  leaderboards: SeasonLeaderboards | null;
}) {
  const [selectedKey, setSelectedKey] = useState("net_epm");

  if (!leaderboards) {
    return <div className="text-gray-400 py-12 text-center">No leaderboards data available.</div>;
  }

  const activeCategory = CATEGORIES.find((c) => c.key === selectedKey) || CATEGORIES[0];
  const entries = (leaderboards.categories as any)[selectedKey] || [];

  return (
    <div className="space-y-6">
      {/* Category Pills */}
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          const isActive = cat.key === selectedKey;
          return (
            <button
              key={cat.key}
              onClick={() => setSelectedKey(cat.key)}
              className={`flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-mono transition-colors ${
                isActive
                  ? "bg-accent text-black font-bold shadow-md shadow-accent/10"
                  : "bg-surface border border-surface-border text-gray-400 hover:text-white hover:bg-surface-elevated"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{cat.label}</span>
            </button>
          );
        })}
      </div>

      {/* Category Header Card */}
      <div className="rounded-xl border border-surface-border bg-surface p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-black text-white">{activeCategory.label}</h2>
          <p className="text-xs text-gray-400 mt-0.5">{activeCategory.description}</p>
        </div>
        <span className="text-xs font-mono font-semibold text-accent bg-surface-elevated px-3 py-1.5 rounded-lg border border-surface-border w-fit">
          Top 20 Qualifiers
        </span>
      </div>

      {/* Leaderboard Table */}
      <div className="overflow-hidden rounded-xl border border-surface-border bg-surface">
        <table className="w-full text-left text-xs font-mono">
          <thead className="border-b border-surface-border bg-surface-elevated text-gray-400">
            <tr>
              <th className="px-4 py-3 w-16">Rank</th>
              <th className="px-4 py-3">Player</th>
              <th className="px-4 py-3">Team</th>
              <th className="px-4 py-3">Pos</th>
              <th className="px-6 py-3 text-right font-bold text-white">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/50 text-gray-300">
            {entries.map((entry: any, index: number) => {
              const isPodium = index < 3;
              return (
                <tr key={entry.player_id} className="hover:bg-surface-elevated/40 transition-colors">
                  <td className="px-4 py-3 font-bold">
                    <span
                      className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs ${
                        index === 0
                          ? "bg-gold text-black font-black"
                          : index === 1
                          ? "bg-gray-300 text-black font-bold"
                          : index === 2
                          ? "bg-amber-700 text-white font-bold"
                          : "text-gray-500"
                      }`}
                    >
                      {entry.rank}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-semibold text-white flex items-center gap-3">
                    <img
                      src={entry.headshot_url}
                      alt={entry.player_name}
                      className="h-8 w-8 rounded-full bg-surface-elevated object-cover border border-surface-border"
                      loading="lazy"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = "none";
                      }}
                    />
                    <Link
                      href={`/player/${entry.player_id}`}
                      className="hover:text-accent hover:underline font-bold"
                    >
                      {entry.player_name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-400">{entry.team_abbrev}</td>
                  <td className="px-4 py-3 text-gray-400">{entry.position}</td>
                  <td className="px-6 py-3 text-right font-black text-sm text-accent">
                    {activeCategory.format(entry.value)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}