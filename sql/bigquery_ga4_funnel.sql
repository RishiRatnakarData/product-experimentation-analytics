-- Real-data extension: Google public GA4 ecommerce sample, January 2021.
-- This query is separate from the repository's synthetic randomized experiment.
-- Record the authenticated project, bytes processed, result rows, and screenshot.
WITH first_events AS (
  SELECT
    user_pseudo_id,
    MIN(IF(event_name = 'session_start', event_timestamp, NULL)) AS session_ts,
    MIN(IF(event_name = 'view_item', event_timestamp, NULL)) AS view_item_ts,
    MIN(IF(event_name = 'add_to_cart', event_timestamp, NULL)) AS cart_ts,
    MIN(IF(event_name = 'begin_checkout', event_timestamp, NULL)) AS checkout_ts,
    MIN(IF(event_name = 'purchase', event_timestamp, NULL)) AS purchase_ts
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20210101' AND '20210131'
    AND user_pseudo_id IS NOT NULL
  GROUP BY user_pseudo_id
),
user_steps AS (
  SELECT
    user_pseudo_id,
    session_ts IS NOT NULL AS reached_session,
    view_item_ts >= session_ts AS reached_view,
    cart_ts >= view_item_ts AS reached_cart,
    checkout_ts >= cart_ts AS reached_checkout,
    purchase_ts >= checkout_ts AS reached_purchase
  FROM first_events
),
stage_counts AS (
  SELECT 1 AS step_order, 'session_start' AS step, COUNTIF(reached_session) AS users FROM user_steps
  UNION ALL SELECT 2, 'view_item', COUNTIF(reached_view) FROM user_steps
  UNION ALL SELECT 3, 'add_to_cart', COUNTIF(reached_cart) FROM user_steps
  UNION ALL SELECT 4, 'begin_checkout', COUNTIF(reached_checkout) FROM user_steps
  UNION ALL SELECT 5, 'purchase', COUNTIF(reached_purchase) FROM user_steps
),
compared AS (
  SELECT
    *,
    LAG(users) OVER (ORDER BY step_order) AS previous_step_users,
    FIRST_VALUE(users) OVER (ORDER BY step_order) AS starting_users
  FROM stage_counts
)
SELECT
  step_order,
  step,
  users,
  COALESCE(previous_step_users, users) AS previous_step_users,
  SAFE_DIVIDE(users, COALESCE(previous_step_users, users)) AS step_conversion_rate,
  SAFE_DIVIDE(users, starting_users) AS overall_conversion_rate,
  COALESCE(previous_step_users, users) - users AS dropoff_users
FROM compared
ORDER BY step_order;
