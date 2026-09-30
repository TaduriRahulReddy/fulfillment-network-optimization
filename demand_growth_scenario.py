import pulp


# ==================================================
# 1. INPUT DATA
# ==================================================

facilities = ["NJ", "CA", "OH", "TX", "GA"]
candidates = ["OH", "TX", "GA"]

regions = [
    "Boston",
    "New_York",
    "Atlanta",
    "Miami",
    "Chicago",
    "Dallas",
    "Denver",
    "Los_Angeles",
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

# SCENARIO: increase average weekly demand by 25%.
demand_growth = 0.25

demand = {
    region: quantity * (1 + demand_growth)
    for region, quantity in original_demand.items()
}

capacity = {
    "NJ": 900,
    "CA": 850,
    "OH": 550,
    "TX": 600,
    "GA": 550,
}

fixed_cost = {
    "NJ": 900_000,
    "CA": 1_100_000,
    "OH": 750_000,
    "TX": 800_000,
    "GA": 700_000,
}

opening_cost = {
    "OH": 650_000,
    "TX": 750_000,
    "GA": 600_000,
}

handling_cost = {
    "NJ": 18,
    "CA": 21,
    "OH": 17,
    "TX": 18,
    "GA": 16,
}

# Values follow the order of "regions".
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

weeks_per_year = 52
peak_factor = 1.20
service_target = 0.90
delivery_limit = 2
opening_budget = 2_400_000

total_demand = sum(demand.values())


# ==================================================
# 2. CREATE MODEL AND VARIABLES
# ==================================================

model = pulp.LpProblem(
    "Demand_Growth_Network",
    pulp.LpMinimize,
)

x = model.add_variable_dicts(
    "shipment",
    [(f, r) for f in facilities for r in regions],
    lowBound=0,
    cat=pulp.LpContinuous,
)

z = model.add_variable_dicts(
    "open",
    candidates,
    cat=pulp.LpBinary,
)


# ==================================================
# 3. OBJECTIVE
# ==================================================

existing_fixed_cost = sum(
    fixed_cost[f]
    for f in facilities
    if f not in candidates
)

candidate_opening_cost = pulp.lpSum(
    opening_cost[f] * z[f]
    for f in candidates
)

candidate_fixed_cost = pulp.lpSum(
    fixed_cost[f] * z[f]
    for f in candidates
)

annual_shipping_cost = weeks_per_year * pulp.lpSum(
    shipping_cost[f, r] * x[f, r]
    for f in facilities
    for r in regions
)

annual_handling_cost = weeks_per_year * pulp.lpSum(
    handling_cost[f] * x[f, r]
    for f in facilities
    for r in regions
)

model += (
    existing_fixed_cost
    + candidate_opening_cost
    + candidate_fixed_cost
    + annual_shipping_cost
    + annual_handling_cost,
    "First_Year_Total_Cost",
)


# ==================================================
# 4. DEMAND CONSTRAINTS
# ==================================================

for r in regions:
    model += (
        pulp.lpSum(x[f, r] for f in facilities) == demand[r],
        f"demand_{r}",
    )


# ==================================================
# 5. PEAK CAPACITY CONSTRAINTS
# ==================================================

for f in facilities:
    peak_volume = peak_factor * pulp.lpSum(
        x[f, r] for r in regions
    )

    if f in candidates:
        model += (
            peak_volume <= capacity[f] * z[f],
            f"capacity_{f}",
        )
    else:
        model += (
            peak_volume <= capacity[f],
            f"capacity_{f}",
        )


# ==================================================
# 6. DELIVERY-SPEED CONSTRAINT
# ==================================================

fast_volume = pulp.lpSum(
    x[f, r]
    for f in facilities
    for r in regions
    if delivery_days[f, r] <= delivery_limit
)

model += (
    fast_volume >= service_target * total_demand,
    "Two_Day_Delivery_Target",
)


# ==================================================
# 7. OPENING-BUDGET CONSTRAINT
# ==================================================

model += (
    candidate_opening_cost <= opening_budget,
    "Opening_Budget",
)


# ==================================================
# 8. SOLVE WITH CBC
# ==================================================

solver = pulp.COIN_CMD(
    path="/opt/homebrew/bin/cbc",
    msg=True,
    gapRel=0,
)

if not solver.available():
    raise RuntimeError(
        "CBC was not found. Run: brew install cbc"
    )

stats = model.solve(solver)

print("\nSolver status:", stats.status_str)

if (
    stats.status != pulp.LpSolveStatus.Optimal
    or not stats.has_solution
):
    raise SystemExit(
        "No proven optimal solution. Check the solver log, "
        "capacity, service target, and budget."
    )


# ==================================================
# 9. SCENARIO AND COST RESULTS
# ==================================================

opened = [
    f for f in candidates
    if z[f].value() > 0.5
]

total_cost = pulp.value(model.objective)

annual_fixed_spend = (
    existing_fixed_cost
    + pulp.value(candidate_fixed_cost)
)

print("\nDEMAND-GROWTH SCENARIO")
print(f"Demand increase:        {demand_growth:.0%}")
print(f"Original weekly demand: {sum(original_demand.values()):,.0f}")
print(f"New weekly demand:      {total_demand:,.0f}")
print(f"Peak weekly demand:     {total_demand * peak_factor:,.0f}")

print("\nCOST BREAKDOWN")
print(
    f"One-time opening cost: "
    f"${pulp.value(candidate_opening_cost):,.2f}"
)
print(f"Annual fixed cost:     ${annual_fixed_spend:,.2f}")
print(
    f"Annual shipping cost: "
    f"${pulp.value(annual_shipping_cost):,.2f}"
)
print(
    f"Annual handling cost: "
    f"${pulp.value(annual_handling_cost):,.2f}"
)
print(f"FIRST-YEAR TOTAL COST: ${total_cost:,.2f}")


# ==================================================
# 10. FACILITY DECISIONS
# ==================================================

print("\nFACILITY DECISIONS")
print("NJ: EXISTING — REMAINS OPEN")
print("CA: EXISTING — REMAINS OPEN")

for f in candidates:
    decision = "OPEN" if f in opened else "DO NOT OPEN"
    print(f"{f}: {decision}")


# ==================================================
# 11. SHIPMENT PLAN
# ==================================================

print("\nSHIPMENT PLAN — AVERAGE WEEK")

for f in facilities:
    for r in regions:
        quantity = x[f, r].value()

        if quantity > 0.000001:
            print(
                f"{f} -> {r}: "
                f"{quantity:,.2f} units/week "
                f"({delivery_days[f, r]} days)"
            )


# ==================================================
# 12. PEAK UTILIZATION
# ==================================================

print("\nPEAK CAPACITY UTILIZATION")

for f in facilities:
    is_active = f not in candidates or f in opened

    if is_active:
        average_volume = sum(
            x[f, r].value() for r in regions
        )

        peak_volume = average_volume * peak_factor
        utilization = peak_volume / capacity[f]

        print(
            f"{f}: {peak_volume:,.2f} / "
            f"{capacity[f]:,.0f} units "
            f"= {utilization:.1%}"
        )


# ==================================================
# 13. DELIVERY AND COST-PER-UNIT METRICS
# ==================================================

fast_units = pulp.value(fast_volume)
coverage = fast_units / total_demand

weighted_delivery_days = sum(
    delivery_days[f, r] * x[f, r].value()
    for f in facilities
    for r in regions
) / total_demand

annual_units = total_demand * weeks_per_year
first_year_cost_per_unit = total_cost / annual_units

print("\nDELIVERY AND COST METRICS")
print(f"Two-day coverage:          {coverage:.1%}")
print(f"Required coverage:         {service_target:.1%}")
print(f"Weighted delivery time:    {weighted_delivery_days:.2f} days")
print(f"First-year cost per unit:  ${first_year_cost_per_unit:,.2f}")