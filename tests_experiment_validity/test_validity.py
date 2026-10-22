"""Standalone acceptance cases for randomized-user analysis."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from experiment_validity.analysis import analyze, binary_effect, mde_at_allocation, required_users_per_arm, sample_ratio_check, validate_user_grain
from experiment_validity.report import write_outputs


def _frame(n=200, c_rate=.2, t_rate=.25):
    assert n%2==0
    n2=n//2
    return pd.DataFrame({
        "user_id": list(range(n)),
        "variant": ["control"]*n2+["treatment"]*n2,
        "converted": [1]*int(n2*c_rate)+[0]*(n2-int(n2*c_rate))+[1]*int(n2*t_rate)+[0]*(n2-int(n2*t_rate)),
        "active_week_4": [1]*60+[0]*(n2-60)+[1]*60+[0]*(n2-60),
        "support_14d": [0]*n2+[1]*30+[0]*(n2-30),
    })


def test_valid_user_grain():
    assert len(validate_user_grain(_frame()))==200


def test_duplicate_id_cannot_silently_deduplicate():
    df=_frame()
    df.loc[1,"user_id"]=df.loc[0,"user_id"]
    with pytest.raises(ValueError,match="Duplicate"):
        analyze(df)


def test_event_level_replication_is_rejected():
    df=_frame()
    with pytest.raises(ValueError,match="Duplicate"):
        analyze(pd.concat([df,df.iloc[[0]]],ignore_index=True))


def test_missing_assignment_rejected():
    df=_frame()
    df.loc[2,"variant"]=None
    with pytest.raises(ValueError,match="Exactly two arms"):
        analyze(df)


def test_invalid_binary_outcome_rejected():
    df=_frame()
    df.loc[2,"converted"]=2
    with pytest.raises(ValueError,match="0/1"):
        analyze(df)


def test_missing_binary_outcome_rejected():
    df=_frame()
    df.loc[2,"converted"]=None
    with pytest.raises(ValueError,match="missing binary"):
        analyze(df)


def test_missing_column_rejected():
    with pytest.raises(ValueError,match="Missing required columns"):
        analyze(_frame().drop(columns="converted"))


def test_srm_balanced_vs_unbalanced():
    df=_frame()
    assert sample_ratio_check(df)["flagged"] is False
    unbalanced=pd.concat([df[df.variant=="control"].iloc[:10],df[df.variant=="treatment"]],ignore_index=True)
    assert sample_ratio_check(unbalanced)["flagged"] is True


def test_expected_allocation_configurable():
    df=pd.DataFrame({"variant":["control"]*75+["treatment"]*25})
    assert sample_ratio_check(df,expected_treatment_fraction=.25)["p_value"]==pytest.approx(1)


def test_group_rates_and_ci():
    df=_frame()
    m=binary_effect(df,"converted")
    assert m.control_n==m.treatment_n==100
    assert m.absolute_lift==pytest.approx(.05)
    assert m.ci_low<=m.absolute_lift<=m.ci_high
    assert 0<=m.p_value<=1


def test_all_zeros_no_division_error():
    df=_frame()
    df["converted"]=0
    x=analyze(df)["primary"]
    assert x["p_value"]==1.
    assert x["relative_lift"] is None


def test_all_ones_no_division_error():
    df=_frame()
    df["converted"]=1
    assert analyze(df)["primary"]["p_value"]==1.


def test_guardrail_harm_blocks_candidate():
    df=_frame(n=2000)
    df.loc[df.variant=="control","support_14d"]=0
    df.loc[df.variant=="treatment","support_14d"]=1
    result=analyze(df,guardrails=(("support_14d","decrease"),))
    assert result["guardrails"][0]["significant_harm"]
    assert result["decision"]=="investigate_guardrail_harm"


def test_balanced_guardrail_not_claim_equivalence():
    df=_frame()
    result=analyze(df,guardrails=(("active_week_4","increase"),))
    assert not result["guardrails"][0]["significant_harm"]
    assert any("not proof of equivalence" in s for s in result["caveats"])


def test_srm_overrides_favorable_primary():
    df=_frame(n=2000)
    unbalanced=pd.concat([df[df.variant=="control"].iloc[:10],df[df.variant=="treatment"]],ignore_index=True)
    assert analyze(unbalanced)["decision"]=="investigate_assignment_mismatch"


def test_no_false_claim_from_insignificant_lift():
    df=_frame(n=200,c_rate=.20,t_rate=.21)
    assert analyze(df)["decision"]=="insufficient_positive_evidence"


def test_power_planning_decreases_with_more_users():
    required=required_users_per_arm(.2,.02)
    assert required>1000
    assert mde_at_allocation(.2,15000) < mde_at_allocation(.2,5000)


def test_invalid_allocation_rejected():
    with pytest.raises(ValueError):
        sample_ratio_check(_frame(),expected_treatment_fraction=1.0)


def test_guardrail_schema_rejected():
    with pytest.raises(ValueError,match="Missing required columns"):
        analyze(_frame(),guardrails=(("nonexistent","increase"),))
    with pytest.raises(ValueError,match="must be distinct"):
        analyze(_frame(),guardrails=(("converted","increase"),))


def test_outputs_evidence_is_valid_json_and_html_safe_markdown(tmp_path:Path):
    out=analyze(_frame(),guardrails=(("active_week_4","increase"),))
    files=write_outputs(out,tmp_path)
    assert len(files)==2
    data=json.loads((tmp_path/"experiment_validity.json").read_text(encoding="utf-8"))
    assert data["unit"]=="assigned_user"
    memo=(tmp_path/"experiment_validity_memo.md").read_text(encoding="utf-8")
    assert "Simulated" in memo or "simulated" in memo
    assert "95% CI" in memo


def test_results_reproducible():
    df=_frame(2000)
    assert analyze(df)==analyze(copy.deepcopy(df))


def test_positive_primary_needs_at_least_one_guardrail():
    # A strong synthetic treatment difference does not bypass the guardrail gate.
    df=_frame(n=2000,c_rate=.2,t_rate=.3)
    assert analyze(df)["decision"] == "guardrail_review_required"


def test_plot_creates_nonempty_file(tmp_path:Path):
    from experiment_validity.report import save_effect_plot
    rep=analyze(_frame(),guardrails=(("active_week_4","increase"),))
    path=save_effect_plot(rep,tmp_path/"figure.png")
    assert path.exists() and path.stat().st_size>5_000
