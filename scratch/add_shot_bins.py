with open('scripts/build_analytics_store.py', 'r', encoding='utf-8') as f:
    c = f.read().replace('\r\n', '\n')

old_p = '"hot_cold_zones": p_sp.get("hot_cold_zones", {}),'
new_p = '"hot_cold_zones": p_sp.get("hot_cold_zones", {}),\n                "shot_density_bins": p_shot.get("density_bins", []),'
c = c.replace(old_p, new_p)

old_t = '"smoe_per_100": t_st.get("smoe_per_100"),'
new_t = '"smoe_per_100": t_st.get("smoe_per_100"),\n                "shot_density_bins": t_st.get("density_bins", []),'
c = c.replace(old_t, new_t)

with open('scripts/build_analytics_store.py', 'w', encoding='utf-8') as f:
    f.write(c)

print('Added shot_density_bins successfully')
