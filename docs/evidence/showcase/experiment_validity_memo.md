# Experiment validity | Decision evidence

**Scope:** Seeded synthetic subscription experiment; estimates do not represent observed commercial results.

**Review outcome:** Candidate for monitored review

## Primary outcome — subscription conversion

| Measure | Verified from supplied user-level file |
|---|---:|
| Control users | 9,918 |
| Treatment users | 10,082 |
| Control conversion | 18.61% |
| Treatment conversion | 21.37% |
| Absolute difference | +2.76 pp |
| Approximate 95% CI | [+1.65 pp, +3.87 pp] |
| Two-sided p-value | 1.0494e-06 |
| SRM p-value | 0.24619 |
| SRM flagged | No |
| 80%-power MDE (equal-arm approximation) | +1.57 pp |

## Guardrails

| Guardrail | Control | Treatment | Difference | Approximate 95% CI | Significant adverse direction? |
|---|---:|---:|---:|---|---|
| Active Week 4 | 26.81% | 27.17% | +0.36 pp | [-0.87 pp, +1.59 pp] | No |
| Support Contact Day 14 | 6.89% | 7.07% | +0.19 pp | [-0.52 pp, +0.89 pp] | No |

## Decision interpretation

This is research evidence from simulated outcomes. `Candidate for monitored review` is not an automated shipment or causal business-value recommendation.

## Boundaries

- Simulated randomized outcomes; no observed commercial impact or production launch recommendation.
- Users, not event rows, are the inferential unit. No silent de-duplication or outcome exclusions.
- Guardrail significance is not proof of equivalence or absence of meaningful harm; confidence intervals should be reviewed.
- This retrospective audit does not establish a prospective preregistration or sequential-peeking policy.
- Guardrail analyses and any subgroup exploration are not multiplicity-adjusted.
