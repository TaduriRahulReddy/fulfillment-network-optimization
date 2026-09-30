# Fulfillment Network Optimization

An operations analytics project using Python, PuLP 4, and the free
CBC solver to optimize facility locations, shipment allocation,
and capacity planning.

All data and network assumptions are synthetic and intended for
educational purposes.

## Business question

Which fulfillment centers should open, and how should demand be
allocated to minimize cost while providing two-day delivery
coverage to at least 90% of shipment units?

How does the recommended network perform as demand grows or
varies across regions?

## Network

- Two existing centers: New Jersey and California
- Three candidate sites: Ohio, Texas, and Georgia
- Eight customer regions
- Forty outbound shipping lanes
- One standardized bulky-item category

## Optimization model

The expansion model is a mixed-integer linear program (MILP) with
40 continuous shipment variables, 3 binary opening decisions,
and 15 business constraints.

The objective minimizes:

- One-time facility opening costs
- Annual fixed operating costs
- Shipping costs
- Handling costs

Constraints enforce:

- Exact regional demand fulfillment
- Peak-week facility capacity
- Zero shipments from unopened facilities
- At least 90% demand-weighted two-day delivery coverage
- A $2.4 million opening budget

Average weekly shipments are multiplied by 1.2 to test peak
capacity and by 52 to calculate annual variable costs.

## Baseline comparison

| Metric | Existing-only baseline | Open Georgia |
|---|---:|---:|
| First-year cost | $13,645,400 | $11,991,280 |
| Two-day coverage | 52.14% | 92.86% |

Opening Georgia reduces modeled first-year costs by
$1,654,120, or 12.1%.

The baseline fulfills the same demand and respects peak capacity
but measures delivery coverage without enforcing the 90% target.
It is an optimized existing-network benchmark, not observed
company performance.

## Demand-growth sensitivity analysis

Demand grows proportionally across regions. Each scenario
reoptimizes facility openings and shipment allocation.

| Growth | Weekly demand | New sites | First-year cost | Optimized coverage | Georgia-only maximum |
|---|---:|---|---:|---:|---:|
| 0% | 1,400 | GA | $11,991,280.00 | 92.86% | 92.86% |
| 5% | 1,470 | GA | $12,442,050.64 | 92.61% | 92.61% |
| 10% | 1,540 | GA | $12,973,854.64 | 91.19% | 91.19% |
| 10.5% | 1,547 | GA | $13,027,035.04 | 91.06% | 91.06% |
| 11% | 1,554 | GA | $13,080,215.44 | 90.92% | 90.92% |
| 11.5% | 1,561 | GA | $13,133,395.84 | 90.79% | 90.79% |
| 12% | 1,568 | GA | $13,186,576.24 | 90.66% | 90.66% |
| 12.5% | 1,575 | GA | $13,239,756.64 | 90.53% | 90.53% |
| 13% | 1,582 | GA | $13,292,937.04 | 90.40% | 90.40% |
| 13.5% | 1,589 | GA | $13,346,117.44 | 90.27% | 90.27% |
| 14% | 1,596 | GA | $13,399,297.84 | 90.15% | 90.15% |
| 14.5% | 1,603 | GA | $13,452,478.24 | 90.02% | 90.02% |
| 15% | 1,610 | TX + GA | $13,700,400.00 | 100.00% | 89.90% |
| 20% | 1,680 | TX + GA | $14,085,200.00 | 100.00% | 88.71% |
| 25% | 1,750 | TX + GA | $14,493,400.00 | 100.00% | 86.19% |
| 30% | 1,820 | TX + GA | $14,907,216.00 | 100.00% | 83.53% |

![Network sensitivity](figures/network_sensitivity.png)

Georgia alone meets the target at 14.5% growth, with approximately
90.02% maximum coverage. At 15% growth, its maximum falls to
89.90%, and the least-cost expansion model selects Texas plus Georgia.

The tested investment trigger is above 14.5% and at or below
15% growth. This is a grid result, not an exact threshold.

## Capacity and delivery stress test

At 25% demand growth, the Georgia-only network has enough total
capacity but cannot meet the delivery target.

- Average weekly demand: 1,750 units
- Peak weekly demand: 2,100 units
- Total network capacity: 2,300 units
- Maximum two-day delivery coverage: 86.19%
- Fast-delivery shortfall: 66.67 units per average week

A separate coverage-maximizing LP identifies the service limit.
Spare California capacity cannot compensate for constrained
capacity on faster delivery lanes.

The optimized Texas-plus-Georgia network achieves 100% two-day
coverage at this growth level.

## Monte Carlo demand simulation

The simulation evaluates two fixed networks under uncertain demand:

1. New Jersey + California + Georgia
2. New Jersey + California + Texas + Georgia

### Method

