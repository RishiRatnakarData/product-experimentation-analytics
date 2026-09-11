"""Seeded behavioral-data generator for a fictional subscription product."""

from __future__ import annotations

import numpy as np
import pandas as pd

ANALYSIS_START = pd.Timestamp("2025-01-01")
EXPERIMENT_EFFECT = 0.025


def _append_event(
    events: list[dict],
    event_id: int,
    user_id: int,
    event_time: pd.Timestamp,
    event_name: str,
    revenue: float = 0.0,
) -> int:
    events.append(
        {
            "event_id": event_id,
            "user_id": user_id,
            "event_time": event_time,
            "event_name": event_name,
            "revenue": revenue,
        }
    )
    return event_id + 1


def generate_users_and_events(
    n_users: int,
    days: int,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return users, event-grain behavior, and one experiment outcome per user.

    Treatment adds exactly 2.5 percentage points to conversion probability.
    Observed lift can differ because outcomes are sampled. Week-four retention is
    generated separately from treatment so it can serve as a guardrail.
    """
    if n_users < 20:
        raise ValueError("n_users must be at least 20")
    if days < 42:
        raise ValueError("days must be at least 42 to observe week-four retention")

    rng = np.random.default_rng(seed)
    analysis_end = ANALYSIS_START + pd.Timedelta(days=days - 1)
    user_ids = np.arange(1, n_users + 1)
    signup_offset = rng.integers(0, days - 35, n_users)
    users = pd.DataFrame(
        {
            "user_id": user_ids,
            "signup_date": ANALYSIS_START + pd.to_timedelta(signup_offset, unit="D"),
            "channel": rng.choice(
                ["organic", "paid_search", "social", "referral"],
                n_users,
                p=[0.38, 0.27, 0.20, 0.15],
            ),
            "device": rng.choice(
                ["mobile", "desktop", "tablet"],
                n_users,
                p=[0.60, 0.33, 0.07],
            ),
            "segment": rng.choice(
                ["individual", "team", "student"],
                n_users,
                p=[0.58, 0.24, 0.18],
            ),
        }
    )
    users["variant"] = np.where(rng.random(n_users) < 0.5, "control", "treatment")

    events: list[dict] = []
    outcomes: list[dict] = []
    event_id = 1
    for row in users.itertuples(index=False):
        latent_engagement = rng.normal()
        base_conversion = (
            0.165
            + (0.040 if row.channel == "referral" else 0.0)
            + (0.022 if row.device == "desktop" else 0.0)
            + (0.030 if row.segment == "team" else 0.0)
        )
        treatment_effect = EXPERIMENT_EFFECT if row.variant == "treatment" else 0.0
        conversion_probability = float(np.clip(base_conversion + treatment_effect, 0.01, 0.95))
        converted = rng.random() < conversion_probability

        landing_time = row.signup_date + pd.Timedelta(minutes=int(rng.integers(0, 30)))
        event_id = _append_event(events, event_id, row.user_id, landing_time, "landing_view")

        signup_started = rng.random() < np.clip(0.72 + 0.05 * latent_engagement, 0.35, 0.95)
        product_viewed = signup_started and rng.random() < 0.86
        added_to_cart = product_viewed and rng.random() < 0.62
        checkout_started = added_to_cart and (converted or rng.random() < 0.55)
        cursor = landing_time
        reached_steps: set[str] = set()
        for reached, event_name in [
            (signup_started, "signup_start"),
            (product_viewed, "product_view"),
            (added_to_cart, "add_to_cart"),
            (checkout_started, "checkout_start"),
        ]:
            if reached:
                cursor += pd.Timedelta(minutes=int(rng.integers(2, 35)))
                event_id = _append_event(events, event_id, row.user_id, cursor, event_name)
                reached_steps.add(event_name)

        if converted:
            for prerequisite in ["signup_start", "product_view", "add_to_cart", "checkout_start"]:
                if prerequisite not in reached_steps:
                    cursor += pd.Timedelta(minutes=int(rng.integers(2, 20)))
                    event_id = _append_event(events, event_id, row.user_id, cursor, prerequisite)
            cursor += pd.Timedelta(minutes=int(rng.integers(2, 20)))
            event_id = _append_event(
                events,
                event_id,
                row.user_id,
                cursor,
                "subscription_start",
                29.0,
            )

        early_app_opens = max(0, int(round(1.5 + 0.9 * latent_engagement + rng.normal())))
        for _ in range(early_app_opens):
            event_time = row.signup_date + pd.Timedelta(
                days=int(rng.integers(1, 14)),
                minutes=int(rng.integers(0, 1_440)),
            )
            event_id = _append_event(events, event_id, row.user_id, event_time, "app_open")

        retention_logit = -1.35 + 1.25 * int(converted) + 0.38 * latent_engagement
        week_4_probability = 1 / (1 + np.exp(-retention_logit))
        active_week_4 = rng.random() < week_4_probability
        for week in range(2, 9):
            if week == 4:
                active = active_week_4
            else:
                decay = 0.82 ** max(week - 2, 0)
                active_probability = np.clip((0.52 if converted else 0.25) * decay, 0.03, 0.90)
                active = rng.random() < active_probability
            event_time = row.signup_date + pd.Timedelta(
                days=week * 7 + int(rng.integers(0, 7)),
                minutes=int(rng.integers(0, 1_440)),
            )
            if active and event_time <= analysis_end:
                event_id = _append_event(events, event_id, row.user_id, event_time, "app_open")

        support_probability = 0.065 + (0.012 if row.device == "mobile" else 0.0)
        support_contact_day_14 = int(rng.random() < support_probability)
        if support_contact_day_14:
            event_time = row.signup_date + pd.Timedelta(
                days=int(rng.integers(0, 14)),
                minutes=int(rng.integers(0, 1_440)),
            )
            event_id = _append_event(events, event_id, row.user_id, event_time, "support_contact")

        outcomes.append(
            {
                "user_id": row.user_id,
                "variant": row.variant,
                "converted": int(converted),
                "active_week_4": int(active_week_4),
                "support_contact_day_14": support_contact_day_14,
            }
        )

    event_frame = pd.DataFrame(events).sort_values(["event_time", "event_id"]).reset_index(drop=True)
    return users, event_frame, pd.DataFrame(outcomes)
