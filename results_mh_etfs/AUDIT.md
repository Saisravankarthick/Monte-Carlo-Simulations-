# Audit: Metropolis-Hastings on the Markov model ETFs

Run 2026-11-01 02:54 UTC · [← results](RESULTS.md) · code: [`mcsim/mh_etfs.py`](../mcsim/mh_etfs.py), [`mcsim/metropolis.py`](../mcsim/metropolis.py), audit: [`mcsim/mh_audit.py`](../mcsim/mh_audit.py)

**8 of 10 checks passed.**

| Check | Result | Detail |
|---|---|---|
| 1. Exact kernel and detailed balance | ✅ pass | detailed balance error 1.4e-17; code vs formula: largest gap 0.0015 over 2,000,000 steps; time in each state vs target: distance 0.0009 |
| 2. Markov property | ✅ pass | P(next | current, previous) vs P(next | current): largest gap 0.0066 over 15 pairs; each step receives only the current state; the ETF chains' proposal is fixed before they start |
| 3. Hastings correction | ✅ pass | with the correction: mean 1.998 (exact 2, ±0.004); without it: 0.996, wrong as expected |
| 4. Recovers known parameters | ✅ pass | 41 of 48 90% ranges contain the true value (expected about 43; pass at 38 or more) |
| 5. Same data as the Yahoo-checked bootstrap run | ✅ pass | 19 of 19 funds have the same dates and the same growth a year |
| 6. Chains converged, every fund | ✅ pass | worst R-hat 1.0019 (refit 1.0036); lowest ESS 2,594; acceptance 27–30% |
| 7. Same answer with a different seed | ✅ pass | largest change in median growth 0.03 posterior standard deviations, in median persistence 0.05 (pass below 0.25) |
| 8. Model fits each fund's actual returns | ❌ fail | average return: actual within 0.07 posterior sd of the model's (pass below 1); days in the model's worst 1%: 0.6–1.5% (pass 0.4–2%), worst 5%: 4.5–5.8%, best 5%: 4.4–8.2% (pass 3.5–6.5%) |
| 9. Predictions consistent | ✅ pass | 19 of 19 funds: the 10-year range is wider with parameter uncertainty, and the fixed-parameter median matches amount × exp(days × mean daily log return) within simulation error (largest gap 3.3 standard errors; pass below 4) |
| 10. Calm and stormy spells captured | ❌ fail | day-to-day link in squared returns (lags 1-5): raw data up to 0.58, after the GARCH up to 0.35 (pass below 0.10) |
| 11. Uncertainty about the mean (note) | ⚠ | model's uncertainty about the mean ÷ 20-day block-bootstrap estimate: 0.38–1.25. Below 0.8, so the return range may be too narrow: SGOV (0.38). Its daily returns drift together (they track short-term interest rates), which the model's constant average return does not capture. |

## Per fund

| Fund | R-hat | Effective draws | Acceptance | Seed change: growth / persistence (sd) | Mean return gap (sd) | Days in model's worst 1% / worst 5% / best 5% | Squared-return link: raw → after GARCH | Uncertainty vs block bootstrap |
|---|---|---|---|---|---|---|---|---|
| VOO | 1.0012 | 3,594 | 29% | 0.01 / 0.04 | -0.03 | 1.3% / 5.7% / 5.2% | 0.50 → 0.05 | 1.13 |
| VTI | 1.0013 | 3,795 | 30% | 0.00 / 0.02 | -0.04 | 1.4% / 5.5% / 5.1% | 0.47 → 0.06 | 1.10 |
| QQQM | 1.0007 | 2,795 | 28% | 0.00 / 0.02 | -0.04 | 1.0% / 5.8% / 5.1% | 0.20 → 0.07 | 1.11 |
| RSP | 1.0011 | 3,372 | 29% | 0.02 / 0.01 | -0.04 | 1.1% / 5.5% / 4.9% | 0.53 → 0.05 | 1.05 |
| EQAL | 1.0007 | 3,555 | 28% | 0.03 / 0.03 | -0.01 | 1.1% / 5.2% / 4.9% | 0.48 → 0.06 | 1.02 |
| VTV | 1.0008 | 3,746 | 28% | 0.01 / 0.02 | -0.03 | 0.9% / 5.3% / 4.8% | 0.57 → 0.06 | 1.13 |
| SCHD | 1.0012 | 3,832 | 28% | 0.02 / 0.03 | -0.04 | 1.3% / 5.2% / 5.1% | 0.58 → 0.04 | 1.13 |
| VXUS | 1.0012 | 3,193 | 27% | 0.03 / 0.00 | +0.00 | 1.1% / 4.8% / 4.8% | 0.53 → 0.06 | 1.04 |
| EWT | 1.0010 | 3,154 | 28% | 0.02 / 0.00 | -0.07 | 1.0% / 5.5% / 4.9% | 0.42 → 0.03 | 1.01 |
| XLE | 1.0011 | 3,443 | 30% | 0.01 / 0.02 | -0.06 | 1.0% / 5.1% / 5.3% | 0.31 → 0.07 | 1.07 |
| XLU | 1.0010 | 3,517 | 29% | 0.03 / 0.03 | -0.02 | 0.9% / 4.9% / 5.0% | 0.54 → 0.04 | 1.10 |
| AAAU | 1.0005 | 3,564 | 30% | 0.02 / 0.05 | -0.04 | 1.0% / 5.3% / 5.7% | 0.27 → 0.05 | 1.07 |
| HYG | 1.0019 | 3,656 | 29% | 0.00 / 0.02 | +0.00 | 1.2% / 5.2% / 4.6% | 0.40 → 0.03 | 1.06 |
| TLT | 1.0002 | 3,532 | 28% | 0.01 / 0.02 | -0.00 | 0.8% / 5.1% / 4.8% | 0.45 → 0.04 | 1.04 |
| IEF | 1.0016 | 2,973 | 28% | 0.00 / 0.01 | -0.02 | 1.1% / 4.7% / 4.4% | 0.30 → 0.03 | 1.01 |
| VGIT | 1.0009 | 3,272 | 28% | 0.00 / 0.04 | +0.02 | 1.2% / 4.5% / 4.4% | 0.22 → 0.03 | 1.00 |
| SCHP | 1.0006 | 3,514 | 30% | 0.02 / 0.00 | -0.00 | 1.0% / 4.5% / 4.8% | 0.36 → 0.06 | 1.25 |
| SHY | 1.0006 | 3,546 | 28% | 0.02 / 0.01 | -0.00 | 1.5% / 5.6% / 5.1% | 0.32 → 0.05 | 0.99 |
| SGOV | 1.0011 | 2,594 | 28% | 0.01 / 0.01 | -0.01 | 0.6% / 4.6% / 8.2% | 0.35 → 0.35 | 0.38 |

