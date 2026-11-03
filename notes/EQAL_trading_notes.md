# EQAL trading notes

Invesco Russell 1000 Equal Weight ETF · data to the **30 Oct 2026 close** (59.17) · written 3 Nov 2026

> Research notes, not advice. Prices are Yahoo Finance, dividend-adjusted. Numbers marked *(computed)* come from the repo's returns data; economic figures come from web sources I could not check against the official releases (listed at the end).

## 1. One-paragraph view

EQAL is in a **calm, mild uptrend** (price above its 200-day average, 3.9% below its August high, volatility about half its long-run level) and sits right on the **Bull/Sideways line** of the Markov model. It has been **beating cap-weighted US stocks over the last 12 months** as leadership broadened, but it **lagged them over the last 10 years**. The economic backdrop is **strong growth with re-accelerating inflation and a Fed that has started hiking again**, which supports earnings but pressures valuations and rate-sensitive sectors. The data favours holding a diversified position over trying to time it; the risks are a rate shock and a return of mega-cap leadership.

## 2. What the data says *(computed)*

| Measure | Value | Read |
|---|---|---|
| Last close | 59.17 | |
| 52-week range | 48.97 (20 Nov 2025) to 61.57 (14 Aug 2026) | 3.9% below the high, 20.8% above the low |
| vs 20 / 50 / 100 / 200-day average | +0.9% / 0.0% / −0.1% / +2.6% | Flat against the 50 and 100-day, above the 200-day: sideways drift inside an uptrend |
| Return: 20 days / 60 days / 6 months / 12 months | +2.0% / −1.5% / +2.7% / +16.2% | Strong year, stalled since August |
| 3-year return a year | +18.2% | |
| 10-year return a year | +10.8% | |
| Volatility: 20-day / 1-year / 10-year | 10.4% / 11.6% / 18.8% | Unusually calm |
| Worst fall in the window | −40% (Feb–Mar 2020) | |
| Worst single day / best | −11.3% (16 Mar 2020) / +11.5% (24 Mar 2020) | |
| Days up | 54% | |

**Against other US funds (EQAL minus the other fund, in percentage points):**

| vs | 20 days | 60 days | 12 months | 10-year, a year | Correlation |
|---|---|---|---|---|---|
| VOO (S&P 500, cap-weighted) | +3.8 | −0.1 | +4.9 | −4.7 | 0.91 |
| VTI (total market) | +3.7 | +0.3 | +4.9 | −4.2 | 0.93 |
| RSP (S&P 500 equal-weight) | −2.1 | −1.7 | −1.6 | −1.6 | 0.98 |
| VTV (US value) | −2.9 | −4.0 | −8.9 | −2.3 | 0.94 |

Equal weight has won the last year and the last month against the cap-weighted funds, but cost about 4–5 points a year over the decade. It tracks RSP almost exactly; EQAL's slight lag is the extra mid-cap exposure of a Russell 1000 index.

## 3. Markov regime model *(computed, same 20-day ±2% rule as the Markov repo)*

- **Today: Bull, by a hair.** The 20-day return is +2.02%. At the 30 Oct reference the Bull line was 59.16 and the Bear line 56.84. These lines move every day as the 20-day window rolls, so a small dip flips the label to Sideways.
- **Long-run mix:** Bear 21.3%, Sideways 35.7%, Bull 43.1%.
- **Stickiness:** Bull stays Bull the next day 87.8% of the time; Bull goes straight to Bear about 0% of the time (it passes through Sideways first, 12.2%).
- **20 days ahead from Bull:** Bear 18.7%, Sideways 35.8%, Bull 45.5%.

| After a day labelled | Next 20 days: average | Median | Share positive |
|---|---|---|---|
| Bear | +1.92% | +2.64% | 70% |
| Sideways | +0.70% | +1.44% | 69% |
| Bull | +0.62% | +0.89% | 59% |

The model's history shows a mean-reversion pattern: the best forward returns followed Bear spells, the weakest followed Bull. As a timing rule it did **not** beat holding: the Markov strategy's Sharpe was 0.44 against 0.57 for buy-and-hold, though it cut the worst fall from −40% to −27%.

## 4. Economic backdrop

