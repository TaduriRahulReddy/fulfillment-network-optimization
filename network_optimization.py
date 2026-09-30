import pulp


# ==================================================
# 1. INPUT DATA — SYNTHETIC LEARNING CASE
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

# Maximum peak-week capacity: units
capacity = {
    "NJ": 900,
    "CA": 850,
    "OH": 550,
    "TX": 600,
    "GA": 550,
}

# Annual fixed operating cost: USD
fixed_cost = {
    "NJ": 900_000,
    "CA": 1_100_000,
    "OH": 750_000,
    "TX": 800_000,
    "GA": 700_000,
}

# One-time opening cost: USD
opening_cost = {
    "OH": 650_000,
    "TX": 750_000,
    "GA": 600_000,
}

# Handling cost per unit: USD
handling_cost = {
    "NJ": 18,
    "CA": 21,
    "OH": 17,
    "TX": 18,
    "GA": 16,
}

# Shipping costs follow the same order as "regions".
shipping_rows = {
    "NJ": [90, 65, 170, 220, 150, 240, 270, 390],
    "CA": [390, 410, 320, 340, 250, 230, 170, 60],
    "OH": [140, 130, 150, 200, 70, 190, 220, 310],
    "TX": [270, 280, 160, 210, 190, 60, 140, 240],
    "GA": [210, 200, 60, 120, 170, 150, 220, 330],
}

# Assumed order-to-door delivery times: days
delivery_rows = {
    "NJ": [1, 1, 3, 4, 2, 4, 5, 7],
    "CA": [7, 7, 6, 6, 4, 4, 3, 1],
    "OH": [2, 2, 2, 3, 1, 3, 4, 6],
    "TX": [5, 5, 2, 3, 3, 1, 2, 4],
    "GA": [3, 3, 1, 2, 2, 2, 4, 6],
}

# Dictionaries indexed by (facility, region)
shipping_cost = {
    (facility, region): shipping_rows[facility][i]
    for facility in facilities
    for i, region in enumerate(regions)
}

delivery_days = {
    (facility, region): delivery_rows[facility][i]
    for facility in facilities
    for i, region in enumerate(regions)
}

weeks_per_year = 52
peak_factor = 1.20
service_target = 0.90
delivery_limit = 2
opening_budget = 2_400_000

total_demand = sum(demand.values())


# ==================================================
# 2. CREATE THE MODEL AND DECISION VARIABLES
# ==================================================

model = pulp.LpProblem(
    "Fulfillment_Network_2027",
    pulp.LpMinimize,
)

# PuLP 4 creates variables through the model.

# x[facility, region]: average weekly shipment quantity
x = model.add_variable_dicts(
    "shipment",
    [(f, r) for f in facilities for r in regions],
    lowBound=0,
    cat=pulp.LpContinuous,
)

# z[facility]: 1 if a candidate opens, otherwise 0
z = model.add_variable_dicts(
    "open",
    candidates,
    cat=pulp.LpBinary,
)


# ==================================================
# 3. OBJECTIVE: MINIMIZE FIRST-YEAR TOTAL COST
# ==================================================

# Existing facilities remain open.
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

# Each region receives exactly its weekly demand.
for r in regions:
    model += (
        pulp.lpSum(x[f, r] for f in facilities) == demand[r],
        f"demand_{r}",
    )


# ==================================================
# 5. CAPACITY AND OPENING CONSTRAINTS
# ==================================================

# Peak volumes are 20% above the average weekly plan.
for f in facilities:
    peak_volume = peak_factor * pulp.lpSum(
        x[f, r] for r in regions
    )

    if f in candidates:
        # A closed candidate has zero usable capacity.
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

# Count only units on lanes delivering within two days.
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
        'CBC was not found. In your active virtual environment, '
        'run: python -m pip install --upgrade "pulp[cbc]"'
    )

# PuLP 4 returns an object containing solve status.
stats = model.solve(solver)

print("\nSolver status:", stats.status_str)

if (
    stats.status != pulp.LpSolveStatus.Optimal
    or not stats.has_solution
):
    raise SystemExit(
        "No proven optimal solution. Check the solver log, "
        "capacity, delivery target, and opening budget."
    )


# ==================================================
# 9. DISPLAY COSTS
# ==================================================

opened = [
    f for f in candidates
    if z[f].value() > 0.5
]

opening_spend = pulp.value(candidate_opening_cost)

annual_fixed_spend = (
    existing_fixed_cost
    + pulp.value(candidate_fixed_cost)
)

shipping_spend = pulp.value(annual_shipping_cost)
handling_spend = pulp.value(annual_handling_cost)
total_cost = pulp.value(model.objective)

print("\nCOST BREAKDOWN")
print(f"One-time opening cost:  ${opening_spend:,.2f}")
print(f"Annual fixed cost:      ${annual_fixed_spend:,.2f}")
print(f"Annual shipping cost:   ${shipping_spend:,.2f}")
print(f"Annual handling cost:   ${handling_spend:,.2f}")
print(f"FIRST-YEAR TOTAL COST:  ${total_cost:,.2f}")


# ==================================================
# 10. DISPLAY FACILITY DECISIONS
# ==================================================

print("\nFACILITY DECISIONS")
print("NJ: EXISTING — REMAINS OPEN")
print("CA: EXISTING — REMAINS OPEN")

for f in candidates:
    decision = "OPEN" if f in opened else "DO NOT OPEN"
    print(f"{f}: {decision}")


# ==================================================
# 11. DISPLAY SHIPMENT PLAN
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
# 12. DISPLAY PEAK CAPACITY UTILIZATION
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
# 13. DISPLAY DELIVERY COVERAGE
# ==================================================

fast_units = pulp.value(fast_volume)
coverage = fast_units / total_demand

weighted_delivery_days = sum(
    delivery_days[f, r] * x[f, r].value()
    for f in facilities
    for r in regions
) / total_demand

print("\nDELIVERY METRICS")
print(f"Total demand:             {total_demand:,.0f} units/week")
print(f"Units within two days:    {fast_units:,.2f} units/week")
print(f"Two-day coverage:         {coverage:.1%}")
print(f"Required coverage:        {service_target:.1%}")
print(f"Weighted delivery time:   {weighted_delivery_days:.2f} days")