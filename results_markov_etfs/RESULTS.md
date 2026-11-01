# Monte Carlo: the Markov model ETFs

Updated 2026-11-01 01:26 UTC · **$10,000 today** in each fund, over **10 years** · 10,000 simulated futures per fund · blocks of 20 real trading days · seed 42

> Research tool, not advice. Each fund's futures are stitched together from that fund's own past, so they show what the past implies, not what will happen.

> ⚠ Short history (under 8 years): QQQM, SGOV. These have not been through a full crash cycle, so their predictions are less reliable.

**Contents:** [1. Bar diagrams](#1-bar-diagrams) · [2. Simulation prediction](#2-simulation-prediction) · [Notes](#notes)

## 1. Bar diagrams

Funds are sorted by their median value after 10 years if history repeats. Total invested: $10,000.

### 1a. Where the money could end up

![Outcome ranges](charts/1_bar_diagrams/outcome_ranges.png)

### 1b. History repeats vs a tougher future

Blue: futures built from each fund's own past. Red: the same with 3.25 points a year taken off.

![History vs stress](charts/1_bar_diagrams/history_vs_stress.png)

### 1c. Chance of losing money

![Chance of loss](charts/1_bar_diagrams/chance_of_loss.png)

### 1d. How often big falls happen

Chance of at least one peak-to-trough fall of each size during the period.

![Chance of big falls](charts/1_bar_diagrams/chance_of_big_falls.png)

### 1e. Bull, Sideways and Bear time (same regime rule as the Markov model)

![Regime mix](charts/1_bar_diagrams/regime_mix.png)

## 2. Simulation prediction

### 2a. Predicted value, median (range in brackets = 5th to 95th percentile)

| Fund | What it is | Year 1 | Year 3 | Year 5 | Year 10 | Growth a year | Chance of loss | Today |
|---|---|---|---|---|---|---|---|---|
| **QQQM** | US tech-heavy (Nasdaq-100) | **$11,807** ($8,385 – $16,197) | **$16,497** ($9,180 – $28,844) | **$22,806** ($10,808 – $46,919) | **$52,081** ($18,133 – $141,775) | 17.9% | 1% | Bear |
| **AAAU** | Gold | **$11,588** ($8,941 – $15,122) | **$15,665** ($9,944 – $24,737) | **$21,072** ($11,834 – $37,846) | **$44,455** ($19,846 – $101,707) | 16.1% | 0% | Bear |
| **VOO** | US large-cap (S&P 500) | **$11,605** ($8,847 – $14,371) | **$15,309** ($9,716 – $22,538) | **$20,160** ($11,235 – $33,646) | **$40,345** ($18,008 – $84,383) | 15.0% | 0% | Sideways |
| **SCHD** | US dividend payers | **$11,392** ($8,956 – $14,014) | **$14,657** ($9,637 – $21,062) | **$18,862** ($10,953 – $30,776) | **$35,266** ($16,665 – $69,913) | 13.4% | 0% | Bull |
| **EWT** | Taiwan | **$11,200** ($7,519 – $16,103) | **$13,969** ($7,017 – $26,681) | **$17,266** ($7,324 – $40,476) | **$29,815** ($8,985 – $96,438) | 11.5% | 7% | Bear |
| **VTI** | US total market | **$11,203** ($8,110 – $14,457) | **$13,799** ($8,027 – $21,806) | **$16,911** ($8,624 – $30,857) | **$28,418** ($11,101 – $67,649) | 11.0% | 4% | Sideways |
| **RSP** | US equal-weight S&P 500 | **$11,107** ($7,770 – $14,638) | **$13,414** ($7,337 – $22,056) | **$16,051** ($7,603 – $31,085) | **$25,481** ($9,113 – $64,725) | 9.8% | 7% | Bull |
| **EQAL** | US equal-weight Russell 1000 | **$11,112** ($8,041 – $14,315) | **$13,319** ($7,704 – $21,057) | **$16,048** ($7,938 – $29,425) | **$25,219** ($9,358 – $61,058) | 9.7% | 6% | Bull |
| **VTV** | US value | **$11,020** ($8,003 – $14,067) | **$13,144** ($7,781 – $20,349) | **$15,611** ($8,084 – $27,795) | **$24,113** ($9,768 – $55,138) | 9.2% | 5% | Bull |
| **XLU** | US utilities | **$10,913** ($7,987 – $13,942) | **$12,717** ($7,696 – $19,697) | **$14,881** ($7,912 – $26,364) | **$21,745** ($9,015 – $49,820) | 8.1% | 7% | Bull |
| **XLE** | US energy | **$10,961** ($6,529 – $16,628) | **$12,651** ($5,113 – $26,926) | **$14,565** ($4,795 – $39,133) | **$21,098** ($4,279 – $85,856) | 7.8% | 21% | Bull |
| **VXUS** | International excluding the US | **$10,731** ($8,065 – $13,714) | **$12,235** ($7,502 – $18,806) | **$13,841** ($7,456 – $24,128) | **$18,753** ($7,839 – $41,466) | 6.5% | 12% | Bear |
| **HYG** | US high-yield corporate bonds | **$10,532** ($8,647 – $12,381) | **$11,554** ($8,355 – $15,469) | **$12,693** ($8,415 – $18,681) | **$15,963** ($9,060 – $27,621) | 4.8% | 8% | Sideways |
| **SGOV** | US Treasury bills, 0-3 months (cash-like) | **$10,303** ($10,198 – $10,400) | **$10,934** ($10,744 – $11,121) | **$11,605** ($11,345 – $11,859) | **$13,468** ($13,049 – $13,886) | 3.0% | 0% | Sideways |
| **IEF** | US Treasuries, 7-10 years | **$10,308** ($9,253 – $11,515) | **$10,934** ($9,123 – $13,227) | **$11,603** ($9,147 – $14,847) | **$13,444** ($9,594 – $19,019) | 3.0% | 8% | Bull |
| **SCHP** | US inflation-protected Treasuries (TIPS) | **$10,272** ($9,404 – $11,160) | **$10,790** ($9,331 – $12,499) | **$11,363** ($9,369 – $13,674) | **$12,937** ($9,862 – $16,794) | 2.6% | 6% | Bull |
| **TLT** | US Treasuries, 20+ years | **$10,247** ($8,217 – $12,981) | **$10,803** ($7,380 – $15,913) | **$11,293** ($6,958 – $18,884) | **$12,751** ($6,413 – $26,534) | 2.5% | 28% | Bull |
| **VGIT** | US Treasuries, 3-10 years | **$10,193** ($9,533 – $10,901) | **$10,609** ($9,452 – $11,937) | **$11,057** ($9,520 – $12,849) | **$12,212** ($9,873 – $15,152) | 2.0% | 6% | Bull |
| **SHY** | US Treasuries, 1-3 years | **$10,186** ($9,953 – $10,449) | **$10,573** ($10,144 – $11,046) | **$10,971** ($10,401 – $11,601) | **$12,038** ($11,172 – $13,002) | 1.9% | 0% | Sideways |

*Today* = regime from the last 20 trading days (Bull above +2%, Bear below −2%).

### 2b. Predicted range over time

![Prediction fans](charts/2_simulation_prediction/prediction_fans.png)

### 2c. Sample simulated futures

![Simulated futures](charts/2_simulation_prediction/simulated_futures_all_funds.png)

### 2d. Distribution of final values

![Outcome distributions](charts/2_simulation_prediction/outcome_distributions.png)

## Notes

| Fund | History used | Years | Growth a year | Volatility | Worst fall |
|---|---|---|---|---|---|
| QQQM | 2020-10-14 to 2026-10-30 | 6.0 ⚠ short | 15.9% | 22.2% | -35% |
| AAAU | 2018-08-16 to 2026-10-30 | 8.2 | 15.5% | 17.5% | -28% |
| VOO | 2010-09-10 to 2026-10-30 | 16.1 | 14.7% | 16.9% | -34% |
| SCHD | 2011-10-21 to 2026-10-30 | 15.0 | 13.8% | 15.3% | -33% |
| EWT | 2006-11-02 to 2026-10-30 | 20.0 | 11.4% | 25.6% | -63% |
| VTI | 2006-11-02 to 2026-10-30 | 20.0 | 10.9% | 19.6% | -55% |
| RSP | 2006-11-02 to 2026-10-30 | 20.0 | 9.9% | 20.7% | -60% |
| EQAL | 2014-12-26 to 2026-10-30 | 11.8 | 9.3% | 18.3% | -40% |
| VTV | 2006-11-02 to 2026-10-30 | 20.0 | 9.3% | 19.3% | -59% |
| XLU | 2006-11-02 to 2026-10-30 | 20.0 | 8.2% | 19.0% | -46% |
| XLE | 2006-11-02 to 2026-10-30 | 20.0 | 7.9% | 30.0% | -71% |
| VXUS | 2011-01-31 to 2026-10-30 | 15.7 | 6.4% | 17.7% | -36% |
| HYG | 2007-04-12 to 2026-10-30 | 19.5 | 4.8% | 10.8% | -34% |
| SGOV | 2020-06-02 to 2026-10-30 | 6.4 ⚠ short | 3.0% | 0.2% | -0% |
| IEF | 2006-11-02 to 2026-10-30 | 20.0 | 3.1% | 6.9% | -24% |
| SCHP | 2010-08-06 to 2026-10-30 | 16.2 | 2.7% | 5.5% | -14% |
| TLT | 2006-11-02 to 2026-10-30 | 20.0 | 2.7% | 15.0% | -48% |
| VGIT | 2009-11-24 to 2026-10-30 | 16.9 | 2.1% | 4.4% | -16% |
| SHY | 2006-11-02 to 2026-10-30 | 20.0 | 1.9% | 1.5% | -6% |

- Funds with different history lengths are compared side by side; the longer ones include crises the shorter ones never saw.
- No taxes, inflation or currency effects beyond what is in the fund prices.
- The tougher case simply subtracts 3.25 points a year from every fund; it is a sensitivity check, not a forecast.

**Files:** [`outcome_ranges.png`](charts/1_bar_diagrams/outcome_ranges.png), [`history_vs_stress.png`](charts/1_bar_diagrams/history_vs_stress.png), [`chance_of_loss.png`](charts/1_bar_diagrams/chance_of_loss.png), [`chance_of_big_falls.png`](charts/1_bar_diagrams/chance_of_big_falls.png), [`prediction_fans.png`](charts/2_simulation_prediction/prediction_fans.png), [`simulated_futures_all_funds.png`](charts/2_simulation_prediction/simulated_futures_all_funds.png), [`outcome_distributions.png`](charts/2_simulation_prediction/outcome_distributions.png), [`regime_mix.png`](charts/1_bar_diagrams/regime_mix.png) · [`fund_summary.csv`](tables/fund_summary.csv), [`prediction_by_year.csv`](tables/prediction_by_year.csv), [`correlation.csv`](tables/correlation.csv)
