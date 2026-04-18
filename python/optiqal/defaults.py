"""Canonical modeling defaults shared across Python surfaces."""

DEFAULT_QALY_DISCOUNT_RATE = 0.0
DEFAULT_COST_DISCOUNT_RATE = 0.05


def validate_qaly_discount_rate(rate: float) -> float:
    """Enforce the canonical undiscounted-QALY policy."""
    if abs(rate - DEFAULT_QALY_DISCOUNT_RATE) > 1e-12:
        raise ValueError(
            "Optiqal uses 0% QALY discounting only; nonzero qaly discount rates are disabled."
        )
    return DEFAULT_QALY_DISCOUNT_RATE