| Item | Latest | Source |
|---|---|---|
| Fed policy rate | Held at **3.75%–4.00%** on 28 Oct 2026, 10–2 vote; both dissenters wanted a 0.25-point **hike**. A hike in September was the first since 2023. Next meeting 9 Dec; one source says markets price a December hike | [InvestingLive](https://investinglive.com/central-banks/fomc-decision-oct-28/), [Admiral Markets](https://admiralmarkets.com/analytics/traders-blog/fomc-october-2026-fed-holds-rates) |
| Inflation (Sept CPI, released 14 Oct) | Headline **3.7%** a year (3.4% in August), +0.6% on the month, over half from gasoline. Core **2.6%** (2.4% in August), above the 2.5% forecast | [InvestingLive](https://investinglive.com/news/us-september-cpi-vs-3-6-expected-0/) |
| Growth (Q3 GDP, advance, 29 Oct) | **+3.4%** annualised, up from +2.2% in Q2. Revisions due 25 Nov and 23 Dec | [Finance Calendar](https://www.financecalendar.com/?p=1313), [GDP release PDF](https://static.poder360.com.br/uploads/2026/10/pib-eua-3-tri-2026-29-out.pdf) |
| Jobs | **Not found.** Only a forecast: unemployment about 4.2% in Q3 ([Philadelphia Fed survey](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/spf-q3-2026)) | |
| Equal-weight vs cap-weight | The S&P 500 traded on 26.3 times earnings at 31 Aug 2026, a 29% premium to its equal-weight version (about 20.4 times, my arithmetic). Several 2026 articles describe equal-weight pulling ahead as breadth widened | [Invesco](https://www.invesco.com/apac/en/institutional/insights/etf/equal-weight-etfs-market-concentration.html), [Seeking Alpha](https://seekingalpha.com/news/4629964-market-breadth-strengthens-equal-weight-sp-500-pulls-ahead-of-market-weight-index) |

**About the fund:** it tracks the Russell 1000 Equal Weight Index, holds roughly 990 stocks, charges 0.20% a year, and rebalances back to equal weights (sources differ on whether quarterly or annually) ([ETF Database](https://etfdb.com/etf/EQAL/), [Trackinsight](https://www.trackinsight.com/en/fund/EQAL)).

## 5. What the economy means for an equal-weight fund *(my reasoning)*

**Supports it**
- Growth of 3.4% helps the cyclical, mid-cap and value-type companies that equal weight holds more of than a cap-weighted fund.
- Cheaper valuation: roughly 20 times earnings against 26 for the cap-weighted index leaves more room if rates do not spike.
- Broadening leadership: the last 12 months show equal weight winning when returns spread beyond a few mega-caps.

**Works against it**
- A restarting hiking cycle with headline inflation at 3.7% raises the chance of higher rates for longer. Equal weight gives about the same weight to rate-sensitive groups (real estate, utilities, financials) as to technology, so it has less of the mega-cap earnings strength that carried cap-weighted indexes through earlier rate rises.
- Rebalancing sells winners and buys laggards. That helps in a rotation and hurts when a few leaders keep running, which is what happened for most of the last decade (−4.7 points a year against VOO).
- Energy-driven inflation (gasoline) is a tax on consumer spending even while headline GDP is strong.

## 6. Scenarios for the next few months

| Scenario | What would happen | Rough signs |
|---|---|---|
| **Broad advance** | Rotation continues, rate worries fade, EQAL retests the 61.57 high | Core CPI stable near 2.6%, Fed holds in December, price holds above the 200-day (57.67) |
| **Range** | Fed hike priced, growth strong: shares chop sideways | Price stays between about 56.8 and 61.6, regime flips between Bull and Sideways |
| **Rate shock / risk-off** | December hike plus higher core inflation: multiples compress | Close below the 200-day, regime goes Bear (20-day return below −2%) |

The data's own odds: about 59–70% of 20-day windows were positive after Bull or Sideways days, and a typical bad month (5th percentile) is about −6.7%.

## 7. Levels and triggers to watch

| Level | Why it matters |
|---|---|
| 61.57 | 52-week and window high (14 Aug 2026) |
| 59.16 | Bull line on the 30 Oct reference (moves daily); price sat on it |
| 59.2 | The 50- and 100-day averages are clustered here (59.18 / 59.25), so this is a crowded area |
| 57.67 | 200-day average |
| 56.84 | Bear line on the 30 Oct reference (moves daily) |
| 48.97 | 52-week low (20 Nov 2025) |

**Dates:** the next jobs report (usually the first Friday of the month), 25 Nov GDP second estimate, **9 Dec FOMC** with new projections.

## 8. Position sizing for a $14,500 holding *(computed)*

- A typical bad day (5th percentile) is −1.66%, about **$241**.
- A typical bad month (5th percentile, 20 trading days) is −6.7%, about **$970**.
- The simulation's 20% fall (the median worst fall inside 10 years is about −34% for a mix with VXUS) would be about **$2,900** on EQAL alone; a repeat of the 2020 fall (−40%) is about **$5,800**.
- Together with $14,000 of VXUS, a stress month can touch both at once; the two funds' correlation is moderate, not low.

## 9. Limits of these notes

- One decade of data, which included no 2008-style crash and was a strong stretch for US stocks.
- The economic figures come from secondary websites, not the BLS, BEA or Fed. **Verify them at [bls.gov](https://www.bls.gov), [bea.gov](https://www.bea.gov) and [federalreserve.gov](https://www.federalreserve.gov) before acting.** No jobs figure was retrieved.
- Prices stop at the 30 Oct close; 2–3 Nov moves are not included.
- The regime model is a description of past price moves, not a forecast, and its timing rule did not beat holding.
- Not personal advice: it does not know your goals, other holdings, taxes or time horizon.
