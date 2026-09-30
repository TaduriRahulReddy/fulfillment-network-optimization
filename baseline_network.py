import pulp


# ==================================================
# 1. INPUT DATA — EXISTING-NETWORK BASELINE
# ==================================================

# Only existing facilities are available.
facilities = ["NJ", "CA"]

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

# Average weekly demand: units
demand = {
    "Boston": 180,
    "New_York": 240,
    "Atlanta": 160,
    "Miami": 100,
    "Chicago": 200,
    "Dallas": 180,
    "Denver": 100,
    "Los_Angeles": 240,
}

# Maximum peak-week throughput: units
capacity = {
    "NJ": 900,
    "CA": 850,
}

# Annual fixed operating costs: USD
fixed_cost = {
    "NJ": 900_000,
    "CA": 1_100_000,
}

# Handling costs per unit: USD
handling_cost = {
    "NJ": 18,
    "CA": 21,
}

# Values follow the order of "regions".
shipping_rows = {
    "NJ": [90, 65, 170, 220, 150, 240, 270, 390],
    "CA": [390, 410, 320, 340, 250, 230, 170, 60],
}

# Assumed order-to-door delivery times: days
delivery_rows = {
    "NJ": [1, 1, 3, 4, 2, 4, 5, 7],
    "CA": [7, 7, 6, 6, 4, 4, 3, 1],
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
delivery_limit = 2
comparison_service_target = 0.90

total_demand = sum(demand.values())


# ==================================================
# 2. CREATE THE MODEL AND SHIPMENT VARIABLES
# ==================================================

model = pulp.LpProblem(
    "Existing_Network_Baseline_2027",
    pulp.LpMinimize,
)

# No facility-opening decisions are needed.
# Both existing facilities remain open.
x = model.add_variable_dicts(
    "shipment",
    [(f, r) for f in facilities for r in regions],
    lowBound=0,
    cat=pulp.LpContinuous,
)


# ==================================================
# 3. OBJECTIVE: MINIMIZE ANNUAL TOTAL COST
# ==================================================

annual_fixed_cost = sum(fixed_cost.values())

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
    annual_fixed_cost
    + annual_shipping_cost
    + annual_handling_cost,
    "Baseline_Annual_Total_Cost",
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

    model += (
        peak_volume <= capacity[f],
        f"capacity_{f}",
    )


# ==================================================
# 6. MEASURE DELIVERY COVERAGE
# ==================================================

# The baseline measures coverage without enforcing 90%.
# This reveals the existing network's service gap.
fast_volume = pulp.lpSum(
    x[f, r]
    for f in facilities
    for r in regions
    if delivery_days[f, r] <= delivery_limit
)


# ==================================================
# 7. SOLVE WITH HOMEBREW CBC
# ==================================================

solver = pulp.COIN_CMD(
    path="/opt/homebrew/bin/cbc",
    msg=True,
    gapRel=0,
)

if not solver.available():
    raise RuntimeError(
        "Homebrew CBC was not found. Run: brew install cbc"
    )

stats = model.solve(solver)

print("\nSolver status:", stats.status_str)

if (
    stats.status != pulp.LpSolveStatus.Optimal
    or not stats.has_solution
):
    raise SystemExit(
        "No proven optimal baseline solution. "
        "Check the solver log and capacity constraints."
    )


# ==================================================
# 8. DISPLAY COST BREAKDOWN
# ==================================================

shipping_spend = pulp.value(annual_shipping_cost)
handling_spend = pulp.value(annual_handling_cost)
total_cost = pulp.value(model.objective)

print("\nEXISTING-NETWORK BASELINE")
print("Available facilities: NJ and CA")
print("New facilities opened: None")

print("\nCOST BREAKDOWN")
print("One-time opening cost:  $0.00")
print(f"Annual fixed cost:      ${annual_fixed_cost:,.2f}")
print(f"Annual shipping cost:   ${shipping_spend:,.2f}")
print(f"Annual handling cost:   ${handling_spend:,.2f}")
print(f"FIRST-YEAR TOTAL COST:  ${total_cost:,.2f}")


# ==================================================
# 9. DISPLAY SHIPMENT PLAN
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
# 10. DISPLAY PEAK CAPACITY UTILIZATION
# ==================================================

print("\nPEAK CAPACITY UTILIZATION")

for f in facilities:
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
# 11. DISPLAY DELIVERY METRICS
# ==================================================

fast_units = pulp.value(fast_volume)
coverage = fast_units / total_demand

weighted_delivery_days = sum(
    delivery_days[f, r] * x[f, r].value()
    for f in facilities
    for r in regions
) / total_demand

service_gap_pp = max(
    0,
    (comparison_service_target - coverage) * 100,
)

print("\nDELIVERY METRICS")
print(f"Total demand:            {total_demand:,.0f} units/week")
print(f"Units within two days:   {fast_units:,.2f} units/week")
print(f"Two-day coverage:        {coverage:.1%}")
print(f"Weighted delivery time:  {weighted_delivery_days:.2f} days")
print(
    f"Comparison target:       {comparison_service_target:.1%} "
    "(not enforced)"
)
print(f"Service gap:             {service_gap_pp:.1f} percentage points")