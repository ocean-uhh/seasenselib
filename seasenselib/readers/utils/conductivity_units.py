"""
Conductivity unit inference and conversion.

Seawater conductivity ranges are non-overlapping by a factor of 10, which
makes unit inference from magnitude reliable:

    S/m   : ~1 – 10      (open-ocean: 2.5 – 7.5)
    mS/cm : ~10 – 100    (open-ocean: 25 – 75)
    uS/cm : ~10000–100000

Use ``infer_conductivity_unit`` to verify a declared unit against the data
magnitude and ``to_mS_cm`` to convert to the canonical ``mS cm-1``.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np

logger = logging.getLogger(__name__)

_COND_RANGES: dict[str, tuple[float, float]] = {
    "S/m":   (0.5,     10.0),
    "mS/cm": (10.0,  1000.0),
    "uS/cm": (500.0, 1_000_000.0),
}

_S_PER_M_ALIASES: frozenset[str] = frozenset({"S/m", "S m-1"})
_MS_PER_CM_ALIASES: frozenset[str] = frozenset({"mS/cm", "mS cm-1"})
_US_PER_CM_ALIASES: frozenset[str] = frozenset({"uS/cm", "µS/cm", "uS cm-1", "µS cm-1"})


def _canonical_declared(declared: str) -> str | None:
    """Map a declared unit string to the S/m | mS/cm | uS/cm bucket, or None."""
    d = declared.strip()
    if d in _S_PER_M_ALIASES:
        return "S/m"
    if d in _MS_PER_CM_ALIASES:
        return "mS/cm"
    if d in _US_PER_CM_ALIASES:
        return "uS/cm"
    return None


def infer_conductivity_unit(
    values: np.ndarray,
    declared: str | None = None,
) -> str:
    """Return the conductivity unit implied by the data's magnitude.

    Parameters
    ----------
    values : np.ndarray
        Conductivity values (any unit).
    declared : str, optional
        Unit claimed by the file header or channel name. When given and it
        disagrees with the inferred unit, a warning is issued.

    Returns
    -------
    str
        One of ``"S/m"``, ``"mS/cm"``, ``"uS/cm"``.

    Raises
    ------
    ValueError
        If the median fits no known range, or all values are non-finite.
    """
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise ValueError(
            "Cannot infer conductivity unit: no finite values in array"
        )

    median = float(np.median(finite))
    inferred: str | None = None

    # S/m and mS/cm ranges overlap at 10.0 — resolve by leaning on the wider gap:
    # open-ocean S/m tops out at ~7.5; mS/cm starts at ~25 for ocean water.
    # The 10–25 gap is brackish/estuarine; we still infer by best-fit range.
    for unit, (low, high) in _COND_RANGES.items():
        if low <= median < high:
            inferred = unit
            break

    if inferred is None:
        raise ValueError(
            f"Cannot infer conductivity unit: median {median:.4g} fits no known "
            f"range (S/m 0.5–10, mS/cm 10–1000, uS/cm 500–1000000). "
            f"Check the data or supply units explicitly."
        )

    if declared is not None:
        declared_canonical = _canonical_declared(declared)
        if declared_canonical is not None and declared_canonical != inferred:
            msg = (
                f"Conductivity unit mismatch: file declares '{declared}' but median "
                f"value {median:.4g} implies '{inferred}'. Check instrument output settings."
            )
            logger.warning(msg)
            warnings.warn(msg, UserWarning, stacklevel=2)

    return inferred


def to_mS_cm(values: np.ndarray, from_unit: str) -> tuple[np.ndarray, str]:
    """Convert conductivity values to mS cm-1.

    Parameters
    ----------
    values : np.ndarray
        Input conductivity values.
    from_unit : str
        Source unit string (e.g. ``"S/m"``, ``"S m-1"``, ``"mS/cm"``).

    Returns
    -------
    tuple[np.ndarray, str]
        ``(converted_values, "mS cm-1")``

    Raises
    ------
    ValueError
        If ``from_unit`` is not recognised.
    """
    unit = from_unit.strip()
    arr = np.asarray(values, dtype=float)
    if unit in _S_PER_M_ALIASES:
        return arr * 10.0, "mS cm-1"
    if unit in _MS_PER_CM_ALIASES:
        return arr.copy(), "mS cm-1"
    if unit in _US_PER_CM_ALIASES:
        return arr / 1000.0, "mS cm-1"
    raise ValueError(
        f"Unrecognised conductivity unit for conversion to mS cm-1: '{from_unit}'. "
        f"Expected one of: S/m, S m-1, mS/cm, mS cm-1, uS/cm, µS/cm."
    )
