import csv
from pathlib import Path

import matplotlib.pyplot as plt


# ==================================================
# 1. LOAD THE SAVED SCENARIO RESULTS
# ==================================================

folder = Path(__file__).resolve().parent

input_files = [
    folder / "growth_sensitivity_results.csv",
    folder / "growth_threshold_results.csv",
]

# Merge both files, keeping one record per growth level.
results_by_growth = {}

for path in input_files:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path.name}. Run its scenario script first."
        )

    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if (
                row["optimized_status"] != "Optimal"
                or row["georgia_only_status"] != "Optimal"
            ):
                raise ValueError(
                    "Summary expects optimal scenario results. "
                    f"Check growth level {row['growth_percent']}."
                )

            growth = float(row["growth_percent"])

            results_by_growth[growth] = {
                "growth": growth,
                "demand": float(row["weekly_demand"]),
                "sites": row["open_candidates"],
                "cost": float(row["first_year_cost_USD"]),
                "cost_per_unit": float(
                    row["first_year_cost_per_unit_USD"]
                ),
                "coverage": float(
                    row["optimized_two_day_coverage"]
                ) * 100,
                "georgia_coverage": float(
                    row["georgia_only_max_coverage"]
                ) * 100,
            }

results = [
    results_by_growth[growth]
    for growth in sorted(results_by_growth)
]

growth_levels = [r["growth"] for r in results]
optimized_coverage = [r["coverage"] for r in results]
georgia_coverage = [r["georgia_coverage"] for r in results]
unit_costs = [r["cost_per_unit"] for r in results]

texas_cases = [
    r for r in results
    if "TX" in r["sites"].split(",")
]

first_texas_growth = (
    texas_cases[0]["growth"] if texas_cases else None
)


# ==================================================
# 2. CREATE THE COMPARISON CHART
# ==================================================

figure, axes = plt.subplots(1, 2, figsize=(13, 5))

axes[0].plot(
    growth_levels,
    georgia_coverage,
    marker="o",
    color="#b45309",
    label="Georgia-only maximum",
)

axes[0].plot(
    growth_levels,
    optimized_coverage,
    marker="s",
    color="#2563eb",
    label="Optimized network",
)

axes[0].axhline(
    90,
    color="#dc2626",
    linestyle="--",
    label="90% requirement",
)

axes[0].set_title("Two-day delivery coverage")
axes[0].set_xlabel("Demand growth (%)")
axes[0].set_ylabel("Shipment units within two days (%)")
axes[0].legend()
axes[0].grid(alpha=0.25)

axes[1].plot(
    growth_levels,
    unit_costs,
    marker="o",
    color="#6d28d9",
)

if first_texas_growth is not None:
    axes[1].axvline(
        first_texas_growth,
        color="#64748b",
        linestyle="--",
        label=f"Texas first selected: {first_texas_growth:g}%",
    )
    axes[1].legend()

axes[1].set_title("First-year cost per shipped unit")
axes[1].set_xlabel("Demand growth (%)")
axes[1].set_ylabel("USD/unit, including opening costs")
axes[1].grid(alpha=0.25)

figure.suptitle(
    "Fulfillment network planning — synthetic case",
    fontsize=14,
)

figure.text(
    0.5,
    0.01,
    "Points are solved scenarios; connecting lines are visual guides.",
    ha="center",
    fontsize=9,
    color="#475569",
)

figure.tight_layout(rect=[0, 0.05, 1, 0.93])

figure_folder = folder / "figures"
figure_folder.mkdir(exist_ok=True)

chart_path = figure_folder / "network_sensitivity.png"

figure.savefig(
    chart_path,
    dpi=200,
    bbox_inches="tight",
)

plt.close(figure)


# ==================================================
# 3. BUILD A RESULTS TABLE FOR THE README
# ==================================================

table_lines = [
    "| Growth | Weekly demand | New sites | First-year cost | "
    "Optimized coverage | Georgia-only maximum |",
    "|---|---:|---|---:|---:|---:|",
]

for row in results:
    sites = row["sites"].replace(",", " + ")

    table_lines.append(
        f"| {row['growth']:g}% "
        f"| {row['demand']:,.0f} "
        f"| {sites} "
        f"| ${row['cost']:,.2f} "
        f"| {row['coverage']:.2f}% "
        f"| {row['georgia_coverage']:.2f}% |"
    )

results_table = "\n".join(table_lines)

