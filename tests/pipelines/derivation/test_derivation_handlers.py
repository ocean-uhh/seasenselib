import numpy as np
import pytest
import xarray as xr

from seasenselib.pipeline.base import StageContext
from seasenselib.pipeline.interfaces import IDerivation
from seasenselib.pipeline.derivation.handlers.derivation_runner import DerivationRunner
from seasenselib.pipeline.derivation.handlers.utils import units_ok

import seasenselib.pipeline.derivation.handlers.density_derivation as density_mod
import seasenselib.pipeline.derivation.handlers.potential_temperature_derivation as pt_mod
import seasenselib.pipeline.derivation.handlers.conservative_temperature_derivation as ct_mod
import seasenselib.pipeline.derivation.handlers.sound_speed_derivation as ss_mod
import seasenselib.pipeline.derivation.handlers.depth_derivation as depth_mod
import seasenselib.pipeline.derivation.handlers.absolute_salinity_derivation as as_mod


def _base_dataset():
    ds = xr.Dataset(
        {
            "temperature": (["time"], np.array([10.0, 11.0])),
            "salinity": (["time"], np.array([35.0, 35.1])),
            "pressure": (["time"], np.array([10.0, 11.0])),
        }
    )
    ds["temperature"].attrs["units"] = "degC"
    ds["salinity"].attrs["units"] = "1"
    ds["pressure"].attrs["units"] = "dbar"
    return ds


def test_density_derivation_missing_inputs():
    ds = xr.Dataset({"temperature": (["time"], [1.0, 2.0])})
    derivation = density_mod.DensityDerivation()
    assert derivation.can_derive(ds) is False


def test_density_derivation_import_error(monkeypatch):
    ds = _base_dataset()
    derivation = density_mod.DensityDerivation()
    monkeypatch.setattr(density_mod, "_get_gsw", lambda: None)
    assert derivation.can_derive(ds) is False
    with pytest.raises(ImportError):
        derivation.derive(ds)


def test_density_derivation_positive_if_gsw_available():
    if density_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    derivation = density_mod.DensityDerivation()
    result, warnings = derivation.derive(ds)
    assert warnings == []
    assert result.dims == ds["temperature"].dims
    assert "standard_name" in result.attrs


def test_potential_temperature_derivation_negative_missing_inputs():
    ds = xr.Dataset({"temperature": (["time"], [1.0, 2.0])})
    derivation = pt_mod.PotentialTemperatureDerivation()
    assert derivation.can_derive(ds) is False


def test_potential_temperature_derivation_import_error(monkeypatch):
    ds = _base_dataset()
    derivation = pt_mod.PotentialTemperatureDerivation()
    monkeypatch.setattr(pt_mod, "_get_gsw", lambda: None)
    assert derivation.can_derive(ds) is False
    with pytest.raises(ImportError):
        derivation.derive(ds)


def test_potential_temperature_derivation_positive_if_gsw_available():
    if pt_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    derivation = pt_mod.PotentialTemperatureDerivation()
    outputs, warnings = derivation.derive(ds)
    assert warnings == []
    assert "potential_temperature" in outputs
    result = outputs["potential_temperature"]
    assert result.dims == ds["temperature"].dims
    assert "standard_name" in result.attrs


def test_conservative_temperature_derivation_requires_lat_lon():
    ds = _base_dataset()
    derivation = ct_mod.ConservativeTemperatureDerivation()
    outputs, warnings = derivation.derive(ds)
    assert outputs == {}
    assert any("latitude and longitude are missing" in w for w in warnings)
    assert any("--default-latitude" in w and "--default-longitude" in w for w in warnings)


def test_conservative_temperature_derivation_treats_nan_lat_lon_as_missing():
    ds = _base_dataset()
    ds = ds.assign_coords(latitude=np.nan, longitude=np.nan)
    derivation = ct_mod.ConservativeTemperatureDerivation()
    outputs, warnings = derivation.derive(ds)

    assert outputs == {}
    assert any("latitude and longitude are missing" in w for w in warnings)


def test_conservative_temperature_derivation_uses_default_latitude_with_longitude():
    if ct_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    ds.attrs["longitude"] = 10.0
    derivation = ct_mod.ConservativeTemperatureDerivation(default_latitude=54.0)
    outputs, warnings = derivation.derive(ds)

    assert "conservative_temperature" in outputs
    assert any("default latitude 54.0" in w for w in warnings)
    assert "explicit default latitude 54.0 degrees" in outputs["conservative_temperature"].attrs["comment"]


