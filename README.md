# Rural Clinician Workforce Panel, 2018–2023

County-year panel of physicians, nurse practitioners (NPs), and physician assistants (PAs) for the 50 U.S. states and the District of Columbia, built from the HRSA Area Health Resources Files (AHRF). It supports the study *Changing Composition of the U.S. Rural Clinician Workforce: Physician, Nurse Practitioner, and Physician Assistant Supply, 2018–2023* (Mollard).

## Contents

| Path | What it is |
|---|---|
| `data/AHRF_allphys_NP_PA_panel_2018_2023_clean.csv` | Cleaned analytic panel: 3,142 counties × 6 years = 18,852 rows, balanced, no missing values |
| `data/raw/AHRF_allphys_NP_PA_panel_2018_2023.csv` | Original panel before cleaning (19,393 rows) |
| `data/cleaning_log.csv` | Every change made during cleaning |
| `data/reference/Ruralurbancontinuumcodes2023.csv` | USDA ERS 2023 Rural-Urban Continuum Codes |
| `clean_panel.py` | Builds the clean panel from the raw panel |
| `reproduce_abstract.py` | Main results (2023 RUCC); writes `results/main_results.txt` |
| `sensitivity_rucc2013.py` | Reruns the main results with 2013 RUCC; writes `results/sensitivity_rucc2023_vs_2013.csv` |
| `results/` | Output of the two analysis scripts |

## How the raw panel was built

AHRF county releases 2019–2020, 2020–2021, 2021–2022, 2022–2023, 2023–2024 and 2024–2025 were harmonized and the 2018–2023 data years extracted into a physician/NP/PA panel; all-active nonfederal physician measures were then added, giving `AHRF_allphys_NP_PA_panel_2018_2023.csv`. The AHRF release files are not included here; they are available from HRSA (link below).

## Reproducing

```
pip install -r requirements.txt
python clean_panel.py
python reproduce_abstract.py
python sensitivity_rucc2013.py
```

## Rurality classification

The primary classification is the USDA **2023 Rural-Urban Continuum Codes** (based on the 2020 Census), held fixed across all years. RUCC 1–3 are metropolitan; 4–9 are nonmetropolitan.

- **Alaska:** Valdez-Cordova takes code 9 (both of its successor areas, Chugach and Copper River, are coded 9).
- **Connecticut:** 2023 codes are published only for the 9 planning regions, while clinician counts are reported for the 8 legacy counties. Each legacy county takes the code of the planning region holding most of its population. This approximation affects 8 units and is recorded in the cleaning log.

**Sensitivity analysis.** All results were rerun using the 2013 codes (2010 Census). No conclusion changes. Growth rates, workforce shares and regression gradients differ by less than one percentage point, and nonmetropolitan densities by less than 2 per 100,000; the only larger difference is in the RUCC 8–9 group, explained below (`results/sensitivity_rucc2023_vs_2013.csv`). Note that USDA redefined codes 6–9 in 2023, raising the urban-population cutoff from 2,500 to 5,000, so RUCC 8–9 contains 1,054 counties under the 2023 codes versus 644 under the 2013 codes.

## Cleaning steps

1. **Territories removed.** Puerto Rico, Guam and the U.S. Virgin Islands are dropped; the panel covers the 50 states and DC.
2. **Empty rows for defunct units removed.** Six Alaska and Virginia units that no longer exist had rows with no counts and no population.
3. **Alaska.** Valdez-Cordova (02261) split into Chugach (02063) and Copper River (02066) in 2019. The two new areas are summed back into 02261 for every year so the unit stays constant.
4. **Connecticut population.** In 2022–2023 the AHRF puts clinician counts on the 8 legacy counties and population on the 9 planning regions. The legacy counties are kept; their 2022–2023 population is imputed as the statewide planning-region total times each county's 2021 share of state population. Imputed values are flagged in `pop_imputed`.
5. **2013 RUCC corrections** (used in the sensitivity analysis). Pueblo, CO (invalid code 32 → 3), Rio Arriba, NM (invalid code 45 → 4), and Fremont, CO (5 → 4).
6. **2023 RUCC added** as the primary classification (see above).
7. **Derived columns rebuilt.** Metro status, rates, and shares are recomputed from the counts so they are consistent after the fixes.

## Data dictionary

| Column | Description |
|---|---|
| `fips` | 5-digit county FIPS code (text, leading zeros kept) |
| `county`, `state` | Names |
| `region`, `region_name` | U.S. Census region: 1 Northeast, 2 Midwest, 3 South, 4 West |
| `rucc23` | USDA 2023 Rural-Urban Continuum Code (1–9) — **primary classification** |
| `metro`, `nonmetro` | Metropolitan (RUCC 1–3) vs nonmetropolitan (RUCC 4–9), 2023 codes |
| `rural` | Same as `nonmetro` |
| `rucc13`, `metro13` | 2013 RUCC and metro status, for sensitivity analysis |
| `year` | 2018–2023 |
| `population` | County population |
| `pop_imputed` | True where population was imputed (Connecticut 2022–2023) |
| `phys_all` | Active nonfederal physicians, all specialties |
| `pcphys` | Primary care physicians |
| `np`, `pa` | Nurse practitioners; physician assistants |
| `apc` | NPs + PAs |
| `total_three` | Physicians (all) + NPs + PAs |
| `total_pc_capable` | Primary care physicians + NPs + PAs |
| `*_rate` | Count per 100,000 population |
| `phys_share`, `np_share_all`, `pa_share_all` | Share of `total_three` |
| `np_share`, `apc_share` | Share of `total_pc_capable` (NPs; NPs + PAs) |

Shares are blank where the denominator is zero.

## Notes and limitations

- Counts come from the AHRF, which draws physician counts from the AMA Physician Masterfile and NP/PA counts from other registries. Sources differ in how active practice and location are defined, so cross-profession comparisons should be read with that in mind.
- Counts are headcounts, not full-time equivalents.
- NP counts include all specialties; they are not restricted to primary care NPs.
- This is an ecological, county-level analysis.

## Sources

- HRSA Area Health Resources Files: https://data.hrsa.gov/topics/health-workforce/ahrf
- USDA ERS Rural-Urban Continuum Codes: https://www.ers.usda.gov/data-products/rural-urban-continuum-codes
