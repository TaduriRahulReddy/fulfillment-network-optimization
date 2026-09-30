import csv
from pathlib import Path

import pulp


# ==================================================
# 1. DATA
# ==================================================

facilities = ["NJ", "CA", "OH", "TX", "GA"]
candidates = ["OH", "TX", "GA"]

regions = [
    "Boston", "New_York", "Atlanta", "Miami",
    "Chicago", "Dallas", "Denver", "Los_Angeles",
]

base_demand = dict(zip(
    regions,
    [180, 240, 160, 100, 200, 180, 100, 240],
))

capacity = {
    "NJ": 900, "CA": 850, "OH": 550,
    "TX": 600, "GA": 550,
}

fixed_cost = {
    "NJ": 900_000,
    "CA": 1_100_000,
    "OH": 750_000,
    "TX": 800_000,
    "GA": 700_000,
}

opening_cost = {
    "OH": 650_000, "TX": 750_000, "GA": 600_000,
}

handling_cost = {
    "NJ": 18, "CA": 21, "OH": 17, "TX": 18, "GA": 16,
}

shipping_rows = {
    "NJ": [90, 65, 170, 220, 150, 240, 270, 390],
    "CA": [390, 410, 320, 340, 250, 230, 170, 60],
    "OH": [140, 130, 150, 200, 70, 190, 220, 310],
    "TX": [270, 280, 160, 210, 190, 60, 140, 240],
    "GA": [210, 200, 60, 120, 170, 150, 220, 330],
}

delivery_rows = {
    "NJ": [1, 1, 3, 4, 2, 4, 5, 7],
    "CA": [7, 7, 6, 6, 4, 4, 3, 1],
    "OH": [2, 2, 2, 3, 1, 3, 4, 6],
    "TX": [5, 5, 2, 3, 3, 1, 2, 4],
    "GA": [3, 3, 1, 2, 2, 2, 4, 6],
}

shipping_cost = {
    (f, r): shipping_rows[f][i]
    for f in facilities
    for i, r in enumerate(regions)
}

delivery_days = {
    (f, r): delivery_rows[f][i]
    for f in facilities
    for i, r in enumerate(regions)
}

peak_factor = 1.20
service_target = 0.90
opening_budget = 2_400_000

solver = pulp.COIN_CMD(
    path="/opt/homebrew/bin/cbc",
    msg=False,
    gapRel=0,
)

if not solver.available():
    raise RuntimeError("CBC not found. Run: brew install cbc")


# ==================================================
# 2. FUNCTION TO SOLVE EACH SCENARIO
# ==================================================

def solve_scenario(growth, georgia_only=False):
    demand = {
        r: quantity * (1 + growth)
        for r, quantity in base_demand.items()
    }

    total_demand = sum(demand.values())

    available = (
        ["NJ", "CA", "GA"]
        if georgia_only
        else facilities
    )

    model = pulp.LpProblem(
        "Growth_Sensitivity",
        pulp.LpMaximize if georgia_only else pulp.LpMinimize,
    )

    x = model.add_variable_dicts(
        "shipment",
        [(f, r) for f in available for r in regions],
        lowBound=0,
        cat=pulp.LpContinuous,
    )

    fast_volume = pulp.lpSum(
        x[f, r]
        for f in available
        for r in regions
        if delivery_days[f, r] <= 2
    )

    if georgia_only:
        # Measure maximum coverage with NJ + CA + GA.
        model += fast_volume, "Maximum_Fast_Volume"
        z = None

    else:
        z = model.add_variable_dicts(
            "open",
            candidates,
            cat=pulp.LpBinary,
        )

        model += (
            fixed_cost["NJ"]
            + fixed_cost["CA"]
            + pulp.lpSum(
                (opening_cost[f] + fixed_cost[f]) * z[f]
                for f in candidates
            )
            + 52 * pulp.lpSum(
                (shipping_cost[f, r] + handling_cost[f])
                * x[f, r]
                for f in available
                for r in regions
            ),
            "First_Year_Total_Cost",
        )

    for r in regions:
        model += (
            pulp.lpSum(x[f, r] for f in available) == demand[r],
            f"demand_{r}",
        )

    for f in available:
        peak_volume = peak_factor * pulp.lpSum(
            x[f, r] for r in regions
        )

        if not georgia_only and f in candidates:
            model += (
                peak_volume <= capacity[f] * z[f],
                f"capacity_{f}",
            )
        else:
            model += (
                peak_volume <= capacity[f],
                f"capacity_{f}",
            )

    if not georgia_only:
        model += (
            fast_volume >= service_target * total_demand,
            "Delivery_Target",
        )

        model += (
            pulp.lpSum(
                opening_cost[f] * z[f]
                for f in candidates
            ) <= opening_budget,
            "Opening_Budget",
        )

    stats = model.solve(solver)

    if (
        stats.status != pulp.LpSolveStatus.Optimal
        or not stats.has_solution
    ):
        return {
            "status": stats.status_str,
            "total_demand": total_demand,
            "cost": None,
            "coverage": None,
            "opened": None,
        }

    return {
        "status": stats.status_str,
        "total_demand": total_demand,
        "cost": (
            None if georgia_only
            else pulp.value(model.objective)
        ),
        "coverage": pulp.value(fast_volume) / total_demand,
        "opened": (
            ["GA"] if georgia_only
            else [f for f in candidates if z[f].value() > 0.5]
        ),
    }


