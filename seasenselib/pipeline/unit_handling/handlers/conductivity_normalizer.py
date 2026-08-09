"""
Conductivity normalizer.

Converts conductivity variables to the canonical unit mS cm-1 before the
derivation stage runs.  Uses magnitude-based inference to detect and warn
about declared-vs-actual mismatches.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import xarray as xr

from .utils import _base_name
from seasenselib.readers.utils.conductivity_units import (
    infer_conductivity_unit,
    to_mS_cm,
)

logger = logging.getLogger(__name__)

_TARGET_UNIT = "mS cm-1"


class ConductivityNormalizer:
    """Convert conductivity variables to mS cm-1."""

    def normalize(self, ds: xr.Dataset) -> Tuple[xr.Dataset, List[str]]:
        """Normalise all conductivity variables to mS cm-1.

        Parameters
        ----------
        ds : xr.Dataset

        Returns
        -------
        tuple[xr.Dataset, list[str]]
            Updated dataset and list of normalisation records
            (``"var: old_unit -> mS cm-1"``).
        """
        normalizations: List[str] = []

        for var_name in list(ds.data_vars):
            if _base_name(var_name) != "conductivity":
                continue

            current_units = ds[var_name].attrs.get("units", "")
            if not current_units:
                continue
            if current_units == _TARGET_UNIT:
                continue

            values = ds[var_name].values
            try:
                inferred = infer_conductivity_unit(values, declared=current_units)
                converted, canonical = to_mS_cm(values, inferred)
            except ValueError as exc:
                logger.warning(
                    "ConductivityNormalizer: cannot convert '%s' (units='%s'): %s",
                    var_name,
                    current_units,
                    exc,
                )
                continue

            saved_attrs = dict(ds[var_name].attrs)
            dims = ds[var_name].dims
            ds[var_name] = (dims, converted)
            ds[var_name].attrs.update(saved_attrs)
            ds[var_name].attrs["units"] = canonical
            ds[var_name].attrs["conductivity_normalised_from"] = current_units
            normalizations.append(f"{var_name}: {current_units} -> {canonical}")
            logger.info(
                "Normalised conductivity '%s': %s -> %s",
                var_name,
                current_units,
                canonical,
            )

        return ds, normalizations
