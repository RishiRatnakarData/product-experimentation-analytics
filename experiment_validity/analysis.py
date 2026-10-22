"""User-grain validation and descriptive inference for a simulated randomized experiment.

This module does not infer that a simulation has a real-world causal effect.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

import pandas as pd
from scipy.stats import chi2, norm


@dataclass(frozen=True)
class BinaryEffect:
    column: str
    label: str
    control_n: int
    treatment_n: int
    control_successes: int
    treatment_successes: int
    control_rate: float
    treatment_rate: float
    absolute_lift: float
    relative_lift: float | None
    ci_low: float
    ci_high: float
    p_value: float
    direction: str
    significant_harm: bool | None


def _check_binary(values: pd.Series, name: str) -> pd.Series:
    if values.isna().any():
        raise ValueError(f"{name}: missing binary outcomes; do not silently exclude users")
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.isna().any() or not bool(numeric.isin([0, 1]).all()):
        raise ValueError(f"{name}: expected 0/1 binary outcomes for every assigned user")
    return numeric.astype("int64")


def validate_user_grain(frame: pd.DataFrame, *, user_col: str = "user_id", arm_col: str = "variant", outcome_col: str = "converted", extra_columns: tuple[str, ...] = ()) -> pd.DataFrame:
    """Validate a one-row-per-randomized-user intention-to-treat table.

    Never quietly deduplicate or collapse event-level observations: doing so can
    conceal instrumentation and assignment errors.
    """
    required = {user_col, arm_col, outcome_col, *extra_columns}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if not len(frame):
        raise ValueError("No assigned users supplied")
    if frame[user_col].isna().any():
        raise ValueError("Missing user identifiers")
    if frame[user_col].duplicated().any():
        raise ValueError("Duplicate user identifiers: requires one row per assigned user, NOT event rows")
    if frame[arm_col].isna().any() or set(frame[arm_col].unique()) != {"control", "treatment"}:
        raise ValueError("Exactly two arms required: control and treatment")
    copy = frame.copy()
    for name in (outcome_col, *extra_columns):
        copy[name] = _check_binary(copy[name], name)
    return copy


def binary_effect(frame: pd.DataFrame, column: str, *, label: str | None = None, direction: Literal["increase", "decrease", "primary"] = "primary", alpha: float = .05, arm_col: str = "variant") -> BinaryEffect:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    ctrl = frame.loc[frame[arm_col] == "control", column].to_numpy(dtype=float)
    trt = frame.loc[frame[arm_col] == "treatment", column].to_numpy(dtype=float)
    n0, n1 = len(ctrl), len(trt)
    if not n0 or not n1:
        raise ValueError("Both assignment groups must be nonempty")
    k0, k1 = int(ctrl.sum()), int(trt.sum())
    p0, p1 = k0/n0, k1/n1
    lift = p1 - p0
    se = math.sqrt(p0*(1-p0)/n0 + p1*(1-p1)/n1)
    critical = float(norm.ppf(1-alpha/2))
    # Unpooled Wald CI is a simple transparent approximate interval; report as such.
    lo, hi = max(-1., lift-critical*se), min(1., lift+critical*se)
    pooled = (k0+k1)/(n0+n1)
    se_null = math.sqrt(pooled*(1-pooled)*(1/n0+1/n1))
    pval = float(2*norm.sf(abs(lift/se_null))) if se_null else (1.0 if lift == 0 else 0.0)
    harm = None
    if direction == "increase":
        harm = bool(hi < 0)  # a lower value is harmful to an increase-desired outcome
    elif direction == "decrease":
        harm = bool(lo > 0)  # a higher value is harmful to a decrease-desired outcome
    return BinaryEffect(column, label or column, n0, n1, k0, k1, p0, p1, lift, lift/p0 if p0 else None, lo, hi, pval, direction, harm)


def sample_ratio_check(frame: pd.DataFrame, *, expected_treatment_fraction: float = 0.5, arm_col: str = "variant", threshold: float = .001) -> dict:
    if not 0 < expected_treatment_fraction < 1:
        raise ValueError("expected_treatment_fraction must be in (0,1)")
    if not 0 < threshold < 1:
        raise ValueError("srm threshold must be in (0,1)")
    c = frame[arm_col].value_counts()
    counts = [int(c["control"]), int(c["treatment"])]
    total = sum(counts)
    expected = [total*(1-expected_treatment_fraction), total*expected_treatment_fraction]
    stat = sum((o-e)**2/e for o,e in zip(counts,expected))
    p = float(chi2.sf(stat,1))
    return {"observed_control": counts[0],"observed_treatment": counts[1],"expected_treatment_fraction": expected_treatment_fraction,"chi_square":stat,"p_value":p,"threshold":threshold,"flagged":p<threshold}


def required_users_per_arm(p0: float, mde: float, *, alpha: float=.05, power: float=.8) -> int:
    if not (0 < p0 < 1 and 0 < mde <= 1-p0):
        raise ValueError("p0 must be in (0,1); positive MDE cannot exceed 1-p0")
    if not (0 < alpha < 1 and 0 < power < 1):
        raise ValueError("alpha and power must be in (0,1)")
    p1=p0+mde
    z_alpha=float(norm.ppf(1-alpha/2))
    z_beta=float(norm.ppf(power))
    pbar=(p0+p1)/2
    numerator=(z_alpha*math.sqrt(2*pbar*(1-pbar)) + z_beta*math.sqrt(p0*(1-p0)+p1*(1-p1)))**2
    return math.ceil(numerator/(mde*mde))


def mde_at_allocation(p0: float, n_per_arm: int, *, alpha: float=.05, power:float=.8) -> float | None:
    if n_per_arm < 2 or not 0 < p0 < 1:
        return None
    hi=1-p0
    if required_users_per_arm(p0,hi,alpha=alpha,power=power)>n_per_arm:
        return None
    lo=0.
    for _ in range(75):
        mid=(lo+hi)/2
        if required_users_per_arm(p0,mid,alpha=alpha,power=power)<=n_per_arm:
            hi=mid
        else:
            lo=mid
    return hi


def analyze(frame: pd.DataFrame, *, guardrails: tuple[tuple[str,str], ...] = (), practical_lift:float=.01, alpha:float=.05, expected_treatment_fraction:float=.5, srm_threshold:float=.001, user_col:str="user_id", arm_col:str="variant", outcome_col:str="converted") -> dict:
    if not 0 <= practical_lift <= 1:
        raise ValueError("practical_lift must be between zero and one")
    if any(direction not in ("increase", "decrease") for _,direction in guardrails):
        raise ValueError("Each guardrail direction must be increase or decrease")
    columns=[name for name,_ in guardrails]
    if len(columns)!=len(set(columns)) or outcome_col in columns:
        raise ValueError("Guardrail columns must be distinct from one another and the primary outcome")
    frame=validate_user_grain(frame,user_col=user_col,arm_col=arm_col,outcome_col=outcome_col,extra_columns=tuple(columns))
    srm=sample_ratio_check(frame,expected_treatment_fraction=expected_treatment_fraction,arm_col=arm_col,threshold=srm_threshold)
    primary=binary_effect(frame,outcome_col,label="Subscription conversion",direction="primary",alpha=alpha,arm_col=arm_col)
    metrics=[binary_effect(frame,col,label=col.replace("_"," ").title(),direction=direction,alpha=alpha,arm_col=arm_col) for col,direction in guardrails]
    eligible=primary.absolute_lift>=practical_lift and primary.p_value<alpha and primary.absolute_lift>0
    significant_harm=any(metric.significant_harm for metric in metrics)
    if srm["flagged"]:
        decision="investigate_assignment_mismatch"
    elif significant_harm:
        decision="investigate_guardrail_harm"
    elif eligible and not metrics:
        decision="guardrail_review_required"
    elif eligible:
        decision="candidate_for_monitored_review"
    else:
        decision="insufficient_positive_evidence"
    n=min(primary.control_n,primary.treatment_n)
    return {
        "analysis_type":"retrospective_simulated_experiment_audit",
        "unit":"assigned_user",
        "method":"two-sided pooled two-proportion z-test; unpooled normal 95% confidence interval; chi-square SRM check",
        "alpha":alpha,"practical_lift_threshold":practical_lift,
        "srm":srm,
        "primary":asdict(primary),
        "guardrails":[asdict(x) for x in metrics],
        "power_planning":{"power_target":.8,"n_per_arm_reference":n,"mde_approx":mde_at_allocation(primary.control_rate,n,alpha=alpha,power=.8),"assumptions":"Equal-arm approximation, two-sided z-test, independent users; not achieved/post-hoc power"},
        "decision":decision,
        "caveats":["Simulated randomized outcomes; no observed commercial impact or production launch recommendation.","Users, not event rows, are the inferential unit. No silent de-duplication or outcome exclusions.","Guardrail significance is not proof of equivalence or absence of meaningful harm; confidence intervals should be reviewed.","This retrospective audit does not establish a prospective preregistration or sequential-peeking policy.","Guardrail analyses and any subgroup exploration are not multiplicity-adjusted."]
    }
