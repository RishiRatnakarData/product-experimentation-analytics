# Simulated experiment decision memo

**Decision:** Launch with a monitored rollout in the fictional case study.

**Primary metric:** Subscription conversion per assigned user.

**Population and period:** 20,000 synthetic users generated with seed 42 from January 1 through June 29, 2025. The generator encodes a 2.5-percentage-point individual treatment effect; the realized result is sampled and may differ.

**Integrity:** Control contained 9,918 users and treatment contained 10,082. The SRM test returned p = 0.2462, so assignment mismatch was not flagged at the pre-specified 0.01 level. All 20 data-quality checks passed.

**Primary result:** Control conversion was 18.61% and treatment conversion was 21.37%. The estimated lift was +2.76 percentage points, or +14.84% relative, with a 95% confidence interval from +1.65 to +3.87 points and a two-sided p-value of 0.00000105.

**Sensitivity:** At the realized allocation, achieved power for the observed difference was 99.83%. The approximate minimum detectable effect for 80% power was 1.57 percentage points at alpha 0.05.

**Guardrails:** Week-four activity changed by +0.36 percentage points (p = 0.5692). Day-14 support contacts changed by +0.19 percentage points (p = 0.6066). Neither guardrail showed statistically significant harm. These results do not prove zero guardrail effect.

**Decision reasoning:** The conversion result cleared both the two-sided 5% significance threshold and the pre-specified one-percentage-point practical threshold, assignment integrity passed, and no measured guardrail showed significant harm. A monitored rollout is therefore appropriate within this simulated decision rule.

**Risks and next step:** Synthetic behavior cannot establish external validity. Before a real launch, verify instrumentation, estimate implementation and incentive costs, define longer-term retention and revenue guardrails, and use a staged rollout with a holdout. Segment differences remain exploratory because the analysis does not adjust for multiple comparisons.
