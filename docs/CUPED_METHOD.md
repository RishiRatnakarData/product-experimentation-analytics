# CUPED variance reduction — separate synthetic experiment

## Why CUPED belongs here

The repository **already implements SRM diagnostics** in `experiment_validity.analysis.sample_ratio_check` and reports the chi-square statistic, expected 50:50 assignment, p-value, and a 0.001 warning threshold. This upgrade does not duplicate that analysis.

The existing subscription-outcome table does not document a numeric **pre-treatment** behavior measure. Its week-four activity and post-exposure events are not legitimate pre-experiment CUPED covariates. Instead, a separate seeded fixture simulates a standardized **pre-period engagement score before random assignment**, then generates independent randomized outcomes. This is a methods demonstration, not a retrofit of missing observations onto the original 20,000 users.

## Execute (Python 3.12)

```powershell
python -m pip install -r requirements.txt
python -m scripts.make_cuped_fixture
python -m scripts.run_cuped --data data/generated/cuped_users.csv --out artifacts/cuped_report.json
python -m pytest -q tests_experiment_validity/test_cuped.py
```

`data/generated/` and `artifacts/` are already Git-ignored. The program operates on **one row per randomized user**, never an event-grain joined table. It requires unique, non-null user IDs; both control/treatment arms; complete binary outcomes; and finite, nonconstant values in a covariate with a `pre_` prefix. The prefix guards against accidental misuse, but **cannot prove measurement timing**. Source documentation must independently establish that the variable preceded treatment exposure.

## Estimator and interpretation

For outcome \(Y\) and pre-treatment covariate \(X\), CUPED forms

\[
Y_i^{*} = Y_i - \theta(X_i - \bar X).
\]

The adjustment coefficient is estimated from **pooled within-arm** covariance and variance,

\[
\theta = \frac{\sum_{g\in\{0,1\}} \sum_{i \in g} (X_i-\bar X_g)(Y_i-\bar Y_g)}{\sum_{g\in\{0,1\}} \sum_{i \in g} (X_i-\bar X_g)^2}.
\]

Centering within randomized arms avoids mixing the treatment mean difference into the slope estimate. The treatment effect estimate is adjusted treatment mean minus adjusted control mean. Original and adjusted mean differences, approximate Welch standard errors, two-sided confidence intervals, and p-values are reported. We also report the **measured** reduction in pooled within-arm outcome variance, which is nonnegative by construction when the same data are used to fit the within-arm coefficient and measure the reduction. It is an **in-sample diagnostic**, not evidence of gains on future experiments. CUPED does not guarantee significance.

## Important limitations

- The fixture is **fictional** and independent of the published 20,000-user subscription experiment. No business lift or retention change is attributed to it.
- Welch uncertainty uses a fitted adjustment as a plug-in and does not separately incorporate uncertainty from estimating \(\theta\); large-sample interpretation is more appropriate than precision claims for tiny experiments.
- Linear adjustment of a binary response can produce adjusted individual values outside the interval 0–1. Group mean differences remain a valid adjusted scale for this demonstration; adjusted values are not predicted probabilities.
- An experiment with SRM warnings should be investigated using the **existing** experiment validity audit before interpreting favorable adjusted effects.
- Post-treatment activity, conversion itself, or labels reconstructed from events must **not** be used as the covariate. Do not present the fixture's variance-reduction number as an empirical improvement to the original project's reported conversion results.