def test_conservative_temperature_derivation_uses_default_longitude_with_latitude():
    if ct_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    ds.attrs["latitude"] = 54.0
    derivation = ct_mod.ConservativeTemperatureDerivation(default_longitude=10.0)
    outputs, warnings = derivation.derive(ds)

    assert "conservative_temperature" in outputs
    assert any("default longitude 10.0" in w for w in warnings)
    assert "explicit default longitude 10.0" in outputs["conservative_temperature"].attrs["comment"]


def test_conservative_temperature_missing_longitude_points_to_default_longitude():
    if ct_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    ds.attrs["latitude"] = 54.0
    derivation = ct_mod.ConservativeTemperatureDerivation()
    outputs, warnings = derivation.derive(ds)

    assert outputs == {}
    assert any("longitude is missing" in w for w in warnings)
    assert any("--default-longitude" in w for w in warnings)


def test_conservative_temperature_derivation_uses_default_coordinates():
    if ct_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    derivation = ct_mod.ConservativeTemperatureDerivation(
        default_latitude=54.0,
        default_longitude=10.0,
    )
    outputs, warnings = derivation.derive(ds)

    assert "conservative_temperature" in outputs
    assert any("default latitude 54.0 degrees and longitude 10.0 degrees" in w for w in warnings)
    assert "Latitude and longitude missing" in outputs["conservative_temperature"].attrs["comment"]


def test_conservative_temperature_derivation_positive_if_gsw_available():
    if ct_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    ds.attrs["latitude"] = 54.0
    ds.attrs["longitude"] = 10.0
    derivation = ct_mod.ConservativeTemperatureDerivation()
    outputs, warnings = derivation.derive(ds)
    assert warnings == []
    assert "conservative_temperature" in outputs
    result = outputs["conservative_temperature"]
    assert result.dims == ds["temperature"].dims
    assert "standard_name" in result.attrs


def test_absolute_salinity_derivation_treats_nan_lat_lon_as_missing():
    ds = _base_dataset()
    ds = ds.assign_coords(latitude=np.nan, longitude=np.nan)
    derivation = as_mod.AbsoluteSalinityDerivation()
    outputs, warnings = derivation.derive(ds)

    assert outputs == {}
    assert any("latitude and longitude are missing" in w for w in warnings)


def test_absolute_salinity_derivation_uses_default_latitude_with_longitude():
    if as_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    ds.attrs["longitude"] = 10.0
    derivation = as_mod.AbsoluteSalinityDerivation(default_latitude=54.0)
    outputs, warnings = derivation.derive(ds)

    assert "absolute_salinity" in outputs
    assert any("default latitude 54.0" in w for w in warnings)
    assert "explicit default latitude 54.0 degrees" in outputs["absolute_salinity"].attrs["comment"]


def test_absolute_salinity_derivation_uses_default_longitude_with_latitude():
    if as_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    ds.attrs["latitude"] = 54.0
    derivation = as_mod.AbsoluteSalinityDerivation(default_longitude=10.0)
    outputs, warnings = derivation.derive(ds)

    assert "absolute_salinity" in outputs
    assert any("default longitude 10.0" in w for w in warnings)
    assert "explicit default longitude 10.0" in outputs["absolute_salinity"].attrs["comment"]


def test_absolute_salinity_missing_longitude_points_to_default_longitude():
    if as_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    ds.attrs["latitude"] = 54.0
    derivation = as_mod.AbsoluteSalinityDerivation()
    outputs, warnings = derivation.derive(ds)

    assert outputs == {}
    assert any("longitude is missing" in w for w in warnings)
    assert any("--default-longitude" in w for w in warnings)


def test_absolute_salinity_derivation_uses_default_coordinates():
    if as_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    derivation = as_mod.AbsoluteSalinityDerivation(
        default_latitude=54.0,
        default_longitude=10.0,
    )
    outputs, warnings = derivation.derive(ds)

    assert "absolute_salinity" in outputs
    assert any("default latitude 54.0 degrees and longitude 10.0 degrees" in w for w in warnings)
    assert "Latitude and longitude missing" in outputs["absolute_salinity"].attrs["comment"]


def test_sound_speed_derivation_negative_missing_inputs():
    ds = xr.Dataset({"salinity": (["time"], [1.0, 2.0])})
    derivation = ss_mod.SoundSpeedDerivation()
    assert derivation.can_derive(ds) is False


def test_sound_speed_derivation_import_error(monkeypatch):
    ds = _base_dataset()
    derivation = ss_mod.SoundSpeedDerivation()
    monkeypatch.setattr(ss_mod, "_get_gsw", lambda: None)
    assert derivation.can_derive(ds) is False
    with pytest.raises(ImportError):
        derivation.derive(ds)


