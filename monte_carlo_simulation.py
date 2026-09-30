import csv
import json
import math
import random
from pathlib import Path

import pulp


# ==================================================
# 1. NETWORK DATA
# ==================================================

regions = [
    "Boston", "New_York", "Atlanta", "Miami",
    "Chicago", "Dallas", "Denver", "Los_Angeles",
]

base_demand = dict(zip(
    regions,
    [180, 240, 160, 100, 200, 180, 100, 240],
))

capacity = {
    "NJ": 900,
    "CA": 850,
    "TX": 600,
    "GA": 550,
}

handling_cost = {
    "NJ": 18,
    "CA": 21,
    "TX": 18,
    "GA": 16,
}

shipping_rows = {
    "NJ": [90, 65, 170, 220, 150, 240, 270, 390],
    "CA": [390, 410, 320, 340, 250, 230, 170, 60],
    "TX": [270, 280, 160, 210, 190, 60, 140, 240],
    "GA": [210, 200, 60, 120, 170, 150, 220, 330],
}

delivery_rows = {
    "NJ": [1, 1, 3, 4, 2, 4, 5, 7],
    "CA": [7, 7, 6, 6, 4, 4, 3, 1],
    "TX": [5, 5, 2, 3, 3, 1, 2, 4],
    "GA": [3, 3, 1, 2, 2, 2, 4, 6],
}

shipping_cost = {
    (f, r): shipping_rows[f][i]
    for f in capacity
    for i, r in enumerate(regions)
}

delivery_days = {
    (f, r): delivery_rows[f][i]
    for f in capacity
    for i, r in enumerate(regions)
}

networks = {
    "Georgia_only": ["NJ", "CA", "GA"],
    "Texas_plus_Georgia": ["NJ", "CA", "TX", "GA"],
}


# ==================================================
# 2. SIMULATION ASSUMPTIONS
# ==================================================

number_of_samples = 1_000
mean_growth = 0.15
service_target = 0.90
seed = 42

# Synthetic log-scale demand volatility.
# Shared shocks affect all regions.
# Regional shocks affect individual regions.
shared_sigma = 0.10
regional_sigma = 0.10

rng = random.Random(seed)

solver = pulp.COIN_CMD(
    path="/opt/homebrew/bin/cbc",
    msg=False,
    gapRel=0,
)

if not solver.available():
    raise RuntimeError("CBC not found. Run: brew install cbc")


# ==================================================
# 3. GENERATE SHARED DEMAND SCENARIOS
# ==================================================

scenarios = []

# Correction keeps expected demand equal to:
# base demand * (1 + mean_growth).
mean_correction = 0.5 * (
    shared_sigma ** 2 + regional_sigma ** 2
)

for sample in range(1, number_of_samples + 1):
    shared_shock = rng.gauss(0, shared_sigma)

    demand = {}

    for r in regions:
        regional_shock = rng.gauss(0, regional_sigma)

        demand[r] = (
            base_demand[r]
            * (1 + mean_growth)
            * math.exp(
                shared_shock
                + regional_shock
                - mean_correction
            )
        )

    scenarios.append((sample, demand))


# ==================================================
# 4. OPTIMIZE ROUTING FOR ONE SAMPLED WEEK
# ==================================================

def solve_week(facilities, demand):
    model = pulp.LpProblem(
        "Simulated_Weekly_Routing",
        pulp.LpMinimize,
    )

    x = model.add_variable_dicts(
        "shipment",
        [(f, r) for f in facilities for r in regions],
        lowBound=0,
        cat=pulp.LpContinuous,
    )

    # Weekly variable cost only:
    # shipping + handling.
    model += pulp.lpSum(
        (shipping_cost[f, r] + handling_cost[f]) * x[f, r]
        for f in facilities
        for r in regions
    )

    for r in regions:
        model += (
            pulp.lpSum(x[f, r] for f in facilities)
            == demand[r],
            f"demand_{r}",
        )

    for f in facilities:
        # Sampled demand represents an actual week.
        # Do not multiply by the planning peak factor.
        model += (
            pulp.lpSum(x[f, r] for r in regions)
            <= capacity[f],
            f"capacity_{f}",
        )

    fast_volume = pulp.lpSum(
        x[f, r]
        for f in facilities
        for r in regions
        if delivery_days[f, r] <= 2
    )

    total_demand = sum(demand.values())

    model += (
        fast_volume >= service_target * total_demand,
        "Two_Day_Target",
    )

    stats = model.solve(solver)

    if stats.status == pulp.LpSolveStatus.Infeasible:
        return {
            "status": "Infeasible",
            "weekly_variable_cost_USD": None,
            "two_day_coverage": None,
            "max_capacity_utilization": None,
        }

    if (
        stats.status != pulp.LpSolveStatus.Optimal
        or not stats.has_solution
    ):
        raise RuntimeError(
            "Unexpected solver termination: " + stats.status_str
        )

    # Validate the allocation before reporting results.
    tolerance = 0.001

    for f in facilities:
        for r in regions:
            if x[f, r].value() < -tolerance:
                raise RuntimeError("Negative shipment allocation.")

    for r in regions:
        served = sum(x[f, r].value() for f in facilities)

        if abs(served - demand[r]) > tolerance:
            raise RuntimeError(f"Demand validation failed: {r}")

    utilization = {}

    for f in facilities:
        volume = sum(x[f, r].value() for r in regions)

        if volume > capacity[f] + tolerance:
            raise RuntimeError(f"Capacity validation failed: {f}")

        utilization[f] = volume / capacity[f]

    fast_units = pulp.value(fast_volume)

    if fast_units < service_target * total_demand - tolerance:
        raise RuntimeError("Delivery coverage validation failed.")

    return {
        "status": "Optimal",
        "weekly_variable_cost_USD": pulp.value(model.objective),
        "two_day_coverage": fast_units / total_demand,
        "max_capacity_utilization": max(utilization.values()),
    }


