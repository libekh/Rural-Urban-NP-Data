"""
Main results: descriptive and regression findings using 2023 RUCC (primary classification).
Run after clean_panel.py, from the main repository folder:  python scripts/reproduce_abstract.py
Also written to results/main_results.txt
"""
import io
import os
import sys
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")
buf = io.StringIO()


def out(*a):
    print(*a)
    print(*a, file=buf)


d = pd.read_csv("data/AHRF_allphys_NP_PA_panel_2018_2023_clean.csv", dtype={"fips": str})
d["area"] = np.where(d.metro, "metro", "nonmetro")


def dens(s):
    P = s.population.sum()
    r = {k: s[c].sum() / P * 1e5 for k, c in
         [("phys", "phys_all"), ("pcp", "pcphys"), ("np", "np"), ("pa", "pa")]}
    r["np_pa_share"] = (s.np.sum() + s.pa.sum()) / s.total_three.sum() * 100
    return pd.Series(r)


out(f"Panel: {d.fips.nunique():,} counties x {d.year.nunique()} years = {len(d):,} county-years "
    f"(50 states + DC). Rurality: 2023 RUCC.\n")

t = d.groupby(["year", "area"]).apply(dens)
out("1. Population-weighted density per 100,000 and NP+PA share of physician-NP-PA workforce (%)")
out(t.round(1).to_string(), "\n")

a, b = t.xs(2018, level="year"), t.xs(2023, level="year")
out("2. Change in density, 2018-2023 (%)")
out(((b / a - 1) * 100)[["phys", "pcp", "np", "pa"]].round(1).to_string(), "\n")
out("3. Nonmetro density as % of metro, 2023")
out((b.loc["nonmetro"] / b.loc["metro"] * 100)[["phys", "pcp", "np", "pa"]].round(1).to_string(), "\n")

r = d[d.year == 2023].groupby("rucc23").apply(dens)
r["counties"] = d[d.year == 2023].groupby("rucc23").size()
r["np_gt_phys"] = r.np > r.phys
out("4. 2023 by RUCC")
out(r.round(1).to_string())
rem = dens(d[(d.year == 2023) & d.rucc23.isin([8, 9])])
out(f"   RUCC 8-9 combined: {int(r.loc[[8, 9], 'counties'].sum())} counties, physicians {rem.phys:.1f}, "
    f"NPs {rem.np:.1f}, PAs {rem.pa:.1f} per 100k; NP+PA share {rem.np_pa_share:.1f}%\n")

out("5. NP coverage in nonmetro counties")
for yr in [2018, 2023]:
    n = d[(d.year == yr) & d.nonmetro]
    np_only = (n.phys_all == 0) & (n.np > 0)
    out(f"   {yr}: counties with NPs but no physicians: {np_only.sum()} "
        f"({n.population[np_only].sum():,.0f} residents); "
        f"residents in counties where NPs outnumber physicians: "
        f"{n.population[n.np > n.phys_all].sum() / n.population.sum() * 100:.1f}%; "
        f"NPs per physician: {n.np.sum() / n.phys_all.sum():.2f}")
w = d[d.nonmetro].pivot_table(index="fips", columns="year", values=["phys_all", "np"])
dp = w[("phys_all", 2023)] - w[("phys_all", 2018)]
dn = w[("np", 2023)] - w[("np", 2018)]
out(f"   2018-2023 net change: physicians {dp.sum():+,.0f}, NPs {dn.sum():+,.0f}. "
    f"Counties losing physicians: {(dp < 0).sum()} of {len(w)}; NPs rose in {((dp < 0) & (dn > 0)).sum()}, "
    f"fully offsetting the loss in {((dp < 0) & (dn >= -dp)).sum()}\n")

# Rural gradient: Poisson, population offset, profession x RUCC, year + region FE,
# SEs clustered by county.
long = pd.concat([d.assign(prof=p, count=d[c]) for p, c in
                  [("phys", "phys_all"), ("np", "np"), ("pa", "pa")]])
m = smf.glm('count ~ C(prof, Treatment("phys")) * rucc23 + C(year) + C(region)',
            data=long, family=sm.families.Poisson(), offset=np.log(long.population)
            ).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(long.fips)[0]})
base = m.params["rucc23"]
out("6. Rural gradient (Poisson, population offset, year + region FE, county-clustered SEs)")
out(f"   Per RUCC step: physicians {(np.exp(base) - 1) * 100:+.1f}%")
for p in ["np", "pa"]:
    k = f'C(prof, Treatment("phys"))[T.{p}]:rucc23'
    lo, hi = np.exp(m.conf_int().loc[k])
    out(f"   Per RUCC step: {p.upper()}s {(np.exp(base + m.params[k]) - 1) * 100:+.1f}%  "
        f"(ratio vs physicians {np.exp(m.params[k]):.3f}, 95% CI {lo:.3f}-{hi:.3f}, p={m.pvalues[k]:.1e})")

os.makedirs("results", exist_ok=True)
open("results/main_results.txt", "w").write(buf.getvalue())
