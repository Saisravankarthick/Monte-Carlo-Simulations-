# Cash-flow Monte Carlo for a liability-driven portfolio

Code and analysis only. It estimates how much a portfolio could be worth on 1 January 2033 given dated
contributions (1 Jan 2027 and 1 Jan 2028), and compares that with the reserve needed to pay ten annual
payments (annuity-due). It reports a funding ratio, the chance of a shortfall, a range for what is left
over for a contribution (with confidence levels), and what happens if there is a large fall in 2031–2032.

**The written strategy and IPS are not in this repository.** The sleeve weights and glide path are inputs
the team chooses. The example config is a **placeholder** that shows the mechanics; it is not a recommendation.

## Run it

On GitHub: **Actions → Run simulation → Run workflow**. It runs the tests, then the simulation, and commits
the `results/` folder (report, charts, tables).

Locally (needs internet for Yahoo Finance prices):

```bash
uv run python -m mcsim --config config/example_placeholder.toml --out results
uv run --with pytest python -m pytest -q      # the correctness tests
```

To use your own strategy, copy `config/example_placeholder.toml`, edit the sleeves, glide path and scenarios,
and set `placeholder = false`.

## What you get

`results/RESULTS.md` is the report: an at-a-glance table, then every chart embedded under its section.
Files are sorted by category:

```
results/
├── RESULTS.md                      the report (open this first)
├── charts/
│   ├── 1_inputs/                   glide path (stacked bars), sampled history by sleeve (bars)
│   ├── 2_paths/                    150 simulated futures per scenario (one colour each), percentile fans
│   ├── 3_outcomes/                 histogram of the value on the valuation date, coloured against the reserve
│   ├── 4_funding/                  shortfall chance (grouped bars), contribution at 80/90/95% confidence (bars),
│   │                               contribution ranges (floating bars)
│   └── 5_risk/                     worst fall in the stress window (histogram), regime mix (stacked bars)
└── tables/                         the same numbers as CSV: portfolio_values, funding_and_contribution, risk
```

Code layout: `mcsim/core.py` (maths), `data.py` (prices), `plots.py` (charts), `tables.py` (CSV),
`report.py` (RESULTS.md), `style.py` (colours); `config/` (inputs); `tests/` (checks).

## How it works, in plain words

1. **Sleeves.** The portfolio has three parts: *growth*, *matching* (bonds that fund the payments) and *flex*
   (short-duration, cash-like). Each is a basket of tickers; the tickers only supply the realistic *shape* of daily
   returns (how bumpy, how they move together).
2. **Resampling.** Blocks of 20 real trading days are drawn at random from the last 15 years and stitched into 6-year
   futures. All sleeves are drawn on the same dates, so their co-movement is kept. 10,000 futures are built.
3. **Cash flows.** Each 1 January the contribution is added and the portfolio is rebalanced to that year's glide-path
   weights. Between rebalances the sleeves drift.
4. **Funding test.** On 1 Jan 2033, reserve = PV of ten payments of $50,000 at the start of each year
   `PMT × [(1 − (1+r)^−n) ÷ r] × (1+r)`, for several assumed reserve returns r. Funding ratio = value ÷ reserve.
   Contribution capacity = value − reserve − flexibility amount.
5. **Scenarios.** Historical averages kept, a haircut of some points a year on a sleeve, or the team's own stated
   expected returns (history supplies only the shape).
6. **Regime days.** The growth sleeve's days are labelled Bull / Sideways / Bear with a 20-day return rule (±2%)
   and counted. This links the simulation to the regime analysis in the Markov-Model repository.

## What it is not

- It is **not Markov chain Monte Carlo (MCMC)** in the technical sense (a sampling method from Bayesian statistics).
  It is a **block-bootstrap Monte Carlo simulation**. The regime labelling is a separate, simple Markov-style
  description of the data.
- The reserve return is a fixed assumption. Yields at the time the reserve is bought are not simulated.
- No taxes, trading costs or inflation. Payments are fixed in nominal dollars.
- Results are ranges under stated assumptions, not predictions.

## How it was checked

`tests/` (14 tests) checks answers that can be worked out by hand: the reserve at each rate matches the
case study's table ($500,000 / $458,112 / $439,305 / $421,767 …); contributions grow to $450,000 at 0% and
$562,094 at 4%; a simulation with no randomness equals the closed-form value; sleeve weighting; a built-in
crash is detected in the right window; resampling keeps correlation and mean; the same seed reproduces the same
result; invalid glide paths are rejected; every chart, table and link in the report is produced.

## AI-assistance disclosure

This code was written with the help of an AI assistant (Claude, Anthropic) in conversation with the repository owner.
The owner chose the question, the case inputs, the scenarios and what to cite. Anything from this repository used in
a competition deliverable should be cited as AI-assisted, with the specific outputs used and how they were used.
Every figure should be re-verified by the team before it is used.
