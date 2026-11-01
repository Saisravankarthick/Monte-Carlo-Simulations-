# ETF Monte Carlo research

A research tool for comparing markets through their ETFs. For each fund it simulates thousands of possible
futures for an investment (a lump sum today, optionally plus a fixed amount every month) and compares the funds on:

- **where the money could end up** (median and 5th–95th percentile range)
- **growth a year**, and how much it varies
- **chance of losing money** over the horizon
- **how deep the falls get** (typical worst fall; chance of falls worse than −20%, −30%, −40%)
- **regime mix** (share of Bull / Sideways / Bear days) and the regime each fund is in today
- **diversification** (how the funds move together)

It is a research tool, not advice: every simulated future is built from each fund's own past.

## Run it

On GitHub: **Actions → Run simulation → Run workflow**. It runs the tests, then the simulation, and commits
the `results/` folder.

Locally (needs internet for Yahoo Finance prices):

```bash
uv run python -m mcsim --config config/etf_research.toml --out results
uv run --with pytest python -m pytest -q
```

Edit `config/etf_research.toml` to change the funds, the amount, monthly additions, the horizon, the number of
simulated futures, or the stress case. Fixed-weight mixes of funds can be added under `[mixes]`.

## What you get

`results/RESULTS.md` is the report: a ranked at-a-glance table, then every chart under its section.

```
results/
├── RESULTS.md                     the report (open this first)
├── charts/
│   ├── 1_overview/                outcome ranges per fund (floating bars); history vs stress (grouped bars)
│   ├── 2_risk_return/             growth vs worst fall (scatter); chance of loss (bars); chance of big falls (grouped bars)
│   ├── 3_paths/                   60 simulated futures per fund, one colour per path (small multiples)
│   ├── 4_distributions/           where the money ends up, red below / green above the amount invested
│   ├── 5_regimes/                 Bull / Sideways / Bear mix (stacked bars) and today's regime
│   └── 6_diversification/         correlation heatmap
└── tables/                        fund_summary.csv and correlation.csv: every number above
```

Code: `mcsim/core.py` (simulation maths), `data.py` (prices), `plots.py` (charts), `tables.py` (CSV),
`report.py` (RESULTS.md), `style.py` (colours); `config/` (inputs); `tests/` (checks).

## How it works

1. **Prices.** Daily dividend-adjusted closes from Yahoo Finance, over `history_years` per fund (less if the fund is younger).
   `config/etf_research.toml` uses 20 years; `config/markov_etfs.toml` uses 10, the same window as the Markov model repo.
2. **Resampling.** Blocks of 20 real consecutive trading days are drawn at random from a fund's history and stitched
   into a future of the chosen length. Blocks keep short-term momentum and volatility clustering. Repeated
   10,000 times per fund. Mixes are built from their members' returns on shared dates, so co-movement is kept.
3. **Money.** The lump sum buys on day 1; each monthly addition buys at that day's simulated price.
4. **Measures.** Value at the end (against the total invested), growth a year of the price path, worst
   peak-to-trough fall, and regime days (20-day return above +2% = Bull, below −2% = Bear, otherwise Sideways).
5. **Stress case.** The same simulation with a fixed number of points a year subtracted from every fund.

This is a **block-bootstrap Monte Carlo simulation**. It is not Markov chain Monte Carlo (MCMC), which is a sampling
method from Bayesian statistics; the regime labels are a separate, simple description of each path.

## Limits

- The past is the only source of randomness, so a decade dominated by one kind of market shapes every simulated future.
- Funds with different history lengths are compared side by side; younger funds have seen fewer crises (flagged in the report).
- Nothing longer than a 20-day block is carried over (for example, multi-year cycles).
- No taxes, currency effects beyond what is in the price, or inflation.

## Checking the data

**Actions → Data audit → Run workflow** re-downloads the Yahoo prices and checks them against the Markov model
repo's report (`data/markov_stats.json`, a copy of that repo's `report/stats.json`). It recomputes rows, regime now,
long-run regime mix, buy-and-hold worst fall and Sharpe for every fund, checks the simulation's inputs against the
same prices, and lists the biggest one-day moves and any gaps. The result is `data_check/DATA_CHECK.md`.
Refresh `data/markov_stats.json` whenever the Markov repo's report is updated.

## Metropolis-Hastings on the ETFs

`mcsim/mh_etfs.py` fits a model to each ETF in `config/markov_etfs.toml` with Metropolis-Hastings (Markov chain
Monte Carlo, engine in `mcsim/metropolis.py`). Daily log returns follow a skewed Student-t (fat tails, bigger falls
than rises); four Markov chains per fund draw the plausible combinations of return, risk, tails and skew. The report
shows each fund's long-run growth and volatility as ranges, and a 10-year prediction in which every simulated future
draws its own parameters, so the range includes how unsure ten years of data leave us.
`mcsim/mh_audit.py` then checks the algorithm against exact answers, recovery of known parameters on made-up data,
the data, convergence, seed stability, fit and the prediction step.

On GitHub: **Actions → Metropolis-Hastings ETFs → Run workflow** (downloads prices, fits, predicts, audits, commits
[`results_mh_etfs/`](results_mh_etfs/RESULTS.md) with [`AUDIT.md`](results_mh_etfs/AUDIT.md)).

## How it was checked

`tests/` (12 tests): with no randomness the simulation equals compound growth, with and without monthly additions;
a stress haircut lowers growth by about that many points; a built-in crash is caught at exactly the right depth;
regime counting follows the rule; the same seed reproduces the same result; resampling keeps the mean and the
correlation between funds; percentiles and probabilities are ordered sensibly; every chart, table and report link exists.

## AI-assistance disclosure

This code was written with the help of an AI assistant (Claude, Anthropic) in conversation with the repository owner,
who chose the research question, the funds and the settings. Cite it as AI-assisted wherever its outputs are used.
