"""
Unit normalizer.

Normalizes known unit variants to preferred CF-like strings and reports
missing units when expected.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple, List
import warnings
import logging

import xarray as xr

from .utils import get_unit_normalizations, get_expected_units, _base_name

logger = logging.getLogger(__name__)


class UnitNormalizer:
    """Normalize unit strings and report missing units."""

    def __init__(self, strict: bool = False, auto_convert: bool = True,
                 custom_conversions: Optional[Dict[str, str]] = None,
                 expected_units: Optional[Dict[str, str]] = None):
        self.strict = strict
        self.auto_convert = auto_convert
        self.expected_units = expected_units or get_expected_units()
        self.unit_normalizations = get_unit_normalizations()
        if custom_conversions:
            self.unit_normalizations.update(custom_conversions)

    def normalize(self, ds: xr.Dataset) -> Tuple[xr.Dataset, List[str], List[str]]:
        issues: List[str] = []
        relabels: List[str] = []

        for var_name in ds.data_vars:
            var = ds[var_name]
            if 'units' not in var.attrs:
                expected = self.expected_units.get(_base_name(var_name))
                if expected:
                    msg = f"Variable '{var_name}' missing units attribute (expected: {expected})"
                    issues.append(msg)
                    if self.strict:
                        raise ValueError(msg)
                    warnings.warn(msg)
                    logger.debug(msg)
                continue

            current_units = var.attrs['units']
            if self.auto_convert and current_units in self.unit_normalizations:
                old_units = current_units
                new_units = self.unit_normalizations[current_units]
                var.attrs['units'] = new_units
                relabels.append(f"{var_name}: {old_units} -> {new_units}")
                logger.debug("Relabelled units for '%s': %s -> %s", var_name, old_units, new_units)
            elif _base_name(var_name) in self.expected_units:
                expected = self.expected_units[_base_name(var_name)]
                if current_units != expected:
                    msg = (
                        f"Variable '{var_name}' has unit '{current_units}' "
                        f"but expected '{expected}'"
                    )
                    issues.append(msg)
                    if self.strict:
                        raise ValueError(msg)
                    warnings.warn(msg)
                    logger.debug(msg)

        return ds, issues, relabels