# ==================================================
# 5. RUN BOTH NETWORKS ON THE SAME SCENARIOS
# ==================================================

results = []

print("\nMONTE CARLO DEMAND SIMULATION")
print(f"Samples per network: {number_of_samples:,}")
print(f"Mean demand growth:  {mean_growth:.0%}")
print(f"Random seed:         {seed}")

for network_name, facilities in networks.items():
    print(f"\nRunning: {network_name}")

    for sample, demand in scenarios:
        outcome = solve_week(facilities, demand)

        row = {
            "sample": sample,
            "network": network_name,
            "total_weekly_demand": sum(demand.values()),
            **{f"demand_{r}": demand[r] for r in regions},
            **outcome,
        }

        results.append(row)

        if sample % 100 == 0:
            print(f"  Completed {sample:,} scenarios")


# ==================================================
# 6. SUMMARIZE RESULTS
# ==================================================

summary = {
    "samples_per_network": number_of_samples,
    "mean_growth": mean_growth,
    "shared_log_sigma": shared_sigma,
    "regional_log_sigma": regional_sigma,
    "seed": seed,
    "solver": "CBC",
    "capacity_convention": (
        "Actual sampled weekly demand; no extra peak multiplier."
    ),
    "routing_policy": (
        "Fixed facilities; shipments optimized after demand is known."
    ),
    "networks": {},
}

print("\nSIMULATION RESULTS")

for network_name in networks:
    network_rows = [
        row for row in results
        if row["network"] == network_name
    ]

    feasible_rows = [
        row for row in network_rows
        if row["status"] == "Optimal"
    ]

    successes = len(feasible_rows)
    success_rate = successes / number_of_samples

    # Wilson 95% interval for the estimated success probability.
    z = 1.96
    n = number_of_samples
    denominator = 1 + z ** 2 / n

    center = (
        success_rate + z ** 2 / (2 * n)
    ) / denominator

    half_width = (
        z
        * math.sqrt(
            success_rate * (1 - success_rate) / n
            + z ** 2 / (4 * n ** 2)
        )
        / denominator
    )

    lower = max(0, center - half_width)
    upper = min(1, center + half_width)

    mean_cost = (
        sum(
            row["weekly_variable_cost_USD"]
            for row in feasible_rows
        ) / successes
        if successes else None
    )

    mean_utilization = (
        sum(
            row["max_capacity_utilization"]
            for row in feasible_rows
        ) / successes
        if successes else None
    )

    summary["networks"][network_name] = {
        "successful_weeks": successes,
        "infeasible_weeks": n - successes,
        "success_rate": success_rate,
        "success_rate_95pct_interval": [lower, upper],
        "mean_weekly_variable_cost_USD_given_feasible": mean_cost,
        "mean_max_utilization_given_feasible": mean_utilization,
    }

    print(f"\n{network_name}")
    print(f"Successful weeks: {successes:,} / {n:,}")
    print(f"Success rate:     {success_rate:.2%}")
    print(f"95% interval:     {lower:.2%} – {upper:.2%}")

    if mean_cost is not None:
        print(f"Mean weekly variable cost*: ${mean_cost:,.2f}")

print(
    "\n*Costs include shipping and handling only, "
    "and are averaged over feasible weeks."
)


# ==================================================
# 7. SAVE RESULTS
# ==================================================

folder = Path(__file__).resolve().parent
csv_path = folder / "monte_carlo_results.csv"
json_path = folder / "monte_carlo_summary.json"

with csv_path.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=list(results[0]),
    )
    writer.writeheader()
    writer.writerows(results)

json_path.write_text(
    json.dumps(summary, indent=2) + "\n",
    encoding="utf-8",
)

print(f"\nDetailed results: {csv_path}")
print(f"Summary:          {json_path}")