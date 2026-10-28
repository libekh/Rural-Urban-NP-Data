"""
Sensitivity analysis: rerun the main results using 2013 RUCC instead of 2023 RUCC (primary).
Run after clean_panel.py, from the main repository folder:  python scripts/sensitivity_rucc2013.py
Writes results/sensitivity_rucc2023_vs_2013.csv
"""
import os
import warnings
warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

d = pd.read_csv("data/AHRF_allphys_NP_PA_panel_2018_2023_clean.csv", dtype={"fips": str})


def dens(s):
    P = s.population.sum()
    return pd.Series({"phys": s.phys_all.sum() / P * 1e5, "pcp": s.pcphys.sum() / P * 1e5,
                      "np": s.np.sum() / P * 1e5, "pa": s.pa.sum() / P * 1e5,
                      "np_pa_share": (s.np.sum() + s.pa.sum()) / s.total_three.sum() * 100})


def run(code, metro):
    x = d.assign(code=d[code], nm=~d[metro])
    out = {}
    y18, y23 = x[x.year == 2018], x[x.year == 2023]
    for lab, flag in [("metro", False), ("nonmetro", True)]:
        a, b = dens(y18[y18.nm == flag]), dens(y23[y23.nm == flag])
        out[f"counties, {lab}"] = (x[(x.year == 2023) & (x.nm == flag)]).shape[0]
        for k in ["phys", "np", "pa", "pcp"]:
            out[f"2023 {k} per 100k, {lab}"] = b[k]
            out[f"{k} change 2018-23 %, {lab}"] = (b[k] / a[k] - 1) * 100
        out[f"NP+PA share 2018 %, {lab}"] = a.np_pa_share
        out[f"NP+PA share 2023 %, {lab}"] = b.np_pa_share
    m23, n23 = dens(y23[~y23.nm]), dens(y23[y23.nm])
    out["nonmetro phys as % of metro, 2023"] = n23.phys / m23.phys * 100
    out["nonmetro NP as % of metro, 2023"] = n23.np / m23.np * 100
    rem = y23[y23.code.isin([8, 9])]
    r = dens(rem)
    out["RUCC 8-9: counties"] = len(rem)
    out["RUCC 8-9: phys per 100k"] = r.phys
    out["RUCC 8-9: NP per 100k"] = r.np
    out["RUCC 8-9: NP+PA share %"] = r.np_pa_share
    for yr, s in [(2018, y18), (2023, y23)]:
        n = s[s.nm]
        out[f"% nonmetro residents in NP>physician counties, {yr}"] = (
            n.population[n.np > n.phys_all].sum() / n.population.sum() * 100)
        out[f"nonmetro counties with NPs but no physicians, {yr}"] = ((n.phys_all == 0) & (n.np > 0)).sum()
    # Rural gradient model
    long = pd.concat([x.assign(prof=p, count=x[c]) for p, c in
                      [("phys", "phys_all"), ("np", "np"), ("pa", "pa")]])
    m = smf.glm('count ~ C(prof, Treatment("phys")) * code + C(year) + C(region)', data=long,
                family=sm.families.Poisson(), offset=np.log(long.population)
                ).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(long.fips)[0]})
    out["per RUCC step: % change phys density"] = (np.exp(m.params["code"]) - 1) * 100
    for p in ["np", "pa"]:
        k = f'C(prof, Treatment("phys"))[T.{p}]:code'
        out[f"per RUCC step: % change {p} density"] = (np.exp(m.params["code"] + m.params[k]) - 1) * 100
        out[f"{p} vs phys gradient: p-value"] = m.pvalues[k]
    return pd.Series(out)


res = pd.DataFrame({"RUCC 2023 (primary)": run("rucc23", "metro"),
                    "RUCC 2013 (sensitivity)": run("rucc13", "metro13")})
os.makedirs("results", exist_ok=True)
res.to_csv("results/sensitivity_rucc2023_vs_2013.csv")
pd.set_option("display.float_format", lambda v: f"{v:,.3g}" if abs(v) < 0.01 else f"{v:,.1f}")
print(res.to_string())
