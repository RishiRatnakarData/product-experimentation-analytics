"""Auditable product experimentation analysis for user-level simulated outcomes."""
from .analysis import analyze, binary_effect, mde_at_allocation, required_users_per_arm, sample_ratio_check, validate_user_grain

__all__ = ["analyze","binary_effect","mde_at_allocation","required_users_per_arm","sample_ratio_check","validate_user_grain"]
