import pulp


# ==================================================
# 1. DATA: FIX THE NETWORK TO NJ + CA + GEORGIA
# ==================================================

facilities = ["NJ", "CA", "GA"]

regions = [
    "Boston", "New_York", "Atlanta", "Miami",
    "Chicago", "Dallas", "Denver", "Los_Angeles",
]

original_demand = {
    "Boston": 180,
    "New_York": 240,
    "Atlanta": 160,
    "Miami": 100,
    "Chicago": 200,
    "Dallas": 180,
    "Denver": 100,
    "Los_Angeles": 240,
}

demand = {
    r: quantity * 1.25
    for r, quantity in original_demand.items()
}

capacity = {"NJ": 900, "CA": 850, "GA": 550}

fixed_cost = {
    "NJ": 900_000,
    "CA": 1_100_000,
    "GA": 700_000,
}

handling_cost = {"NJ": 18, "CA": 21, "GA": 16}

shipping_rows = {
    "NJ": [90, 65, 170, 220, 150, 240, 270, 390],
    "CA": [390, 410, 320, 340, 250, 230, 170, 60],
    "GA": [210, 200, 60, 120, 170, 150, 220, 330],
}

delivery_rows = {
    "NJ": [1, 1, 3, 4, 2, 4, 5, 7],
    "CA": [7, 7, 6, 6, 4, 4, 3, 1],
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
total_demand = sum(demand.values())


# ==================================================
# 2. FUNCTION TO BUILD EITHER TEST
# ==================================================

def build_model(maximize_coverage=False):
    sense = (
        pulp.LpMaximize
        if maximize_coverage
        else pulp.LpMinimize
    )

    model = pulp.LpProblem(
        "Georgia_Only_Stress_Test",
        sense,
    )

    # Create fresh variables for each model.
    x = model.add_variable_dicts(
        "shipment",
        [(f, r) for f in facilities for r in regions],
        lowBound=0,
        cat=pulp.LpContinuous,
    )

    fast_volume = pulp.lpSum(
        x[f, r]
        for f in facilities
        for r in regions
        if delivery_days[f, r] <= 2
    )

    if maximize_coverage:
        # Diagnostic objective: serve as many units
        # as possible within two days.
        model += fast_volume, "Maximum_Fast_Volume"
    else:
        # Same first-year cost convention as earlier:
        # include Georgia's opening cost once.
        model += (
            600_000
            + sum(fixed_cost.values())
            + 52 * pulp.lpSum(
                (shipping_cost[f, r] + handling_cost[f])
                * x[f, r]
                for f in facilities
                for r in regions
            ),
            "First_Year_Total_Cost",
        )

    for r in regions:
        model += (
            pulp.lpSum(x[f, r] for f in facilities)
            == demand[r],
            f"demand_{r}",
        )

    for f in facilities:
        model += (
            peak_factor * pulp.lpSum(
                x[f, r] for r in regions
            ) <= capacity[f],
            f"capacity_{f}",
        )

    if not maximize_coverage:
        model += (
            fast_volume >= service_target * total_demand,
            "Two_Day_Target",
        )

    return model, x, fast_volume


# ==================================================
# 3. TEST THE 90% REQUIREMENT
# ==================================================

solver = pulp.COIN_CMD(
    path="/opt/homebrew/bin/cbc",
    msg=False,
    gapRel=0,
)

if not solver.available():
    raise RuntimeError("CBC not found. Run: brew install cbc")

model, x, fast_volume = build_model()
stats = model.solve(solver)

print("\nGEORGIA-ONLY NETWORK AT 25% HIGHER DEMAND")
print(f"Average weekly demand: {total_demand:,.0f}")
print(f"Peak weekly demand:    {total_demand * peak_factor:,.0f}")
print(f"Required coverage:     {service_target:.1%}")
print(f"Solver status:         {stats.status_str}")

if (
    stats.status == pulp.LpSolveStatus.Optimal
    and stats.has_solution
):
    print("\nThis network can meet the target.")
    print(
        f"First-year cost: "
        f"${pulp.value(model.objective):,.2f}"
    )
    print(
        f"Two-day coverage: "
        f"{pulp.value(fast_volume) / total_demand:.1%}"
    )

elif stats.status == pulp.LpSolveStatus.Infeasible:
    print("\nThis network cannot meet all requirements.")
    print("Calculating its maximum possible two-day coverage...")

    # ==================================================
    # 4. DIAGNOSE THE SERVICE LIMIT
    # ==================================================

    diagnostic, diagnostic_x, diagnostic_fast = build_model(
        maximize_coverage=True
    )

    diagnostic_stats = diagnostic.solve(solver)

    if (
        diagnostic_stats.status != pulp.LpSolveStatus.Optimal
        or not diagnostic_stats.has_solution
    ):
        raise SystemExit(
            "Diagnostic did not solve optimally. "
            "Check overall capacity and the solver status: "
            + diagnostic_stats.status_str
        )

    max_fast_units = pulp.value(diagnostic_fast)
    max_coverage = max_fast_units / total_demand
    required_fast_units = service_target * total_demand

    print("\nMAXIMUM SERVICE CAPABILITY")
    print(f"Required fast units:    {required_fast_units:,.2f}")
    print(f"Maximum fast units:     {max_fast_units:,.2f}")
    print(f"Fast-unit shortfall:    {required_fast_units - max_fast_units:,.2f}")
    print(f"Maximum coverage:       {max_coverage:.2%}")
    print(
        f"Coverage shortfall:    "
        f"{(service_target - max_coverage) * 100:.2f} "
        "percentage points"
    )

    print("\nPEAK UTILIZATION AT MAXIMUM COVERAGE")

    for f in facilities:
        weekly_units = sum(
            diagnostic_x[f, r].value()
            for r in regions
        )

        peak_units = weekly_units * peak_factor

        print(
            f"{f}: {peak_units:,.2f} / "
            f"{capacity[f]:,.0f} "
            f"= {peak_units / capacity[f]:.1%}"
        )

    print(
        "\nThis diagnostic maximizes delivery coverage; "
        "it does not minimize shipping cost."
    )

else:
    raise SystemExit(
        "Unexpected solver termination: " + stats.status_str
    )