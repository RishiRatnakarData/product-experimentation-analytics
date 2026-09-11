-- Every funnel flag is one row per user. Event counts never act as user counts.
CREATE OR REPLACE VIEW user_funnel AS
WITH first_steps AS (
    SELECT
        user_id,
        MIN(event_time) FILTER (WHERE event_name = 'landing_view') AS landing_time,
        MIN(event_time) FILTER (WHERE event_name = 'signup_start') AS signup_time,
        MIN(event_time) FILTER (WHERE event_name = 'product_view') AS product_time,
        MIN(event_time) FILTER (WHERE event_name = 'add_to_cart') AS cart_time,
        MIN(event_time) FILTER (WHERE event_name = 'checkout_start') AS checkout_time,
        MIN(event_time) FILTER (WHERE event_name = 'subscription_start') AS conversion_time
    FROM events
    GROUP BY user_id
)
SELECT
    u.user_id,
    u.channel,
    u.device,
    u.segment,
    u.variant,
    (landing_time IS NOT NULL)::INT AS reached_landing,
    (signup_time >= landing_time)::INT AS reached_signup,
    (product_time >= signup_time)::INT AS reached_product,
    (cart_time >= product_time)::INT AS reached_cart,
    (checkout_time >= cart_time)::INT AS reached_checkout,
    (conversion_time >= checkout_time)::INT AS reached_subscription
FROM users AS u
LEFT JOIN first_steps USING (user_id);

CREATE OR REPLACE VIEW funnel AS
WITH stage_counts AS (
    SELECT 1 AS step_order, 'landing_view' AS step, SUM(reached_landing)::BIGINT AS users FROM user_funnel
    UNION ALL SELECT 2, 'signup_start', SUM(reached_signup)::BIGINT FROM user_funnel
    UNION ALL SELECT 3, 'product_view', SUM(reached_product)::BIGINT FROM user_funnel
    UNION ALL SELECT 4, 'add_to_cart', SUM(reached_cart)::BIGINT FROM user_funnel
    UNION ALL SELECT 5, 'checkout_start', SUM(reached_checkout)::BIGINT FROM user_funnel
    UNION ALL SELECT 6, 'subscription_start', SUM(reached_subscription)::BIGINT FROM user_funnel
),
with_comparisons AS (
    SELECT
        *,
        LAG(users) OVER (ORDER BY step_order) AS previous_step_users,
        FIRST_VALUE(users) OVER (ORDER BY step_order) AS landing_users
    FROM stage_counts
)
SELECT
    step_order,
    step,
    users,
    COALESCE(previous_step_users, users) AS previous_step_users,
    users * 1.0 / NULLIF(COALESCE(previous_step_users, users), 0) AS step_conversion_rate,
    users * 1.0 / NULLIF(landing_users, 0) AS overall_conversion_rate,
    COALESCE(previous_step_users, users) - users AS dropoff_users,
    (COALESCE(previous_step_users, users) - users) * 1.0
        / NULLIF(COALESCE(previous_step_users, users), 0) AS dropoff_rate
FROM with_comparisons
ORDER BY step_order;

CREATE OR REPLACE VIEW funnel_by_segment AS
SELECT
    channel,
    segment,
    variant,
    COUNT(*) AS eligible_users,
    SUM(reached_product)::BIGINT AS product_view_users,
    SUM(reached_cart)::BIGINT AS add_to_cart_users,
    SUM(reached_checkout)::BIGINT AS checkout_users,
    SUM(reached_subscription)::BIGINT AS converted_users,
    AVG(reached_subscription) AS conversion_rate
FROM user_funnel
GROUP BY channel, segment, variant
ORDER BY eligible_users DESC;

-- A cohort/week row is emitted only when that entire week is observable.
CREATE OR REPLACE VIEW cohort_retention AS
WITH cohort_users AS (
    SELECT
        user_id,
        DATE_TRUNC('week', signup_date)::DATE AS signup_week,
        signup_date
    FROM users
),
activity AS (
    SELECT DISTINCT
        u.user_id,
        FLOOR(DATE_DIFF('day', u.signup_date, e.event_time) / 7)::INT AS activity_week
    FROM users AS u
    JOIN events AS e USING (user_id)
    WHERE e.event_name IN ('landing_view', 'app_open')
),
eligible AS (
    SELECT
        c.user_id,
        c.signup_week,
        w.week_number
    FROM cohort_users AS c
    CROSS JOIN GENERATE_SERIES(0, 8) AS w(week_number)
    CROSS JOIN run_config AS r
    WHERE c.signup_date + w.week_number * INTERVAL 7 DAY <= r.analysis_end
)
SELECT
    e.signup_week,
    e.week_number,
    COUNT(DISTINCT e.user_id) AS eligible_users,
    COUNT(DISTINCT a.user_id) AS retained_users,
    COUNT(DISTINCT a.user_id) * 1.0 / NULLIF(COUNT(DISTINCT e.user_id), 0) AS retention_rate
FROM eligible AS e
LEFT JOIN activity AS a
    ON e.user_id = a.user_id
    AND e.week_number = a.activity_week
GROUP BY e.signup_week, e.week_number
ORDER BY e.signup_week, e.week_number;

CREATE OR REPLACE VIEW channel_performance AS
SELECT
    u.channel,
    u.device,
    u.segment,
    COUNT(*) AS users,
    AVG(o.converted) AS conversion_rate,
    AVG(o.active_week_4) AS week_4_retention,
    AVG(o.support_contact_day_14) AS day_14_support_contact_rate
FROM users AS u
JOIN experiment_outcomes AS o USING (user_id)
GROUP BY u.channel, u.device, u.segment
ORDER BY users DESC;

CREATE OR REPLACE VIEW experiment_summary_sql AS
SELECT
    variant,
    COUNT(*) AS users,
    SUM(converted) AS conversions,
    AVG(converted) AS conversion_rate,
    AVG(active_week_4) AS week_4_retention,
    AVG(support_contact_day_14) AS day_14_support_contact_rate
FROM experiment_outcomes
GROUP BY variant
ORDER BY variant;
