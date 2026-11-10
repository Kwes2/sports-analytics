import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

FIA_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


def format_laptime(seconds: float) -> str:
    if pd.isna(seconds) or seconds <= 0:
        return "N/A"
    minutes = int(seconds // 60)
    rem = seconds % 60
    return f"{minutes}:{rem:06.3f}"


def estimate_fuel_burn(laps_df: pd.DataFrame) -> float:
    clean = laps_df[(~laps_df["is_pit_lap"]) & (laps_df["lap_duration"].notna())].copy()
    if len(clean) < 30:
        return 0.035
    clean["dur_c"] = clean["lap_duration"] - clean.groupby("driver_number")["lap_duration"].transform("mean")
    clean["lap_c"] = clean["lap_number"] - clean.groupby("driver_number")["lap_number"].transform("mean")
    coeff, _, _, _ = np.linalg.lstsq(clean[["lap_c"]].values, clean["dur_c"].values, rcond=None)
    return max(0.015, -float(coeff[0]))


def compute_subset_stats(subset_df: pd.DataFrame, d_name_map: dict, d_team_map: dict, finish_map: dict):
    drivers_data = []

    for d_num, d_laps in subset_df.groupby("driver_number"):
        raw = d_laps["lap_duration"].dropna().values
        fuel = d_laps["fuel_corr_lap"].dropna().values

        if len(raw) == 0:
            continue

        raw_avg = float(np.mean(raw))
        raw_med = float(np.median(raw))
        fuel_avg = float(np.mean(fuel))
        fuel_med = float(np.median(fuel))

        drivers_data.append({
            "driver_number": int(d_num),
            "code": d_name_map.get(d_num, str(d_num)),
            "team": d_team_map.get(d_num, "N/A"),
            "finish_position": finish_map.get(d_num, 99),
            "laps_counted": len(raw),
            "raw_avg": raw_avg,
            "raw_med": raw_med,
            "fuel_avg": fuel_avg,
            "fuel_med": fuel_med,
        })

    if not drivers_data:
        return []

    drivers_data = sorted(drivers_data, key=lambda x: x["finish_position"])

    min_raw_avg = min(d["raw_avg"] for d in drivers_data)
    min_fuel_avg = min(d["fuel_avg"] for d in drivers_data)
    min_raw_med = min(d["raw_med"] for d in drivers_data)
    min_fuel_med = min(d["fuel_med"] for d in drivers_data)

    for d in drivers_data:
        d["raw_avg_formatted"] = format_laptime(d["raw_avg"])
        d["raw_avg_gap"] = round(d["raw_avg"] - min_raw_avg, 3)
        d["raw_avg_pct"] = round(((d["raw_avg"] - min_raw_avg) / min_raw_avg) * 100, 3)

        d["fuel_avg_formatted"] = format_laptime(d["fuel_avg"])
        d["fuel_avg_gap"] = round(d["fuel_avg"] - min_fuel_avg, 3)
        d["fuel_avg_pct"] = round(((d["fuel_avg"] - min_fuel_avg) / min_fuel_avg) * 100, 3)

        d["raw_med_formatted"] = format_laptime(d["raw_med"])
        d["raw_med_gap"] = round(d["raw_med"] - min_raw_med, 3)
        d["raw_med_pct"] = round(((d["raw_med"] - min_raw_med) / min_raw_med) * 100, 3)

        d["fuel_med_formatted"] = format_laptime(d["fuel_med"])
        d["fuel_med_gap"] = round(d["fuel_med"] - min_fuel_med, 3)
        d["fuel_med_pct"] = round(((d["fuel_med"] - min_fuel_med) / min_fuel_med) * 100, 3)

    return drivers_data


def process_race(season: int, race_dir: Path):
    laps_file = race_dir / "laps.parquet"
    drivers_file = race_dir / "drivers.parquet"

    if not laps_file.exists():
        return None

    laps_df = pd.read_parquet(laps_file)
    drivers_df = pd.read_parquet(drivers_file) if drivers_file.exists() else pd.DataFrame()

    d_name_map = {}
    d_team_map = {}
    if not drivers_df.empty and "driver_number" in drivers_df.columns:
        for _, row in drivers_df.drop_duplicates("driver_number").iterrows():
            d_name_map[row["driver_number"]] = row.get("name_acronym", str(row["driver_number"]))
            d_team_map[row["driver_number"]] = row.get("team_name", "N/A")

    laps_df["lap_duration"] = pd.to_numeric(laps_df["lap_duration"], errors="coerce")
    laps_df["date_start"] = pd.to_datetime(laps_df["date_start"], format="ISO8601", utc=True, errors="coerce")

    valid_dates = laps_df["date_start"].dropna()
    race_date_str = valid_dates.min().strftime("%Y-%m-%d") if not valid_dates.empty else "2026-01-01"

    if "is_pit_lap" not in laps_df.columns:
        laps_df["is_pit_lap"] = laps_df.get("is_pit_out_lap", False).fillna(False)

    total_race_laps = int(laps_df["lap_number"].max())

    # Interval Gap
    sorted_df = laps_df.sort_values(by=["lap_number", "date_start"]).copy()
    sorted_df["gap_ahead"] = 999.0
    for _, grp in sorted_df.groupby("lap_number"):
        t_arr = grp["date_start"].values
        diffs = np.diff(t_arr) / np.timedelta64(1, "s")
        sorted_df.loc[grp.index, "gap_ahead"] = [999.0] + list(diffs)

    laps_df["gap_ahead"] = sorted_df["gap_ahead"]
    laps_df["in_traffic"] = (laps_df["gap_ahead"] >= 0.1) & (laps_df["gap_ahead"] <= 1.6)

    med_pace = laps_df["lap_duration"].median()
    laps_df["is_neutralized"] = laps_df["lap_duration"] > (med_pace * 1.15)

    # Fuel Correction
    beta_fuel = estimate_fuel_burn(laps_df)
    laps_df["fuel_offset"] = beta_fuel * (total_race_laps - laps_df["lap_number"])
    laps_df["fuel_corr_lap"] = laps_df["lap_duration"] - laps_df["fuel_offset"]

    last_laps = laps_df.sort_values(by=["lap_number", "date_start"], ascending=[False, True])
    finish_df = last_laps.drop_duplicates(subset="driver_number", keep="first").reset_index(drop=True)
    finish_map = {row["driver_number"]: idx + 1 for idx, row in finish_df.iterrows()}

    # 3 Views
    view_all = laps_df[laps_df["lap_duration"].notna()].copy()
    view_clean = laps_df[
        (laps_df["lap_number"] > 1) &
        (~laps_df["is_pit_lap"]) &
        (~laps_df["is_neutralized"]) &
        (laps_df["lap_duration"].notna())
    ].copy()
    view_no_traffic = view_clean[~view_clean["in_traffic"]].copy()

    race_doc = {
        "season": season,
        "race_slug": race_dir.name,
        "race_name": race_dir.name.replace("_", " ").title(),
        "date": race_date_str,
        "total_laps": total_race_laps,
        "fuel_burn_rate": round(beta_fuel, 4),
        "views": {
            "all_laps": compute_subset_stats(view_all, d_name_map, d_team_map, finish_map),
            "clean_laps": compute_subset_stats(view_clean, d_name_map, d_team_map, finish_map),
            "no_traffic_laps": compute_subset_stats(view_no_traffic, d_name_map, d_team_map, finish_map),
        }
    }

    return race_doc


def compile_season_driver_averages(all_race_docs: list, output_dir: Path):
    """
    Normalizes pace gaps across the entire season for each view toggle.
    Calculates driver mean % deficit to fastest across all completed races.
    """
    view_keys = ["all_laps", "clean_laps", "no_traffic_laps"]
    season_views = {}

    for vk in view_keys:
        driver_accum = {}

        for race in all_race_docs:
            drivers = race["views"].get(vk, [])
            for d in drivers:
                d_num = d["driver_number"]
                if d_num not in driver_accum:
                    driver_accum[d_num] = {
                        "driver_number": d_num,
                        "code": d["code"],
                        "team": d["team"],
                        "races_counted": 0,
                        "raw_avg_gaps": [],
                        "raw_avg_pcts": [],
                        "fuel_avg_gaps": [],
                        "fuel_avg_pcts": [],
                        "raw_med_gaps": [],
                        "raw_med_pcts": [],
                        "fuel_med_gaps": [],
                        "fuel_med_pcts": [],
                    }
                rec = driver_accum[d_num]
                rec["races_counted"] += 1
                rec["raw_avg_gaps"].append(d["raw_avg_gap"])
                rec["raw_avg_pcts"].append(d["raw_avg_pct"])
                rec["fuel_avg_gaps"].append(d["fuel_avg_gap"])
                rec["fuel_avg_pcts"].append(d["fuel_avg_pct"])
                rec["raw_med_gaps"].append(d["raw_med_gap"])
                rec["raw_med_pcts"].append(d["raw_med_pct"])
                rec["fuel_med_gaps"].append(d["fuel_med_gap"])
                rec["fuel_med_pcts"].append(d["fuel_med_pct"])

        # Aggregate averages
        view_standings = []
        for d_num, rec in driver_accum.items():
            if rec["races_counted"] < 3:  # Skip single-race fill-ins
                continue

            view_standings.append({
                "driver_number": d_num,
                "code": rec["code"],
                "team": rec["team"],
                "races_counted": rec["races_counted"],
                # Mean Gap in Seconds
                "avg_raw_gap_sec": round(float(np.mean(rec["raw_avg_gaps"])), 3),
                "avg_fuel_gap_sec": round(float(np.mean(rec["fuel_avg_gaps"])), 3),
                "avg_med_gap_sec": round(float(np.mean(rec["raw_med_gaps"])), 3),
                "avg_fuel_med_gap_sec": round(float(np.mean(rec["fuel_med_gaps"])), 3),
                # Normalized Mean % Deficit (The Pure Ranking Metric)
                "pct_raw_avg": round(float(np.mean(rec["raw_avg_pcts"])), 2),
                "pct_fuel_avg": round(float(np.mean(rec["fuel_avg_pcts"])), 2),
                "pct_raw_med": round(float(np.mean(rec["raw_med_pcts"])), 2),
                "pct_fuel_med": round(float(np.mean(rec["fuel_med_pcts"])), 2),
            })

        # Rank by Fuel Corrected Median % Deficit (Standard golden benchmark)
        view_standings = sorted(view_standings, key=lambda x: x["pct_fuel_med"])
        for idx, item in enumerate(view_standings, start=1):
            item["season_rank"] = idx

        season_views[vk] = view_standings

    # Save to JSON
    with open(output_dir / "season_driver_averages.json", "w") as f:
        json.dump(season_views, f, indent=2)

    print(f"[+] Saved season driver averages to {output_dir / 'season_driver_averages.json'}")


def main():
    parser = argparse.ArgumentParser(description="Build web dataset with season-level normalized averages.")
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    season_dir = project_root / "data" / str(args.season)

    output_dir = season_dir / "processed"
    races_out_dir = output_dir / "races"
    races_out_dir.mkdir(parents=True, exist_ok=True)

    race_dirs = sorted([d for d in season_dir.iterdir() if d.is_dir() and d.name != "processed" and (d / "laps.parquet").exists()])
    print(f"Building Web Dataset for {len(race_dirs)} rounds in {args.season}...")

    all_race_docs = []
    races_summary = []

    for idx, race_dir in enumerate(race_dirs, start=1):
        race_doc = process_race(args.season, race_dir)
        if race_doc:
            race_file = races_out_dir / f"{race_doc['race_slug']}.json"
            with open(race_file, "w") as f:
                json.dump(race_doc, f, indent=2)

            races_summary.append({
                "round": idx,
                "race_slug": race_doc["race_slug"],
                "race_name": race_doc["race_name"],
                "date": race_doc["date"],
                "total_laps": race_doc["total_laps"],
                "fuel_burn_rate": race_doc["fuel_burn_rate"],
            })
            all_race_docs.append(race_doc)

    # Chronological sort
    races_summary = sorted(races_summary, key=lambda x: x["date"])
    for idx, r in enumerate(races_summary, start=1):
        r["round"] = idx

    with open(output_dir / "races_summary.json", "w") as f:
        json.dump(races_summary, f, indent=2)

    # Compile Season Averages
    if all_race_docs:
        compile_season_driver_averages(all_race_docs, output_dir)

    print("[Done] Pipeline complete.")


if __name__ == "__main__":
    main()