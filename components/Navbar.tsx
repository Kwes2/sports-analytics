// components/Navbar.tsx
import Link from "next/link";
import { Activity, Users, Shield, Award, Crosshair } from "lucide-react";

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-surface-border bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10 border border-accent/30 text-accent font-bold">
            NBA
          </div>
          <div>
            <div className="text-base font-extrabold tracking-tight text-white flex items-center gap-1.5">
              ANALYTICS <span className="text-xs font-mono font-semibold px-1.5 py-0.5 rounded bg-surface-elevated text-accent border border-surface-border">PRO</span>
            </div>
            <div className="text-[10px] text-gray-400 font-mono tracking-wider">INTELLIGENCE PLATFORM</div>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="flex items-center gap-1 sm:gap-2">
          <Link
            href="/"
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold text-gray-300 transition-colors hover:bg-surface-elevated hover:text-white"
          >
            <Activity className="h-4 w-4 text-accent" />
            <span>Games Feed</span>
          </Link>

          <Link
            href="/players"
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold text-gray-300 transition-colors hover:bg-surface-elevated hover:text-white"
          >
            <Users className="h-4 w-4 text-emerald" />
            <span>Players</span>
          </Link>

          <Link
            href="/teams"
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold text-gray-300 transition-colors hover:bg-surface-elevated hover:text-white"
          >
            <Shield className="h-4 w-4 text-amber-400" />
            <span>Teams</span>
          </Link>

          <Link
            href="/leaderboards"
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold text-gray-300 transition-colors hover:bg-surface-elevated hover:text-white"
          >
            <Award className="h-4 w-4 text-gold" />
            <span>Leaderboards</span>
          </Link>

          <Link
            href="/simulator"
            className="hidden sm:flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold text-gray-300 transition-colors hover:bg-surface-elevated hover:text-white"
          >
            <Crosshair className="h-4 w-4 text-crimson" />
            <span>Matchup Sim</span>
          </Link>
        </nav>

        {/* Season Anchor Indicator */}
        <div className="hidden lg:flex items-center gap-2 font-mono text-xs text-gray-400">
          <span className="h-2 w-2 rounded-full bg-emerald animate-pulse" />
          <span>2026-27 ACTIVE</span>
        </div>
      </div>
    </header>
  );
}