# ==================================================
# 3. RUN THE GROWTH LEVELS
# ==================================================

# Change this list later to investigate smaller intervals.
growth_percentages = [0, 5, 10, 15, 20, 25, 30]

results = []

print("\nDEMAND-GROWTH SENSITIVITY\n")

for growth_percent in growth_percentages:
    growth = growth_percent / 100

    optimized = solve_scenario(growth)
    georgia = solve_scenario(growth, georgia_only=True)

    print(f"GROWTH: {growth_percent}%")
    print(f"Weekly demand: {optimized['total_demand']:,.0f}")

    if optimized["cost"] is not None:
        annual_units = optimized["total_demand"] * 52
        cost_per_unit = optimized["cost"] / annual_units

        print(f"Open candidates: {', '.join(optimized['opened'])}")
        print(f"First-year cost: ${optimized['cost']:,.2f}")
        print(f"Cost per unit: ${cost_per_unit:,.2f}")
        print(f"Optimized coverage: {optimized['coverage']:.2%}")
    else:
        cost_per_unit = None
        print(f"Optimization status: {optimized['status']}")

    if georgia["coverage"] is not None:
        georgia_meets_target = (
            georgia["coverage"] >= service_target - 1e-8
        )

        print(f"Georgia-only maximum coverage: {georgia['coverage']:.2%}")
        print(f"Georgia-only meets 90%: {georgia_meets_target}")
    else:
        georgia_meets_target = None
        print(f"Georgia-only status: {georgia['status']}")

    print()

    results.append({
        "growth_percent": growth_percent,
        "weekly_demand": optimized["total_demand"],
        "optimized_status": optimized["status"],
        "open_candidates": (
            ",".join(optimized["opened"])
            if optimized["opened"] is not None else ""
        ),
        "first_year_cost_USD": optimized["cost"],
        "first_year_cost_per_unit_USD": cost_per_unit,
        "optimized_two_day_coverage": optimized["coverage"],
        "georgia_only_status": georgia["status"],
        "georgia_only_max_coverage": georgia["coverage"],
        "georgia_only_meets_target": georgia_meets_target,
    })


# ==================================================
# 4. SAVE RESULTS TO CSV
# ==================================================

output = Path(__file__).resolve().parent / "growth_sensitivity_results.csv"

with output.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)

print(f"Results saved to: {output}")


# ==================================================
# 5. REPORT THE FIRST TESTED TEXAS RECOMMENDATION
# ==================================================

texas_cases = [
    row for row in results
    if "TX" in row["open_candidates"].split(",")
]

if texas_cases:
    first_growth = texas_cases[0]["growth_percent"]

    print(
        f"\nTexas is first selected at {first_growth}% growth "
        "among the tested levels."
    )
    print(
        "This is a grid result, not an exact threshold. "
        "Test smaller increments around that level next."
    )
else:
    print("\nTexas was not selected at any tested growth level.")