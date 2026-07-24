"""
Conservative Temperature Derivation

Calculates conservative temperature from in-situ temperature, salinity, and pressure using GSW.
"""

from typing import List, Dict, Tuple, Optional
import xarray as xr

from ...interfaces import IDerivation
import seasenselib.parameters as params
from .utils import (
    coordinate_fallback_instruction,
    format_coordinate_names,
    format_defaulted_coordinates,
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


class ConservativeTemperatureDerivation(IDerivation):
    """
    Derives conservative temperature using the TEOS-10 Gibbs SeaWater (GSW) library.

    Conservative temperature (CT) is computed from practical salinity, in-situ temperature,
    pressure, and geographic position.
    """

    def __init__(
        self,
        default_latitude: Optional[float] = None,
        default_longitude: Optional[float] = None,
    ):
        self.default_latitude = (
            None if default_latitude is None else float(default_latitude)
        )
        self.default_longitude = (
            None if default_longitude is None else float(default_longitude)
        )

    @staticmethod
    def output_parameter() -> str:
        return params.CONSERVATIVE_TEMPERATURE

    @staticmethod
    def required_inputs() -> List[str]:
        return [params.TEMPERATURE, params.SALINITY, params.PRESSURE]

    def can_derive(self, dataset: xr.Dataset) -> bool:
        if _get_gsw() is None:
            return False
        temps = list_variants(dataset, params.TEMPERATURE)
        sals = list_variants(dataset, params.SALINITY)
        press = list_variants(dataset, params.PRESSURE)
        return bool(temps and sals and press)

    def derive(self, dataset: xr.Dataset) -> Tuple[Dict[str, xr.DataArray], List[str]]:
        gsw = _get_gsw()
        if gsw is None:
            raise ImportError(
                "GSW library is required for conservative temperature derivation. "
                "Install with: pip install gsw"
            )

        warnings: List[str] = []
        outputs: Dict[str, xr.DataArray] = {}

        temps = list_variants(dataset, params.TEMPERATURE)
        sals = list_variants(dataset, params.SALINITY)
        press = list_variants(dataset, params.PRESSURE)

        if not temps or not sals or not press:
            return outputs, warnings

        if len(sals) > 1:
            warnings.append(
                "Conservative temperature not derived: multiple salinity variables present."
            )
            return outputs, warnings
        if len(press) > 1:
            warnings.append(
                "Conservative temperature not derived: multiple pressure variables present."
            )
            return outputs, warnings

        sal_name = sals[0]
        pres_name = press[0]

        if not units_ok(dataset, sal_name, params.SALINITY):
            warnings.append(
                f"Conservative temperature not derived: salinity units not supported for '{sal_name}'."
            )
            return outputs, warnings
        if not units_ok(dataset, pres_name, params.PRESSURE):
            warnings.append(
                f"Conservative temperature not derived: pressure units not supported for '{pres_name}'."
            )
            return outputs, warnings

        lat, lon, defaulted = resolve_lat_lon(
            dataset,
            default_latitude=self.default_latitude,
            default_longitude=self.default_longitude,
        )
        if lat is None or lon is None:
            missing = [
                name
                for name, value in (("latitude", lat), ("longitude", lon))
                if value is None
            ]
            verb = "is" if len(missing) == 1 else "are"
            warnings.append(
                f"Conservative temperature not derived: {format_coordinate_names(missing)} "
                f"{verb} missing. {coordinate_fallback_instruction(missing)}"
            )
            return outputs, warnings
        if defaulted:
            warnings.append(
                "Conservative temperature used explicit default "
                f"{format_defaulted_coordinates(defaulted)} because "
                f"{format_coordinate_names(list(defaulted))} missing."
            )

        sal = dataset[sal_name].values
        pres = dataset[pres_name].values

        for temp_name in temps:
            if not units_ok(dataset, temp_name, params.TEMPERATURE):
                warnings.append(
                    f"Conservative temperature skipped for '{temp_name}': unsupported temperature units."
                )
                continue

            temp = dataset[temp_name].values

            sa = gsw.SA_from_SP(sal, pres, lon, lat)
            ct = gsw.CT_from_t(sa, temp, pres)

            output_name = output_name_from_input(
                params.CONSERVATIVE_TEMPERATURE,
                temp_name,
                params.TEMPERATURE,
            )
            ct_da = xr.DataArray(
                ct,
                dims=dataset[temp_name].dims,
                coords=dataset[temp_name].coords,
                attrs={
                    **self.metadata(),
                    "derivation": (
                        f"gsw.CT_from_t(SA_from_SP({sal_name}, {pres_name}, lon, lat), "
                        f"{temp_name}, {pres_name})"
                    ),
                },
            )
            if defaulted:
                comment = ct_da.attrs.get("comment", "")
                note = (
                    f"{format_coordinate_names(list(defaulted), title=True)} missing; "
                    f"explicit default {format_defaulted_coordinates(defaulted)} "
                    "used for conservative temperature derivation"
                )
                ct_da.attrs["comment"] = f"{comment}; {note}".strip("; ")
            outputs[output_name] = ct_da

        return outputs, warnings

    def metadata(self) -> dict:
        from seasenselib.knowledge import load_json
        data = load_json("pipeline/derivation/derivations.json")
        if not isinstance(data, dict) or "conservative_temperature" not in data:
            raise RuntimeError(
                "Missing derivation metadata for 'conservative_temperature' in pipeline/derivation/derivations.json"
            )
        return data["conservative_temperature"]
