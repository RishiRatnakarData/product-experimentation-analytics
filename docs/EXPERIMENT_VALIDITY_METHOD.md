# Experiment validity and decision rules

## Statistical unit and estimand

The primary analysis is an **assigned-user, intention-to-treat** conversion-rate difference: treatment minus control. Input must contain one unique `user_id` per assigned user with binary `converted` status and a single `variant` in {control, treatment}. Events must *not* be treated as independent observations, and duplicated or missing outcomes cause explicit failure. This audit does not reconstruct users from event rows.

## Checks and estimates

1. **SRM:** Chi-square test against the planned treatment fraction (default 0.5); flag at p < 0.001. An SRM failure takes precedence over positive lift.
2. **Primary lift:** Difference in sample proportions, two-sided pooled z-test (alpha 0.05), and **approximate** unpooled normal 95% CI; appropriate as a transparent large-sample baseline, not an exact interval for rare events or small cells.
3. **Guardrails:** Optional binary outcomes with explicitly specified desirable direction (`increase` or `decrease`). A guardrail is flagged as *significant harm* only if its approximate 95% interval lies entirely in the adverse direction. A nonsignificant result **does not establish noninferiority or safety**, especially with multiple metrics.
4. **Planning:** Solve the independent-user equal-arm two-sided normal-approximation sample-size equation for 80% prospective power at a positive MDE. For realized sample sizes, report an approximate MDE at the smaller of the two arms. We **do not use achieved power calculated from the observed lift** as evidence.
5. **Decision language:** `candidate_for_monitored_review` requires positive significant lift exceeding user-supplied practical threshold, no flagged SRM and no detected directional guardrail harm. It is **never** an automated launch approval. Experiment costs, instrumentation, funnel usability, generalizability, policy on interim looks, multiplicity and unobserved harms need external review. The input is synthetic.

## Result integrity

- All outputs are computed from the provided outcome file; no published lift or p-value is inserted into generated evidence.
- The study is synthetic and this extension cannot validate the real-world business impact of a randomized treatment.
- The original repo's simulated 20,000-user and 129,937-event claims must be reconciled by actually running against the current local `data/generated/` artifacts before publication.
- The original power analysis and retention model are **unchanged**; their CI and practical implications should not be replaced by these new reports without reconciliation.
- The separate GA4 BigQuery dataset is not merged into the treatment experiment.
- The generated chart and JSON are ignored if saved under the repository's `artifacts/` ignore rule; deliberate publication of sanitized aggregate evidence may follow a source/metric review.

## Exploratory segments

The consolidated showcase also estimates conversion effects for supported channel and device segments when each arm contains at least 30 simulated users. The test statistics are exploratory: Holm-adjusted p-values are included across reported segment comparisons. Unadjusted intervals are shown for descriptive context, not subgroup discovery claims.
