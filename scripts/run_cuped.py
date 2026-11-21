"""Evaluate CUPED on a user-level experiment CSV or Parquet, without event joins."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from experiment_validity.cuped import analyze_cuped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("artifacts/cuped_report.json"))
    parser.add_argument("--pre-covariate", default="pre_period_engagement_score")
    parser.add_argument("--outcome", default="converted")
    args = parser.parse_args()
    if not args.data.is_file():
        parser.error(f"Missing data file: {args.data}")
    try:
        if args.data.suffix.lower() == ".csv":
            df = pd.read_csv(args.data)
        elif args.data.suffix.lower() == ".parquet":
            df = pd.read_parquet(args.data)
        else:
            parser.error("Expected .csv or .parquet")
        result = analyze_cuped(df, covariate=args.pre_covariate, outcome=args.outcome)
    except ValueError as error:
        parser.error(str(error))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    before, after = result["original"], result["cuped_adjusted"]
    print(f"Original effect: {100 * before['effect']:+.3f} percentage points; SE={100 * before['standard_error']:.3f} pp")
    print(f"CUPED effect:    {100 * after['effect']:+.3f} percentage points; SE={100 * after['standard_error']:.3f} pp")
    reduced = result["measured_variance_reduction_fraction"]
    print(f"Measured variance reduction: {100 * reduced:.2f}%" if reduced is not None else "Variance reduction unavailable")
    print(f"Report: {args.out}")


if __name__ == "__main__":
    main()