![Traces](charts/audit_traces.png)

## Recovery test (made-up data with known answers)

Each row: 10 years of daily returns simulated from the GARCH model with known parameters, then fitted from scratch.

| Set | Growth: true | Growth: fitted | Tails ν: true / fitted | Skew γ: true / fitted | Persistence: true / fitted | Inside the 90% range |
|---|---|---|---|---|---|---|
| 1 | 13.4% | 21.9% | 6.0 / 6.7 | 0.92 / 0.93 | 0.970 / 0.941 | 3 of 4 |
| 2 | 7.9% | 6.0% | 8.0 / 8.0 | 0.95 / 0.94 | 0.950 / 0.926 | 4 of 4 |
| 3 | 16.3% | 17.3% | 5.0 / 5.0 | 0.90 / 0.92 | 0.980 / 0.961 | 3 of 4 |
| 4 | 2.6% | 0.3% | 10.0 / 10.5 | 1.00 / 0.97 | 0.900 / 0.934 | 4 of 4 |
| 5 | 10.6% | 16.2% | 4.5 / 4.7 | 0.88 / 0.93 | 0.960 / 0.955 | 3 of 4 |
| 6 | 5.2% | 4.0% | 7.0 / 6.3 | 1.05 / 1.04 | 0.930 / 0.941 | 4 of 4 |
| 7 | 13.4% | 15.3% | 6.0 / 6.8 | 0.92 / 0.94 | 0.970 / 0.971 | 4 of 4 |
| 8 | 7.9% | 4.2% | 8.0 / 7.6 | 0.95 / 0.91 | 0.950 / 0.946 | 3 of 4 |
| 9 | 16.3% | 39.8% | 5.0 / 5.1 | 0.90 / 0.96 | 0.980 / 0.993 | 1 of 4 |
| 10 | 2.6% | 4.5% | 10.0 / 11.1 | 1.00 / 1.01 | 0.900 / 0.881 | 4 of 4 |
| 11 | 10.6% | 19.5% | 4.5 / 4.5 | 0.88 / 0.85 | 0.960 / 0.949 | 4 of 4 |
| 12 | 5.2% | 4.6% | 7.0 / 6.3 | 1.05 / 1.05 | 0.930 / 0.946 | 4 of 4 |

## What the checks mean

1-3 test the Metropolis-Hastings code itself against exact answers, including a negative control that must fail. 4 tests the whole fitting method: if the 90% ranges caught the truth much less than 90% of the time, the ranges in the report would be overconfident. 5 ties the data to the Yahoo-checked bootstrap run. 6-7 show the chains settled and that the answer does not depend on the random seed. 8 checks the fit: bad days happen as often as the model says (about 1% of days fall in its worst 1%), so its crash risk is neither understated nor overstated. 9 checks the prediction step. 10 checks that the GARCH removes the calm-and-stormy pattern from the shocks it leaves over. 11 is a note comparing the model's uncertainty about the average return with a method that keeps 20-day runs of real days together.
