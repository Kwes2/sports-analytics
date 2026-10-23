"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();

  const links = [
    { name: "Players", href: "/" },
    { name: "Teams", href: "/teams" },
    { name: "Games", href: "/games" },
  ];

  return (
    <nav className="border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-white font-medium text-sm tracking-tight">
          <Activity className="w-4 h-4 text-zinc-400" />
          <span>CourtIQ</span>
        </Link>

        <div className="flex items-center space-x-6 text-xs font-mono">
          {links.map((link) => {
            const isActive = pathname === link.href || (link.href !== "/" && pathname.startsWith(link.href));
            return (
              <Link
                key={link.name}
                href={link.href}
                className={`transition-colors py-1 ${
                  isActive ? "text-white font-semibold border-b border-white" : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {link.name}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}