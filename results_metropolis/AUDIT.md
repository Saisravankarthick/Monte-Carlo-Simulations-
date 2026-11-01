# Audit: Metropolis-Hastings

Run 2026-11-01 01:55 UTC · code: [`mcsim/metropolis.py`](../mcsim/metropolis.py) · audit: [`mcsim/metropolis_audit.py`](../mcsim/metropolis_audit.py) · [← results](RESULTS.md)

**6 of 6 checks passed.**

| Check | Result | Detail |
|---|---|---|
| 1. Exact kernel and detailed balance | ✅ pass | detailed balance error 1.4e-17, stationarity error 5.6e-17; code's transition probabilities vs formula: largest gap 0.0015 over 2,000,000 steps; time in each state vs target: distance 0.0009 |
| 2. Markov property | ✅ pass | P(next | current, previous) vs P(next | current): largest gap 0.0066 across 15 (previous, current) pairs; mh_step takes only the current state (x, e_x) |
| 3. Hastings correction | ✅ pass | with the correction: mean 1.998 (exact 2, ±0.004), variance 1.987 (exact 2); negative control without it: mean 0.996, wrong as expected |
| 4. Banana at T = 1 matches the exact answer | ✅ pass | all four within 4 standard errors (ESS of x 2,039, of y 1,267) |
| 5. Chains agree (convergence) | ✅ pass | R-hat x 1.000, y 1.001; acceptance 17%, 17%, 17%, 17% (healthy range 10-60%) |
| 6-7. Annealing reaches [1, 1, 0], reproducibly | ✅ pass | distance to [1, 1]: 0.0006, 0.0008, 0.0014; height z: 3.9e-07, 1.6e-07, 4.3e-07; same seed reproduces the run exactly: yes |

## Banana at T = 1: estimates vs exact values

Exact: x ~ Normal(1, 0.5) and y | x ~ Normal(x², 1/200), so mean x = 1, var x = 0.5, mean y = 1.5, var y = 2.505. The standard error uses batch means, which allows for the chains' autocorrelation.

| Quantity | Estimate | Exact | Standard error | Gap in standard errors | Result |
|---|---|---|---|---|---|
| mean of x | 0.9970 | 1.0000 | ±0.0158 | -0.2 | ✅ |
| mean of y | 1.5033 | 1.5000 | ±0.0456 | +0.1 | ✅ |
| var of x | 0.5095 | 0.5000 | ±0.0164 | +0.6 | ✅ |
| var of y | 2.6290 | 2.5050 | ±0.2210 | +0.6 | ✅ |

## What each check means

1. **Exact kernel.** A 5-state target (1:2:3:4:5) with a proposal that steps up 70% of the time. The code's observed transition probabilities match the Metropolis-Hastings formula, and that kernel satisfies detailed balance (π_i P_ij = π_j P_ji), the condition that makes the target the chain's long-run distribution.
2. **Markov property.** Knowing the previous state as well as the current one does not change the odds of the next state, and the step function receives only the current state.
3. **Hastings correction.** The q(x | y) / q(y | x) term matters when proposals are lopsided. With it, draws match Gamma(2, 1); without it (negative control) they do not, which shows the check can fail.
4. **Known answer.** The banana distribution's moments are known exactly and the draws reproduce them.
5. **Convergence.** Chains started far apart end up describing the same distribution (R-hat near 1).
6-7. **Optimisation and reproducibility.** Lowering the temperature on a fixed schedule takes all three chains to [1, 1, 0], and the same seed gives the same result.
