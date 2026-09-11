# Power BI report

The completed four-page report uses CSV and JSON artifacts from the reproducible 20,000-user run. A visible banner on every page identifies the experiment as synthetic and prevents the results from being represented as real company evidence.

## Data import

Import these files from `artifacts/`:

- `funnel.csv`
- `funnel_by_segment.csv`
- `cohort_retention.csv`
- `experiment_results.csv`
- `retention_predictions.csv`
- `quality_report.csv`
- `channel_performance.csv`

Set rates and probabilities to Decimal Number, counts to Whole Number, dates to Date, and `passed`/`srm_flag` to True/False. Do not create relationships between aggregate tables; each is already at its documented reporting grain.

## Core measures

Create the following measures in their named tables:

```DAX
Control Conversion =
CALCULATE(
    MAX(experiment_results[control_rate]),
    experiment_results[metric] = "converted"
)

Treatment Conversion =
CALCULATE(
    MAX(experiment_results[treatment_rate]),
    experiment_results[metric] = "converted"
)

Absolute Lift =
CALCULATE(
    MAX(experiment_results[absolute_lift]),
    experiment_results[metric] = "converted"
)

Relative Lift =
CALCULATE(
    MAX(experiment_results[relative_lift]),
    experiment_results[metric] = "converted"
)

Experiment P Value =
CALCULATE(
    MAX(experiment_results[p_value]),
    experiment_results[metric] = "converted"
)

Quality Pass Rate =
DIVIDE(
    CALCULATE(COUNTROWS(quality_report), quality_report[passed] = TRUE()),
    COUNTROWS(quality_report)
)

Model Precision =
DIVIDE(
    CALCULATE(COUNTROWS(retention_predictions), retention_predictions[predicted_class] = 1, retention_predictions[actual_active_week_4] = 1),
    CALCULATE(COUNTROWS(retention_predictions), retention_predictions[predicted_class] = 1)
)

Model Recall =
DIVIDE(
    CALCULATE(COUNTROWS(retention_predictions), retention_predictions[predicted_class] = 1, retention_predictions[actual_active_week_4] = 1),
    CALCULATE(COUNTROWS(retention_predictions), retention_predictions[actual_active_week_4] = 1)
)
```

## Page 1 — Executive experiment overview

- Cards: control conversion, treatment conversion, absolute lift, relative lift, p-value, and SRM status.
- Clustered columns: control and treatment rates for all three metrics.
- Error-bar chart: primary lift with the 95% confidence interval.
- Decision text: monitored rollout, qualified as a simulated case-study recommendation.

Validation: cards must show 18.61%, 21.37%, +2.76 points, +14.84%, p = 0.00000105, and no SRM flag.

## Page 2 — Funnel and conversion

- Funnel or horizontal bars: users by `step`, sorted by `step_order`.
- Cards: eligible users, final conversions, and overall conversion.
- Matrix: channel and segment with eligible users, converted users, and conversion rate.
- Bar chart: `dropoff_users` and `dropoff_rate` by step.

Validation: the landing stage must contain 20,000 users, subscription start must contain 4,001 users, and final conversion must be 20.01%. Checkout-to-subscription drop-off must be 3,458 users or 46.36%.

## Page 3 — Cohort and retention

- Matrix: `signup_week` on rows, `week_number` on columns, and `retention_rate` as values.
- Line chart: weighted retention by activity week.
- Table: cohort-week eligible users and retained users.
- Channel/segment bars: week-four retention from `channel_performance`.

Do not fill missing cohort weeks with zero. Missing rows mean the full observation window was unavailable.

## Page 4 — Model and data quality

- Cards: model precision, recall, test users, and quality pass rate.
- Histogram: predicted probability by actual week-four outcome.
- Confusion-matrix visual from actual and predicted class.
- Quality table: check, pass/fail, observed value, and severity.

Validation: the quality pass rate must be 100% across 20 checks. Validate model totals and threshold metrics against `retention_model_metrics.json` before publishing a screenshot.

## Visual standard

Use one restrained accent color for treatment, gray for control, green only for passed checks, and red only for adverse or failed states. Use a 16:9 canvas, consistent card sizes, concise titles, thousand separators, percentage formats, and a footer containing seed 42 and the generated date range. Avoid decorative gauges and three-dimensional charts.
