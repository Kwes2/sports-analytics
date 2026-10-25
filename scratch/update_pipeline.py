with open('scripts/run_pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read().replace('\r\n', '\n')

old_stages = '''            ("Stage 2J: PBP Momentum, Runs & Droughts", "scripts/features/momentum_and_runs.py"),
            ("Stage 2K: Hustle Tracking & 5-Man Lineups", "scripts/features/hustle_and_lineups.py"),
            ("Stage 3: Analytics Store & Dual Percentiles", "scripts/build_analytics_store.py"),
        ])'''

new_stages = '''            ("Stage 2J: PBP Momentum, Runs & Droughts", "scripts/features/momentum_and_runs.py"),
            ("Stage 2K: Hustle Tracking & 5-Man Lineups", "scripts/features/hustle_and_lineups.py"),
            ("Stage 2L: ML Archetypes & Player Similarities", "scripts/features/archetypes.py"),
            ("Stage 3: Tiered Analytics Store & Partitioning", "scripts/build_analytics_store.py"),
            ("Stage 4: Head-to-Head Matchup Simulations", "scripts/features/matchup_simulator.py"),
        ])'''

content = content.replace(old_stages, new_stages)

# Also update --only-synthesis
old_synth = '''    if args.only_synthesis:
        stages_to_run = [
            ("Stage 3: Analytics Store & Dual Percentiles", "scripts/build_analytics_store.py")
        ]'''

new_synth = '''    if args.only_synthesis:
        stages_to_run = [
            ("Stage 2L: ML Archetypes & Player Similarities", "scripts/features/archetypes.py"),
            ("Stage 3: Tiered Analytics Store & Partitioning", "scripts/build_analytics_store.py"),
            ("Stage 4: Head-to-Head Matchup Simulations", "scripts/features/matchup_simulator.py"),
        ]'''

content = content.replace(old_synth, new_synth)

with open('scripts/run_pipeline.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated run_pipeline.py successfully.")
