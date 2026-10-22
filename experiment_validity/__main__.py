"""Run a user-level experiment audit from a generated outcome table."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .analysis import analyze
from .report import save_effect_plot, write_outputs


def main() -> None:
    parser=argparse.ArgumentParser(description="Audit a seeded experiment using one row per randomized user")
    parser.add_argument("--data",required=True,help="User-grain CSV or Parquet outcome table")
    parser.add_argument("--out",default="artifacts/experiment_validity")
    parser.add_argument("--outcome-col",default="converted")
    parser.add_argument("--user-col",default="user_id")
    parser.add_argument("--arm-col",default="variant")
    parser.add_argument("--expected-treatment-fraction",type=float,default=.5)
    parser.add_argument("--practical-lift",type=float,default=.01,help="Absolute fraction; 0.01 = one percentage point")
    parser.add_argument("--guardrail",action="append",default=[],help="Column:increase or Column:decrease, repeated")
    args=parser.parse_args()
    data=Path(args.data)
    if not data.is_file():
        parser.error(f"Cannot find {data}; first run the existing product analytics pipeline")
    try:
        frame=pd.read_parquet(data) if data.suffix.lower()==".parquet" else pd.read_csv(data) if data.suffix.lower()==".csv" else None
        if frame is None:
            parser.error("Only .csv or .parquet input supported")
        guardrails=[]
        for expression in args.guardrail:
            parts=expression.split(":")
            if len(parts)!=2 or parts[1] not in ("increase","decrease"):
                parser.error("--guardrail requires Column:increase or Column:decrease")
            guardrails.append((parts[0],parts[1]))
        report=analyze(frame,guardrails=tuple(guardrails),outcome_col=args.outcome_col,user_col=args.user_col,arm_col=args.arm_col,expected_treatment_fraction=args.expected_treatment_fraction,practical_lift=args.practical_lift)
    except (ValueError,KeyError,ImportError) as exc:
        parser.error(str(exc))
    paths=write_outputs(report,args.out)
    paths.append(save_effect_plot(report,Path(args.out)/"experiment_effects.png"))
    print(f"Primary lift: {report['primary']['absolute_lift']*100:+.2f} pp")
    print(f"Assignment SRM p-value: {report['srm']['p_value']:.5g}")
    print(f"Decision evidence: {report['decision']}")
    print("Created:")
    for path in paths:
        print(f"  {path}")


if __name__=="__main__":
    main()
