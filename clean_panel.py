"""
Clean the AHRF county-year panel of physicians, NPs, and PAs (2018-2023).

Input : data/raw/AHRF_allphys_NP_PA_panel_2018_2023.csv  (original analytic panel)
Output: data/AHRF_allphys_NP_PA_panel_2018_2023_clean.csv
        data/cleaning_log.csv

Every change is recorded in the cleaning log. Run: python clean_panel.py
"""
import numpy as np
import pandas as pd

RAW = "data/raw/AHRF_allphys_NP_PA_panel_2018_2023.csv"
OUT = "data/AHRF_allphys_NP_PA_panel_2018_2023_clean.csv"
LOG = "data/cleaning_log.csv"
RUCC23 = "data/reference/Ruralurbancontinuumcodes2023.csv"

log = []


def note(step, fips, years, change):
    log.append({"step": step, "fips": fips, "years": years, "change": change})


d = pd.read_csv(RAW, dtype={"fips_str": str})
d["fips"] = d["fips_str"].str.zfill(5)
n_raw = len(d)

# 1. Restrict to the 50 states and DC -----------------------------------------
terr = d["fips"].str[:2].isin(["60", "66", "69", "72", "78"])
for st, g in d[terr].groupby("state"):
    note("1 territories", f"{st} ({g.fips.nunique()} units)", "all", "dropped: outside 50 states + DC")
d = d[~terr].copy()

# 2. Drop empty rows for units that do not exist in the study period ------------
empty = ["02001", "02201", "02232", "02280", "51515", "51560"]
for f in empty:
    g = d[d.fips == f]
    note("2 defunct units", f, ",".join(map(str, g.year)),
         f"dropped: '{g.county.iloc[0]}' rows have no clinician counts and no population")
d = d[~d.fips.isin(empty)].copy()

# 3. Alaska: Valdez-Cordova (02261) split into Chugach (02063) + Copper River (02066)
#    in 2019. Recombine into 02261 for every year so the unit is constant and keeps
#    its RUCC code (9).
va = d[d.fips == "02261"].set_index("year")
split = d[d.fips.isin(["02063", "02066"])].groupby("year")[["population", "pcphys", "np", "pa", "phys_all"]].sum(min_count=1)
for yr in range(2020, 2024):
    if yr in split.index:
        va.loc[yr, "population"] = split.loc[yr, "population"]
        if yr >= 2021:  # counts moved to the new areas from 2021; 2020 counts are on 02261
            for c in ["pcphys", "np", "pa", "phys_all"]:
                va.loc[yr, c] = split.loc[yr, c]
va = va.reset_index()
d = pd.concat([d[~d.fips.isin(["02261", "02063", "02066"])], va], ignore_index=True)
note("3 Alaska", "02261", "2020-2023",
     "Chugach (02063) + Copper River (02066) summed into Valdez-Cordova (02261): population 2020-23, counts 2021-23; 02063/02066 rows removed")

# 4. Connecticut: in 2022-23 counts sit on the 8 legacy counties (no population) and
#    population sits on 9 planning regions (no counts). Keep the legacy counties and
#    impute their population as statewide planning-region total x county's 2021 share.
ct_old = d.fips.str[:2].eq("09") & d.fips.str[2].eq("0")
ct_new = d.fips.str[:2].eq("09") & ~d.fips.str[2].eq("0")
share21 = d[ct_old & (d.year == 2021)].set_index("fips")["population"]
share21 = share21 / share21.sum()
d["pop_imputed"] = False
for yr in [2022, 2023]:
    total = d.loc[ct_new & (d.year == yr), "population"].sum()
    for f, s in share21.items():
        m = (d.fips == f) & (d.year == yr)
        d.loc[m, "population"] = round(total * s)
        d.loc[m, "pop_imputed"] = True
    note("4 Connecticut", "09001-09015", str(yr),
         f"legacy-county population imputed from planning-region total ({int(total):,}) x 2021 county shares")
note("4 Connecticut", "09110-09190", "2022,2023", "dropped planning-region rows (population only, no counts)")
d = d[~ct_new].copy()

# 5. RUCC 2013 corrections (sensitivity classification; checked against a copy of the USDA ERS 2013 file) ---------
fix = {"08101": (3, "Pueblo, CO: invalid code 32"),
       "35039": (4, "Rio Arriba, NM: invalid code 45"),
       "08043": (4, "Fremont, CO: coded 5, USDA 2013 file lists 4")}