# Baseline cost comes from your confirmed CBC baseline run.
baseline_cost = 13_645_400

base_case = results_by_growth[0]
cost_reduction = baseline_cost - base_case["cost"]
reduction_percent = cost_reduction / baseline_cost * 100


# ==================================================
# 4. GENERATE THE GITHUB README
# ==================================================

readme = f"""# Fulfillment Network Optimization

A Wayfair-inspired operations analytics project using Python,
PuLP 4 and the free CBC solver.

All data is synthetic. This project is not affiliated with Wayfair
and does not use internal company data.

## Business question

Which fulfillment centers should open, and how should demand be
allocated to minimize cost while providing two-day delivery
coverage to at least 90% of shipment units?

## Network

- Two existing centers: New Jersey and California
- Three candidate sites: Ohio, Texas and Georgia
- Eight customer regions
- Forty outbound shipping lanes
- One standardized bulky-item category

## Model

The expansion model is a MILP with 40 continuous shipment variables,
3 binary opening decisions and 15 business constraints.

The objective includes one-time opening costs, annual fixed
operating costs, shipping costs and handling costs.

Constraints enforce demand fulfillment, peak-week capacity,
facility activation, delivery coverage and the opening budget.

Weekly shipments are multiplied by 1.2 to test peak capacity
and by 52 to calculate annual variable costs.

## Baseline comparison

| Metric | Existing-only baseline | Open Georgia |
|---|---:|---:|
| First-year cost | $13,645,400 | ${base_case['cost']:,.0f} |
| Two-day coverage | 52.14% | {base_case['coverage']:.2f}% |

Modeled first-year cost reduction:
${cost_reduction:,.0f}, or {reduction_percent:.1f}%.

The baseline measures service without enforcing the 90% target.
It is an optimized existing-network benchmark, not observed
company performance.

## Demand-growth results

{results_table}

![Network sensitivity](figures/network_sensitivity.png)

## Investment finding

Georgia alone meets the target at 14.5% growth, with approximately
90.02% maximum coverage. At 15% growth, its maximum falls to
89.90%, and the optimized model selects Texas plus Georgia.

The tested investment trigger is above 14.5% and at or below
15% growth. This is a grid result, not an exact threshold.

At 25% growth, Georgia alone achieves at most 86.19% coverage.
The optimized Texas-plus-Georgia network achieves 100%.

## Project files

- network_optimization.py: current-demand expansion
- baseline_network.py: existing-only benchmark
- demand_growth_scenario.py: 25% demand growth
- georgia_only_stress_test.py: fixed-network service limit
- growth_sensitivity.py: broad growth scenarios
- growth_threshold.py: refined growth scenarios
- project_summary.py: chart and README generation

## Setup

Use Python 3.12 or newer. Run these commands:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install "pulp[cbc]" matplotlib

On Apple Silicon macOS, install Homebrew CBC:

    brew install cbc

The scripts use /opt/homebrew/bin/cbc.
Change the solver path for other machines.

## Run

    python network_optimization.py
    python baseline_network.py
    python demand_growth_scenario.py
    python georgia_only_stress_test.py
    python growth_sensitivity.py
    python growth_threshold.py
    python project_summary.py

## Validation

CBC reported optimal solutions for the baseline, expansion and
growth scenarios. A coverage-maximizing LP diagnosed why the
Georgia-only network could not meet the target at higher demand.

CBC's log excludes the constant $2 million existing-center cost.
The Python total-cost report includes it.

## Assumptions and limitations

- All numeric inputs and facility locations are synthetic.
- Delivery coverage uses deterministic assumed route times.
- Coverage is not measured on-time delivery reliability.
- Inventory and replenishment are assumed sufficient.
- Inbound freight and inventory carrying costs are excluded.
- Candidate facilities can open immediately.
- Growth scenarios reconsider investment decisions.
- Fractional shipments represent average planning volumes.
- Peak demand preserves average-week allocation proportions.

## Recommendation

Open Georgia for current demand. Prepare further expansion before
growth reaches the modeled service limit. Actual investment timing
must account for construction lead times, demand uncertainty
and multi-year financial returns.
"""

readme_path = folder / "README.md"

if readme_path.exists():
    readme_path = folder / "README.generated.md"

readme_path.write_text(readme, encoding="utf-8")

print(f"Chart saved: {chart_path}")
print(f"README saved: {readme_path}")