def test_sound_speed_derivation_positive_if_gsw_available():
    if ss_mod._get_gsw() is None:
        pytest.skip("GSW not available")
    ds = _base_dataset()
    derivation = ss_mod.SoundSpeedDerivation()
    result, warnings = derivation.derive(ds)
    assert warnings == []
    assert result.dims == ds["temperature"].dims
    assert "standard_name" in result.attrs


def test_depth_derivation_requires_pressure_units():
    ds = xr.Dataset({"pressure": (["time"], [1.0, 2.0])})
    derivation = depth_mod.DepthDerivation()
    assert derivation.can_derive(ds) is False


def test_salinity_derivations_accept_cf_generic_salinity_units():
    ds = _base_dataset()
    ds["salinity"].attrs["units"] = "1e-3"

    assert units_ok(ds, "salinity", "salinity") is True


def test_depth_derivation_default_latitude_behavior():
    ds = xr.Dataset({"pressure": (["time"], [10.0, 12.0])})
    ds["pressure"].attrs["units"] = "dbar"
    derivation = depth_mod.DepthDerivation(use_default_latitude=True, default_latitude=45.0)

    if depth_mod._get_gsw() is None:
        pytest.skip("GSW not available")

    outputs, warnings = derivation.derive(ds)
    assert "depth" in outputs
    assert any("explicit default latitude of 45.0 degrees" in warning for warning in warnings)
    result = outputs["depth"]
    assert "comment" in result.attrs
    assert "explicit default latitude 45.0 degrees" in result.attrs["comment"]
    assert "latitude" not in ds.coords

    warning_text = "\n".join(warnings)
    assert "reader-arg" not in warning_text
    assert "explicit default latitude of 45.0 degrees" in warning_text
    assert "Omit the fallback latitude option" in warning_text


def test_depth_derivation_missing_latitude_no_default():
    ds = xr.Dataset({"pressure": (["time"], [10.0, 12.0])})
    ds["pressure"].attrs["units"] = "dbar"
    derivation = depth_mod.DepthDerivation(use_default_latitude=False)
    assert derivation.can_derive(ds) is True

    outputs, warnings = derivation.derive(ds)

    assert outputs == {}
    assert any("Depth not derived" in warning for warning in warnings)
    assert any("--default-latitude" in warning for warning in warnings)


def test_depth_derivation_import_error(monkeypatch):
    ds = _base_dataset()
    derivation = depth_mod.DepthDerivation(use_default_latitude=True)
    monkeypatch.setattr(depth_mod, "_get_gsw", lambda: None)
    assert derivation.can_derive(ds) is False
    with pytest.raises(ImportError):
        derivation.derive(ds)


class DummyDerivation(IDerivation):
    def output_parameter(self) -> str:
        return "dummy"

    def required_inputs(self):
        return ["temperature"]

    def can_derive(self, dataset: xr.Dataset) -> bool:
        return "temperature" in dataset.data_vars

    def derive(self, dataset: xr.Dataset) -> xr.DataArray:
        return xr.DataArray(
            np.ones_like(dataset["temperature"].values),
            dims=dataset["temperature"].dims,
            coords=dataset["temperature"].coords,
            attrs={"units": "1"},
        )

    def metadata(self):
        return {"units": "1"}


def test_derivation_runner_adds_and_skips():
    ds = xr.Dataset({"temperature": (["time"], [1.0, 2.0])})
    ds["temperature"].attrs["units"] = "degC"
    runner = DerivationRunner(derivations=[DummyDerivation()])
    result = runner.process(StageContext(ds, {}))
    assert "dummy" in result.dataset

    # Should skip if already present
    ds2 = xr.Dataset({
        "temperature": (["time"], [1.0, 2.0]),
        "dummy": (["time"], [9.0, 9.0]),
    })
    ds2["temperature"].attrs["units"] = "degC"
    result2 = runner.process(StageContext(ds2, {}))
    assert np.all(result2.dataset["dummy"].values == np.array([9.0, 9.0]))


def test_derivation_unit_guard_skips_on_unit_mismatch():
    ds = xr.Dataset({"temperature": (["time"], [1.0, 2.0])})
    ds["temperature"].attrs["units"] = "K"
    runner = DerivationRunner(derivations=[DummyDerivation()])
    context = StageContext(ds, {})
    result = runner.process(context)

    assert "dummy" not in result.dataset
    warnings = result.metadata.get("warnings", [])
    assert any("units for 'temperature'" in w for w in warnings)
