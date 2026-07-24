"""
Depth Derivation

Derives depth from pressure and latitude using the GSW library.
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Dict

import numpy as np
import xarray as xr

import seasenselib.parameters as params
from ...interfaces import IDerivation
from ...unit_handling.handlers.utils import get_unit_normalizations
from .utils import (
    format_coordinate_value,
    list_variants,
    output_name_from_input,
    resolve_lat_lon,
    units_ok,
)

_GSW = None


def _get_gsw():
    global _GSW
    if _GSW is not None:
        return _GSW
    try:
        import gsw  # type: ignore
    except ImportError:
        return None
    _GSW = gsw
    return gsw


class DepthDerivation(IDerivation):
    """
    Derives depth from pressure and latitude using TEOS-10 (GSW).
    
    Requires:
        - pressure (dbar)
        - latitude (degrees)
    
    Produces:
        - depth (meters, positive up; z-from-pressure)
    """

    def __init__(self, use_default_latitude: bool = False, default_latitude: float = 45.0):
        self.use_default_latitude = use_default_latitude
        self.default_latitude = default_latitude

    @staticmethod
    def output_parameter() -> str:
        """Return name of derived parameter."""
        return params.DEPTH

    @staticmethod
    def required_inputs() -> List[str]:
        """Return list of required input parameters."""
        return [params.PRESSURE]

    def can_derive(self, dataset: xr.Dataset) -> bool:
        """Check if depth derivation is possible."""
        if _get_gsw() is None:
            return False
        pressures = list_variants(dataset, params.PRESSURE)
        if not pressures:
            return False
        if not any(units_ok(dataset, name, params.PRESSURE) for name in pressures):
            return False

        return True

    def derive(self, dataset: xr.Dataset) -> xr.DataArray:
        """Derive depth from pressure and latitude."""
        gsw = _get_gsw()
        if gsw is None:
            raise ImportError(
                "GSW library is required for depth derivation. "
                "Install with: pip install gsw"
            )

        lat, used_default = self._resolve_latitude(dataset)
        if lat is None and self.use_default_latitude:
            lat = self.default_latitude
            used_default = True

        outputs: Dict[str, xr.DataArray] = {}
        warnings: List[str] = []

        if lat is None:
            warnings.append(
                "Depth not derived: pressure is available, but latitude is missing. "
                "Provide latitude in the input data or pass --default-latitude LAT "
                "(API: default_latitude=LAT) to explicitly derive depth from pressure."
            )
            return outputs, warnings

        if used_default:
            lat_text = format_coordinate_value(lat)
            warning = (
                f"Latitude not found; using explicit default latitude of {lat_text} degrees for depth calculation. "
                "This is an explicit processing assumption, not instrument metadata. "
                "Omit the fallback latitude option to avoid this behavior."
            )
            warnings.append(warning)

        pressures = list_variants(dataset, params.PRESSURE)
        for pres_name in pressures:
            if not units_ok(dataset, pres_name, params.PRESSURE):
                warnings.append(
                    f"Depth skipped for '{pres_name}': unsupported pressure units."
                )
                continue

            pressure = dataset[pres_name]
            depth = gsw.conversions.z_from_p(pressure.values, lat)

            attrs = {
                **self.metadata(),
                'derivation': f"gsw.z_from_p({pres_name}, latitude)"
            }
            if used_default:
                lat_text = format_coordinate_value(lat)
                attrs['comment'] = (
                    f"{attrs.get('comment', '')}; " if attrs.get('comment') else ""
                ) + (
                    f"Latitude missing; explicit default latitude {lat_text} degrees used for depth derivation "
                    "(processing assumption, not instrument metadata)"
                )

            output_name = output_name_from_input(params.DEPTH, pres_name, params.PRESSURE)
            depth_da = xr.DataArray(
                depth,
                dims=pressure.dims,
                coords=pressure.coords,
                attrs=attrs
            )
            outputs[output_name] = depth_da

        return outputs, warnings

    def metadata(self) -> dict:
        """Return metadata for the derived parameter."""
        from seasenselib.knowledge import load_json
        data = load_json("pipeline/derivation/derivations.json")
        if not isinstance(data, dict) or 'depth' not in data:
            raise RuntimeError(
                "Missing derivation metadata for 'depth' in pipeline/derivation/derivations.json"
            )
        return data['depth']

    @staticmethod
    def _resolve_latitude(dataset: xr.Dataset) -> Tuple[Optional[float], bool]:
        """Return latitude as a scalar float if available (and whether it was defaulted)."""
        lat, _, _ = resolve_lat_lon(dataset)
        lat = DepthDerivation._to_float(lat)
        if lat is not None:
            return lat, False
        return None, False

    @staticmethod
    def _to_float(value) -> Optional[float]:
        if value is None:
            return None
        try:
            arr = np.asarray(value)
            if arr.size == 0:
                return None
            val = float(arr.reshape(-1)[0])
            if np.isnan(val):
                return None
            return val
        except Exception:
            return None

    @staticmethod
    def _pressure_units_ok(dataset: xr.Dataset) -> bool:
        """Ensure pressure units are in dbar before deriving depth."""
        units = dataset[params.PRESSURE].attrs.get('units')
        if not units:
            return False
        normalized = get_unit_normalizations().get(units, units)
        normalized = str(normalized).strip().lower()
        return normalized in ("dbar", "decibar")


__all__ = ["DepthDerivation"]
