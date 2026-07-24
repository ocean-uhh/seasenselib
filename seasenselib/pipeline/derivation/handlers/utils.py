"""
Derivation utilities.

Helpers for selecting numbered input variables and validating units.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import re

import numpy as np
import xarray as xr

import seasenselib.parameters as params
from ...unit_handling.handlers.utils import get_unit_aliases, get_unit_normalizations
from ....knowledge.loader import load_json

_INPUT_UNITS: Optional[Dict[str, List[str]]] = None
_ALIASES: Optional[Dict[str, str]] = None
_NORMALIZATIONS: Optional[Dict[str, str]] = None


def get_input_units() -> Dict[str, List[str]]:
    global _INPUT_UNITS
    if _INPUT_UNITS is None:
        try:
            data = load_json("pipeline/derivation/input_units.json")
            if isinstance(data, dict):
                _INPUT_UNITS = {
                    str(k): [str(v).lower() for v in values]
                    for k, values in data.items()
                    if isinstance(values, list)
                }
            else:
                _INPUT_UNITS = {}
        except Exception:
            _INPUT_UNITS = {}
    return _INPUT_UNITS


def list_variants(dataset: xr.Dataset, base: str) -> List[str]:
    """Return available variable variants like base, base_1, base_2 (sorted)."""
    names: List[str] = []
    if base in dataset.data_vars:
        names.append(base)
    pattern = re.compile(rf"^{re.escape(base)}_(\d+)$")
    numbered: List[Tuple[int, str]] = []
    for name in dataset.data_vars:
        match = pattern.match(name)
        if match:
            numbered.append((int(match.group(1)), name))
    for _, name in sorted(numbered, key=lambda item: item[0]):
        names.append(name)
    return names


def pick_first_variant(dataset: xr.Dataset, base: str) -> Tuple[Optional[str], int]:
    variants = list_variants(dataset, base)
    if not variants:
        return None, 0
    return variants[0], len(variants)


def output_name_from_input(base_output: str, input_name: str, base_input: str) -> str:
    if input_name == base_input:
        return base_output
    suffix = input_name[len(base_input) + 1:]
    return f"{base_output}_{suffix}"


def canonical_unit(unit: str) -> str:
    global _ALIASES, _NORMALIZATIONS
    if _ALIASES is None:
        _ALIASES = get_unit_aliases()
    if _NORMALIZATIONS is None:
        _NORMALIZATIONS = get_unit_normalizations()
    raw = str(unit).strip()
    aliased = _ALIASES.get(raw, raw)
    normalized = _NORMALIZATIONS.get(aliased, aliased)
    return str(normalized).strip().lower()


def units_ok(dataset: xr.Dataset, var_name: str, base: str) -> bool:
    allowed = get_input_units().get(base)
    if not allowed:
        return True
    if var_name not in dataset:
        return False
    unit = dataset[var_name].attrs.get("units")
    if not unit:
        return False
    return canonical_unit(unit) in allowed


def usable_coordinate_value(value) -> Optional[object]:
    """Return coordinate value unless it is empty or entirely NaN."""
    if value is None:
        return None
    try:
        arr = np.asarray(value)
        if arr.size == 0:
            return None
        numeric = arr.astype(float)
        if np.all(np.isnan(numeric)):
            return None
    except (TypeError, ValueError):
        pass
    return value


def resolve_lat_lon(
    dataset: xr.Dataset,
    default_latitude: Optional[float] = None,
    default_longitude: Optional[float] = None,
) -> Tuple[Optional[object], Optional[object], Dict[str, float]]:
    """Resolve latitude/longitude from data, attrs, CF names, or explicit defaults."""
    def _find_value(names: List[str]) -> Optional[object]:
        for name in names:
            if name in dataset.coords:
                value = usable_coordinate_value(dataset.coords[name].values)
                if value is not None:
                    return value
            if name in dataset.data_vars:
                value = usable_coordinate_value(dataset[name].values)
                if value is not None:
                    return value
            if name in dataset.attrs:
                value = usable_coordinate_value(dataset.attrs[name])
                if value is not None:
                    return value
        return None

    lat = _find_value([params.LATITUDE, "lat", "latitude"])
    lon = _find_value([params.LONGITUDE, "lon", "longitude"])

    if lat is None or lon is None:
        for var in dataset.coords.values():
            if var.attrs.get("standard_name") == "latitude" and lat is None:
                lat = usable_coordinate_value(var.values)
            if var.attrs.get("standard_name") == "longitude" and lon is None:
                lon = usable_coordinate_value(var.values)
        for var in dataset.data_vars.values():
            if var.attrs.get("standard_name") == "latitude" and lat is None:
                lat = usable_coordinate_value(var.values)
            if var.attrs.get("standard_name") == "longitude" and lon is None:
                lon = usable_coordinate_value(var.values)

    defaulted: Dict[str, float] = {}
    if lat is None and default_latitude is not None:
        lat = float(default_latitude)
        defaulted["latitude"] = float(lat)
    if lon is None and default_longitude is not None:
        lon = float(default_longitude)
        defaulted["longitude"] = float(lon)

    return lat, lon, defaulted


def format_coordinate_value(value: float) -> str:
    """Format a user-supplied coordinate without unnecessary rounding."""
    return str(float(value))


def format_defaulted_coordinates(defaulted: Dict[str, float]) -> str:
    parts = []
    if "latitude" in defaulted:
        parts.append(f"latitude {format_coordinate_value(defaulted['latitude'])} degrees")
    if "longitude" in defaulted:
        parts.append(f"longitude {format_coordinate_value(defaulted['longitude'])} degrees")
    return " and ".join(parts)


def format_coordinate_names(names: List[str], title: bool = False) -> str:
    text = " and ".join(names)
    return f"{text[:1].upper()}{text[1:]}" if title and text else text


def coordinate_fallback_instruction(missing: List[str]) -> str:
    """Return a CLI/API hint for explicitly supplying missing coordinates."""
    if missing == ["latitude"]:
        return (
            "Provide latitude in the input data or pass --default-latitude LAT "
            "(API: default_latitude=LAT)."
        )
    if missing == ["longitude"]:
        return (
            "Provide longitude in the input data or pass --default-longitude LON "
            "(API: default_longitude=LON)."
        )
    return (
        "Provide latitude and longitude in the input data or pass "
        "--default-latitude LAT and --default-longitude LON "
        "(API: default_latitude=LAT, default_longitude=LON)."
    )


__all__ = [
    "get_input_units",
    "list_variants",
    "pick_first_variant",
    "output_name_from_input",
    "canonical_unit",
    "units_ok",
    "usable_coordinate_value",
    "resolve_lat_lon",
    "format_coordinate_value",
    "format_defaulted_coordinates",
    "format_coordinate_names",
    "coordinate_fallback_instruction",
]
