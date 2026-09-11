# Data dictionary

## Source tables

### Users — one row per user

| Field | Definition |
|---|---|
| `user_id` | Unique synthetic user identifier |
| `signup_date` | User acquisition date |
| `channel` | Organic, paid search, social, or referral acquisition |
| `device` | Mobile, desktop, or tablet |
| `segment` | Individual, team, or student customer segment |
| `variant` | Control or treatment assignment |

### Events — one row per event

| Field | Definition |
|---|---|
| `event_id` | Unique event identifier |
| `user_id` | User foreign key |
| `event_time` | Generated event timestamp within the analysis period |
| `event_name` | Funnel, activity, or support event |
| `revenue` | Simulated event revenue; 29.00 only for subscription starts |

Funnel event order is `landing_view`, `signup_start`, `product_view`, `add_to_cart`, `checkout_start`, and `subscription_start`. `app_open` represents retention activity. `support_contact` is the day-14 customer-experience guardrail.

### Experiment outcomes — one row per user

| Field | Definition |
|---|---|
| `user_id` | User foreign key |
| `variant` | Duplicated assignment for auditable experiment analysis |
| `converted` | One when subscription starts, otherwise zero |
| `active_week_4` | One when an app open occurs during days 28–34 |
| `support_contact_day_14` | One when a support contact occurs before day 14 |

All tables are synthetic. No personal or company data are included.
