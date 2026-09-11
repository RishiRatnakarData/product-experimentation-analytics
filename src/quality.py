"""Auditable data-quality checks for generated product analytics tables."""

from __future__ import annotations

import pandas as pd

from src.generate import ANALYSIS_START

FUNNEL_STEPS = [
    "landing_view",
    "signup_start",
    "product_view",
    "add_to_cart",
    "checkout_start",
    "subscription_start",
]


def build_quality_report(
    users: pd.DataFrame,
    events: pd.DataFrame,
    outcomes: pd.DataFrame,
    days: int,
) -> pd.DataFrame:
    """Return one row per check instead of hiding validation in assertions."""
    analysis_end = ANALYSIS_START + pd.Timedelta(days=days - 1, hours=23, minutes=59)
    rows: list[dict] = []

    def add(check: str, passed: bool, observed: object, severity: str = "critical") -> None:
        rows.append(
            {
                "check_name": check,
                "passed": bool(passed),
                "observed_value": str(observed),
                "severity": severity,
            }
        )

    add("users_nonempty", not users.empty, len(users))
    add("events_nonempty", not events.empty, len(events))
    add("unique_user_ids", users["user_id"].is_unique, users["user_id"].nunique())
    add("unique_event_ids", events["event_id"].is_unique, events["event_id"].nunique())
    add("one_outcome_per_user", outcomes["user_id"].is_unique, outcomes["user_id"].nunique())
    add("outcomes_cover_users", set(outcomes["user_id"]) == set(users["user_id"]), len(outcomes))
    unknown_events = ~events["user_id"].isin(users["user_id"])
    add("events_reference_known_users", not unknown_events.any(), int(unknown_events.sum()))
    add(
        "valid_assignments",
        set(users["variant"].unique()) == {"control", "treatment"},
        sorted(users["variant"].unique()),
    )
    assignment_counts = users.groupby("user_id")["variant"].nunique()
    add("one_assignment_per_user", assignment_counts.eq(1).all(), int(assignment_counts.max()))
    merged_assignments = users[["user_id", "variant"]].merge(
        outcomes, on="user_id", suffixes=("_user", "_outcome")
    )
    assignments_match = merged_assignments["variant_user"].eq(
        merged_assignments["variant_outcome"]
    )
    add("outcome_assignment_matches", assignments_match.all(), int((~assignments_match).sum()))
    binary_columns = ["converted", "active_week_4", "support_contact_day_14"]
    valid_binary = all(set(outcomes[column].unique()) <= {0, 1} for column in binary_columns)
    add("valid_binary_outcomes", valid_binary, binary_columns)
    required_dimensions = users[["channel", "device", "segment", "variant"]]
    add(
        "complete_required_dimensions",
        not required_dimensions.isna().any().any(),
        int(required_dimensions.isna().sum().sum()),
    )
    add(
        "valid_event_timestamps",
        events["event_time"].notna().all(),
        int(events["event_time"].isna().sum()),
    )
    in_period = events["event_time"].between(ANALYSIS_START, analysis_end)
    add("events_within_analysis_period", in_period.all(), int((~in_period).sum()))

    first_times = (
        events[events["event_name"].isin(FUNNEL_STEPS)]
        .pivot_table(index="user_id", columns="event_name", values="event_time", aggfunc="min")
        .reindex(columns=FUNNEL_STEPS)
    )
    ordering_errors = 0
    for left, right in zip(FUNNEL_STEPS, FUNNEL_STEPS[1:]):
        comparable = first_times[left].notna() & first_times[right].notna()
        ordering_errors += int(
            (first_times.loc[comparable, left] > first_times.loc[comparable, right]).sum()
        )
        ordering_errors += int((first_times[right].notna() & first_times[left].isna()).sum())
    add("valid_funnel_order", ordering_errors == 0, ordering_errors)

    converted_users = set(outcomes.loc[outcomes["converted"].eq(1), "user_id"])
    subscription_users = set(
        events.loc[events["event_name"].eq("subscription_start"), "user_id"]
    )
    add(
        "conversion_event_matches_outcome",
        converted_users == subscription_users,
        len(converted_users ^ subscription_users),
    )
    mature = users["signup_date"] + pd.Timedelta(days=35) <= analysis_end
    add("week_four_label_observable", mature.all(), int((~mature).sum()))

    return pd.DataFrame(rows)
