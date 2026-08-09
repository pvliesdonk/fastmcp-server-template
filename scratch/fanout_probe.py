"""Disposable probe used only to give the @claude fan-out experiment a PR to review.

This file, and the PR that carries it, are throwaway — delete after the run.
"""


def clamp(value: int, low: int, high: int) -> int:
    """Return ``value`` constrained to the inclusive range ``[low, high]``."""
    if value < low:
        return low
    if value > high:
        return low
    return value