- Generate 1,000 weekly demand scenarios.
- Set expected regional demand 15% above the baseline.
- Apply a shared demand shock and independent regional shocks.
- Use correlated lognormal demand with a mean correction.
- Set shared and regional log-scale standard deviations to 0.10.
- Use Python's random generator with seed 42.
- Evaluate both networks against identical demand scenarios.
- Use CBC to minimize weekly shipping and handling costs
  after observing demand.

A successful scenario fulfills all regional demand, respects
facility capacity, and meets the 90% two-day delivery target.

Facility openings remain fixed; shipment allocation can change
between scenarios.

### Results

| Network | Successful weeks | Infeasible weeks | Success rate | Wilson 95% interval |
|---|---:|---:|---:|---:|
| Georgia only | 943 / 1,000 | 57 | 94.30% | 92.69%–95.57% |
| Texas + Georgia | 1,000 / 1,000 | 0 | 100.00% | 99.62%–100.00% |

| Network | Mean weekly shipping and handling cost, conditional on feasibility |
|---|---:|
| Georgia only | $190,572.22 |
| Texas + Georgia | $170,495.74 |

Georgia alone fails in 5.7% of sampled weeks. Texas plus Georgia
meets the requirements in every sampled week.

No failures in 1,000 samples does not guarantee future success.
Confidence intervals measure Monte Carlo sampling uncertainty,
not uncertainty about the demand assumptions.

Costs exclude opening and fixed operating costs. Each average
uses that network's feasible weeks, so the figures do not establish
investment savings or return on investment.

### Relationship to the peak stress test

The planning model applies a 1.2 multiplier to average weekly
demand to test peak capacity.

The simulation samples actual weekly demand and compares it
directly with weekly capacity. It does not apply the peak
multiplier again.

These analyses use different demand assumptions, so their
feasibility results should not be interpreted as contradictory.

## Project files

| File | Purpose |
|---|---|
| `network_optimization.py` | Current-demand expansion MILP |
| `baseline_network.py` | Existing-only benchmark |
| `demand_growth_scenario.py` | Expansion at 25% demand growth |
| `georgia_only_stress_test.py` | Fixed-network feasibility and maximum coverage |
| `growth_sensitivity.py` | Broad demand-growth scenarios |
| `growth_threshold.py` | Refined growth scenarios |
| `project_summary.py` | Comparison chart and README generation |
| `monte_carlo_simulation.py` | Uncertain-demand simulation with fixed networks |
| `growth_sensitivity_results.csv` | Broad growth results |
| `growth_threshold_results.csv` | Refined growth results |
| `monte_carlo_results.csv` | Demand and outcomes for each simulated week |
| `monte_carlo_summary.json` | Simulation assumptions and summary statistics |
| `figures/network_sensitivity.png` | Growth comparison chart |

## Setup

Use Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "pulp[cbc]" matplotlib
```

On Apple Silicon macOS, install Homebrew CBC:

```bash
brew install cbc
```

The solver scripts use `/opt/homebrew/bin/cbc`.
Change that path when running on another machine.

The simulation uses Python's standard library and PuLP;
no additional simulation package is required.

## Run

```bash
python network_optimization.py
python baseline_network.py
python demand_growth_scenario.py
python georgia_only_stress_test.py
python growth_sensitivity.py
python growth_threshold.py
python project_summary.py
python monte_carlo_simulation.py
```

The simulation performs 2,000 CBC solves:
1,000 demand scenarios for each of the two networks.

## Validation

CBC reported optimal solutions for the baseline, expansion,
and demand-growth scenarios.

A separate coverage-maximizing LP quantified the Georgia-only
network's service limit when the delivery requirement was infeasible.

The simulation checks shipment nonnegativity, regional demand
fulfillment, capacity, and delivery coverage before reporting
a successful solution. Infeasible weeks are recorded without
fabricated costs or shipment allocations.

CBC's optimization log excludes the constant $2 million
existing-center cost. The Python planning cost report includes it.

## Assumptions and limitations

- All numeric inputs and network assumptions are synthetic.
- Delivery times are deterministic.
- Coverage measures planned shipment speed, not actual on-time reliability.
- Inventory and replenishment are assumed sufficient.
- Inbound freight, inventory carrying costs, and SKU differences are excluded.
- Candidate facilities can open immediately.
- Opening costs are one-time; fixed operating costs recur annually.
- Growth scenarios reconsider investment decisions.
- Fractional shipments represent average planning volumes.
- Peak planning preserves average-week regional allocation proportions.
- Simulation demand volatility is assumed rather than fitted to historical data.
- Simulated weeks are independent; serial demand patterns are excluded.
- Simulation permits routing adjustments after demand is observed.
- Simulation results are conditional on the selected demand assumptions.

## Recommendation

Open Georgia for current demand under the modeled assumptions.
Prepare further expansion before growth reaches the peak-planning
delivery limit between 14.5% and 15%.

Monte Carlo results provide additional evidence that Texas plus
Georgia is more resilient to the modeled demand uncertainty.

Actual investment timing requires construction lead times,
historical demand validation, demand forecasts, and a multi-year
financial evaluation.