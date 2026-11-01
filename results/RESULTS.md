# Cash-flow Monte Carlo: results

Updated 2026-11-01 00:59 UTC · 10,000 simulated futures · seed 42 · blocks of 20 real days resampled from 2014-12-26 to 2026-10-30 (2,979 trading days)

> **PLACEHOLDER ALLOCATION.** The sleeve weights and glide path in this run are illustrative inputs used to show how the model works. They are not a recommendation. The strategy's allocation is the team's own decision.

## Inputs

| Item | Value |
|---|---|
| Contribution on 1 Jan 2027 | $300,000 |
| Contribution on 1 Jan 2028 | $150,000 |
| Valuation date | 1 Jan 2033 |
| Operating payments | 10 × $50,000 at the start of each year (annuity-due) |
| Flexibility amount held back from the contribution | $0 |

**Sleeves**

| Sleeve | Holdings (weights inside the sleeve) |
|---|---|
| growth | EQAL 50%, VXUS 50% |
| matching | IEF 100% |
| flex | SHY 100% |

**Glide path** (rebalanced to these weights on 1 January of each year)

| Year | Growth | Matching | Flex |
|---|---|---|---|
| 2027 | 60% | 30% | 10% |
| 2028 | 55% | 35% | 10% |
| 2029 | 50% | 40% | 10% |
| 2030 | 45% | 45% | 10% |
| 2031 | 40% | 50% | 10% |
| 2032 | 30% | 55% | 15% |

**What the sampled history looked like** (annualised, before any scenario adjustment)

| Sleeve | Average return | Volatility | Worst fall |
|---|---|---|---|
| growth | 9.7% | 17.0% | -38% |
| matching | 1.3% | 6.5% | -24% |
| flex | 1.6% | 1.5% | -6% |

## Reserve needed on 1 Jan 2033 (closed form, no simulation)

| Reserve earns | Reserve needed for the payments |
|---|---|
| 2% | $458,112 |
| 3% | $439,305 |
| 4% | $421,767 |

For scale: the contributions add up to $450,000 even if they earn nothing.

## Scenario: history

Historical average returns kept.

### Portfolio value

| Percentile | 1 Jan 2031 | 1 Jan 2033 |
|---|---|---|
| 5th | $413,958 | $429,264 |
| 25th | $486,967 | $519,218 |
| 50th (median) | $546,929 | $592,135 |
| 75th | $612,595 | $674,666 |
| 95th | $717,043 | $809,032 |

### Funding reliability and the facility contribution

Contribution = portfolio value − reserve − flexibility amount.

| If the reserve earns | Reserve | Funding ratio: 10th pct / median | Chance value < reserve | Contribution: 10th / median / 90th |
|---|---|---|---|---|
| 2% | $458,112 | 1.00× / 1.29× | 9.62% | $2,182 / $134,023 / $296,217 |
| 3% | $439,305 | 1.05× / 1.35× | 6.35% | $20,988 / $152,829 / $315,024 |
| 4% | $421,767 | 1.09× / 1.40× | 4.28% | $38,527 / $170,368 / $332,562 |

**A range you could state with a confidence level** (the contribution is at least this much, with the stated probability):

| If the reserve earns | 80% confident ≥ | 90% confident ≥ | 95% confident ≥ |
|---|---|---|---|
| 2% | $44,743 | $2,182 | −$28,848 |
| 3% | $63,549 | $20,988 | −$10,041 |
| 4% | $81,088 | $38,527 | $7,498 |

### Sequence risk: a large fall in 2031–2032

| Measure | Value |
|---|---|
| Worst fall inside the window, median | -8% |
| Chance of a fall worse than −20% in the window | 1.2% |
| Chance of a fall worse than −30% in the window | 0.0% |
| (too few paths with such a fall to condition on) | – |

### Regime days of the growth sleeve (20-day return, ±2% rule)

Out of 1,493 labelled days, 5th – median – 95th percentile:

| Bear | Sideways | Bull |
|---|---|---|
| 229 – 323 – 424 | 498 – 584 – 672 | 471 – 584 – 698 |

## Scenario: stress

Historical average returns kept; haircut of growth −3.25 points a year.

### Portfolio value

| Percentile | 1 Jan 2031 | 1 Jan 2033 |
|---|---|---|
| 5th | $390,176 | $394,992 |
| 25th | $457,757 | $476,419 |
| 50th (median) | $513,140 | $542,809 |
| 75th | $574,108 | $616,960 |
| 95th | $669,907 | $738,862 |

### Funding reliability and the facility contribution

Contribution = portfolio value − reserve − flexibility amount.

| If the reserve earns | Reserve | Funding ratio: 10th pct / median | Chance value < reserve | Contribution: 10th / median / 90th |
|---|---|---|---|---|
| 2% | $458,112 | 0.92× / 1.18× | 18.87% | −$34,794 / $84,697 / $230,612 |
| 3% | $439,305 | 0.96× / 1.24× | 13.51% | −$15,988 / $103,504 / $249,418 |
| 4% | $421,767 | 1.00× / 1.29× | 9.77% | $1,551 / $121,042 / $266,957 |

**A range you could state with a confidence level** (the contribution is at least this much, with the stated probability):

| If the reserve earns | 80% confident ≥ | 90% confident ≥ | 95% confident ≥ |
|---|---|---|---|
| 2% | $3,784 | −$34,794 | −$63,120 |
| 3% | $22,590 | −$15,988 | −$44,314 |
| 4% | $40,129 | $1,551 | −$26,775 |

### Sequence risk: a large fall in 2031–2032

| Measure | Value |
|---|---|
| Worst fall inside the window, median | -8% |
| Chance of a fall worse than −20% in the window | 1.7% |
| Chance of a fall worse than −30% in the window | 0.0% |
| (too few paths with such a fall to condition on) | – |

### Regime days of the growth sleeve (20-day return, ±2% rule)

Out of 1,493 labelled days, 5th – median – 95th percentile:

| Bear | Sideways | Bull |
|---|---|---|
| 252 – 349 – 454 | 515 – 601 – 688 | 431 – 540 – 653 |

## Limits

- The sampled history is the only source of randomness. It is limited and includes a long bull market, so the history-based scenario flatters the growth sleeve.
- Block resampling keeps co-movement and short-term clustering but nothing longer than one block.
- The reserve return is a fixed assumption here. In practice it depends on the yields available when the reserve is bought, which is a risk this model does not simulate.
- No taxes, trading costs, or inflation. The payments are fixed in nominal terms.
- Results are ranges under stated assumptions, not predictions.
