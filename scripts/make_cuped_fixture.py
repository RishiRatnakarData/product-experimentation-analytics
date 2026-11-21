"""Generate fictional users with a truly pre-assignment simulated covariate."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def create_fixture(path: Path, *, users: int = 3000, seed: int = 42) -> pd.DataFrame:
    if users < 100:
        raise ValueError("At least 100 users are required for this demonstration")
    rng = np.random.default_rng(seed)
    # Measured BEFORE the random assignment in this synthetic process.
    pre_engagement = rng.normal(loc=0, scale=1, size=users)
    treatment = rng.integers(0, 2, size=users)
    propensity = 1 / (1 + np.exp(-(-1.3 + 0.95 * pre_engagement + 0.14 * treatment)))
    outcomes = rng.binomial(1, propensity)
    frame = pd.DataFrame({
        "user_id": np.arange(1, users + 1),
        "variant": np.where(treatment == 1, "treatment", "control"),
        "pre_period_engagement_score": pre_engagement,
        "converted": outcomes,
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/generated/cuped_users.csv"))
    parser.add_argument("--users", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = create_fixture(args.out, users=args.users, seed=args.seed)
    print(f"Generated {len(result)} synthetic users at {args.out}")


if __name__ == "__main__":
    main()