for f, (code, why) in fix.items():
    d.loc[d.fips == f, "rucc13"] = code
    note("5 RUCC", f, "all", f"rucc13 set to {code} ({why})")

# 6. Fill state / region for all rows from the state's other rows -------------------
st = d.dropna(subset=["state"]).drop_duplicates("fips").set_index("fips")["state"]
d["state"] = d["state"].fillna(d["fips"].map(st))
reg = d.dropna(subset=["region"]).groupby("state")["region"].agg(lambda s: s.mode().iloc[0])
d["region"] = d["state"].map(reg).astype(int)
d["region_name"] = d["region"].map({1: "Northeast", 2: "Midwest", 3: "South", 4: "West"})

# 6b. Add 2023 RUCC (USDA ERS 2023 file), the primary classification -------------------
r23 = pd.read_csv(RUCC23, dtype=str, encoding="latin-1")
r23 = r23[r23.Attribute == "RUCC_2023"].set_index("FIPS")["Value"].astype(int)
d["rucc23"] = d["fips"].map(r23)
# Valdez-Cordova: both successor areas (02063, 02066) are coded 9.
d.loc[d.fips == "02261", "rucc23"] = 9
note("6b RUCC 2023", "02261", "all", "rucc23 = 9 (Chugach and Copper River are both 9)")
# Connecticut: 2023 codes exist only for planning regions. Each legacy county takes the
# code of the planning region holding most of its population (approximation).
ct_map = {"09001": ("09190/09120", 2), "09003": ("09110", 1), "09005": ("09160", 4),
          "09007": ("09130", 1), "09009": ("09170/09140", 2), "09011": ("09180", 2),
          "09013": ("09110", 1), "09015": ("09150", 4)}
for f, (region, code) in ct_map.items():
    d.loc[d.fips == f, "rucc23"] = code
    note("6b RUCC 2023", f, "all", f"rucc23 = {code} from planning region {region} (dominant-region approximation)")

# 7. Rebuild classification and every derived column from the counts ---------------
d["rucc13"] = d["rucc13"].astype(int)
d["rucc23"] = d["rucc23"].astype(int)
# Primary classification: 2023 RUCC. 2013 RUCC kept for sensitivity analysis.
d["metro"] = d["rucc23"] <= 3
d["nonmetro"] = ~d["metro"]
d["rural"] = d["nonmetro"]
d["metro13"] = d["rucc13"] <= 3
d["apc"] = d["np"] + d["pa"]
d["total_pc_capable"] = d["pcphys"] + d["apc"]
d["total_three"] = d["phys_all"] + d["np"] + d["pa"]
per = 1e5 / d["population"]
for rate, cnt in [("pcphys_rate", "pcphys"), ("np_rate", "np"), ("pa_rate", "pa"),
                  ("apc_rate", "apc"), ("phys_all_rate", "phys_all")]:
    d[rate] = d[cnt] * per


def safe_div(a, b):
    return np.where(b > 0, a / b.where(b > 0), np.nan)


d["np_share"] = safe_div(d["np"], d["total_pc_capable"])
d["apc_share"] = safe_div(d["apc"], d["total_pc_capable"])
d["phys_share"] = safe_div(d["phys_all"], d["total_three"])
d["np_share_all"] = safe_div(d["np"], d["total_three"])
d["pa_share_all"] = safe_div(d["pa"], d["total_three"])

cols = ["fips", "county", "state", "region", "region_name", "rucc23", "metro", "nonmetro", "rural",
        "rucc13", "metro13",
        "year", "population", "pop_imputed", "phys_all", "pcphys", "np", "pa", "apc",
        "total_three", "total_pc_capable", "phys_all_rate", "pcphys_rate", "np_rate", "pa_rate",
        "apc_rate", "phys_share", "np_share_all", "pa_share_all", "np_share", "apc_share"]
d = d[cols].sort_values(["fips", "year"]).reset_index(drop=True)

# 8. Checks ------------------------------------------------------------------------
assert not d.duplicated(["fips", "year"]).any()
assert d["rucc13"].between(1, 9).all()
assert d["rucc23"].between(1, 9).all()
assert d["population"].notna().all()
assert d.groupby("fips").year.nunique().eq(6).all(), "panel not balanced"
assert d["fips"].str[:2].nunique() == 51

d.to_csv(OUT, index=False)
pd.DataFrame(log).to_csv(LOG, index=False)
print(f"raw rows {n_raw} -> clean rows {len(d)} | counties {d.fips.nunique()} | "
      f"rows with missing counts {d.np.isna().sum()}")
