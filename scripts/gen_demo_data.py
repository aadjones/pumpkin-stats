#!/usr/bin/env python3
"""Generate mock nutrition data → data/demo.csv (default 30 rows)."""

import argparse
import csv
import datetime as dt
import pathlib
import random

# --- CLI --------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--rows", type=int, default=30, help="number of days")
args = parser.parse_args()

# --- output path ------------------------------------------------------------
out = pathlib.Path("data") / "demo.csv"
out.parent.mkdir(exist_ok=True)


# --- helpers ----------------------------------------------------------------
def clamp(val, low, high):
    return max(low, min(val, high))


# --- random-walk baselines --------------------------------------------------
today = dt.date.today()
kcal = 2200
protein_g = 120
carb_g = 260
fat_g = 70

with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "kcal", "protein", "carbs", "fat"])

    for i in range(args.rows):
        d = today - dt.timedelta(days=i)

        # ---- Calories: slow random walk ------------------------------------
        kcal = clamp(kcal + random.randint(-120, 120), 1500, 3100)

        # ---- Macros: independent noisy walks, slightly nudged by kcal ------
        # target macros scale with kcal but each gets ± random drift
        protein_target = kcal * 0.06
        carb_target = kcal * 0.12
        fat_target = kcal * 0.03

        protein_g = clamp(int(protein_g + random.randint(-8, 8) + 0.1 * (protein_target - protein_g)), 40, 200)
        carb_g = clamp(int(carb_g + random.randint(-12, 12) + 0.1 * (carb_target - carb_g)), 100, 400)
        fat_g = clamp(int(fat_g + random.randint(-5, 5) + 0.1 * (fat_target - fat_g)), 20, 120)

        w.writerow([d.isoformat(), kcal, protein_g, carb_g, fat_g])

print(f"✅  Wrote {args.rows} rows → {out}")
