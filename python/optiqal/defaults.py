"""Canonical modeling defaults shared across Python surfaces."""

DEFAULT_QALY_DISCOUNT_RATE = 0.03
DEFAULT_COST_DISCOUNT_RATE = 0.03


def validate_qaly_discount_rate(rate: float) -> float:
    """Validate a health-effect discount rate for sensitivity analysis."""
    rate = float(rate)
    if rate < 0:
        raise ValueError("QALY discount rate must be nonnegative.")
    if rate > 0.10:
        raise ValueError(
            "QALY discount rate above 10% is outside supported sensitivity bounds."
        )
    return rate
