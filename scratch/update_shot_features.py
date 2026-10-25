import os

filepath = os.path.join("scripts", "features", "shot_features.py")
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read().replace("\r\n", "\n")

if 'sys.stdout.reconfigure' not in content:
    content = content.replace(
        'logger = logging.getLogger("ShotFeatures")',
        'if hasattr(sys.stdout, "reconfigure"):\n    sys.stdout.reconfigure(encoding="utf-8")\n\nlogger = logging.getLogger("ShotFeatures")'
    )

# 1. Update Accumulator __init__
old_init = '''        # Spatial Distribution
        self.zones_fga = defaultdict(int)
        self.zones_fgm = defaultdict(int)'''

new_init = '''        # Spatial Distribution & Hex Density Bins
        self.zones_fga = defaultdict(int)
        self.zones_fgm = defaultdict(int)
        self.spatial_bins = defaultdict(lambda: {"fga": 0, "fgm": 0, "fg3m": 0, "pts": 0})'''

content = content.replace(old_init, new_init)

# 2. Update record_shot signature and logic
old_record = '''    def record_shot(
        self,
        is_made: int,
        is_3pt: int,
        zone_basic: str,
        action_type: str,
        period: int,
        min_rem: int,
        sec_rem: int,
        zone_xpps: float,
    ) -> None:'''

new_record = '''    def record_shot(
        self,
        is_made: int,
        is_3pt: int,
        zone_basic: str,
        action_type: str,
        period: int,
        min_rem: int,
        sec_rem: int,
        zone_xpps: float,
        loc_x: Optional[float] = None,
        loc_y: Optional[float] = None,
    ) -> None:'''

content = content.replace(old_record, new_record)

# Add binning inside record_shot
old_rec_body = '''        # Rim
        if zone_basic == "Restricted Area":'''

new_rec_body = '''        # 2D Hex Density Binning (~2 ft grid cells)
        if loc_x is not None and loc_y is not None:
            bx = int(round(float(loc_x) / 20.0) * 20)
            by = int(round(float(loc_y) / 20.0) * 20)
            self.spatial_bins[(bx, by)]["fga"] += 1
            self.spatial_bins[(bx, by)]["fgm"] += is_made
            self.spatial_bins[(bx, by)]["fg3m"] += (1 if is_3pt and is_made else 0)
            self.spatial_bins[(bx, by)]["pts"] += pts

        # Rim
        if zone_basic == "Restricted Area":'''

content = content.replace(old_rec_body, new_rec_body)

# 3. Add density_bins to compile()
old_compile = '''        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "team_id": self.team_id,'''

new_compile = '''        # Compile density bins
        density_bins = [
            {
                "x": bx,
                "y": by,
                "fga": stats["fga"],
                "fgm": stats["fgm"],
                "fg_pct": round(stats["fgm"] / stats["fga"], 3),
                "efg_pct": round((stats["fgm"] + 0.5 * stats["fg3m"]) / stats["fga"], 3),
            }
            for (bx, by), stats in sorted(self.spatial_bins.items(), key=lambda item: item[1]["fga"], reverse=True)
        ]

        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "team_id": self.team_id,
            "density_bins": density_bins,'''

content = content.replace(old_compile, new_compile)

# 4. Pass loc_x and loc_y in process_season_shots
old_call = '''            # Player Accumulator
            if pid not in player_acc:
                player_acc[pid] = ShotFeatureAccumulator(entity_id=pid, name=pname, team_id=tid)
            player_acc[pid].record_shot(
                is_made, is_3pt, zone_basic, action_type, period, min_rem, sec_rem, xpps
            )

            # Team Accumulator
            if tid not in team_acc:
                team_acc[tid] = ShotFeatureAccumulator(entity_id=tid, name=f"Team {tid}", team_id=tid)
            team_acc[tid].record_shot(
                is_made, is_3pt, zone_basic, action_type, period, min_rem, sec_rem, xpps
            )'''

new_call = '''            loc_x = shot.get("LOC_X")
            loc_y = shot.get("LOC_Y")

            # Player Accumulator
            if pid not in player_acc:
                player_acc[pid] = ShotFeatureAccumulator(entity_id=pid, name=pname, team_id=tid)
            player_acc[pid].record_shot(
                is_made, is_3pt, zone_basic, action_type, period, min_rem, sec_rem, xpps, loc_x, loc_y
            )

            # Team Accumulator
            if tid not in team_acc:
                team_acc[tid] = ShotFeatureAccumulator(entity_id=tid, name=f"Team {tid}", team_id=tid)
            team_acc[tid].record_shot(
                is_made, is_3pt, zone_basic, action_type, period, min_rem, sec_rem, xpps, loc_x, loc_y
            )'''

content = content.replace(old_call, new_call)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("shot_features.py updated with pre-binned shot hexmaps successfully.")
