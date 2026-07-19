"""Regression test for the TS plotter temperature/potential-temperature issue.

The TS plotter must accept a dataset that has ``potential_temperature`` but no
bare ``temperature`` (e.g. when in-situ temperature is stored as
``temperature_1`` / ``temperature_2``). See the reported issue where
``required_vars`` hard-required ``params.TEMPERATURE`` even though the plotter
prefers ``params.POTENTIAL_TEMPERATURE`` when present.
"""

import matplotlib

matplotlib.use("Agg")

import pytest
import xarray as xr
import numpy as np

import seasenselib.parameters as params
from seasenselib.plotters.ts_diagram_plotter import TsDiagramPlotter


def _make_dataset(temperature_var):
    """Build a minimal dataset with the given temperature variable name."""
    n = 5
    time = np.array(
        ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"],
        dtype="datetime64[s]",
    )
    ds = xr.Dataset(
        {
            temperature_var: (
                "time",
                np.linspace(10.0, 12.0, n),
                {"long_name": "temperature", "units": "degC"},
            ),
            params.SALINITY: (
                "time",
                np.linspace(34.0, 35.0, n),
                {"long_name": "salinity", "units": "PSU"},
            ),
            params.DEPTH: (
                "time",
                np.linspace(0.0, 100.0, n),
                {"long_name": "depth", "units": "m"},
            ),
        },
        coords={"time": time},
    )
    return ds


def test_ts_plotter_accepts_potential_temperature_without_temperature():
    """Reproduces the reported bug: potential_temperature present, no bare
    temperature (only temperature_1 / temperature_2)."""
    ds = _make_dataset(params.POTENTIAL_TEMPERATURE)
    # Add the subscripted in place temperatures that exist in the demo notebook.
    n = ds.sizes["time"]
    ds[params.TEMPERATURE + "_1"] = (
        "time",
        np.linspace(10.0, 12.0, n),
        {"long_name": "temperature 1", "units": "degC"},
    )
    ds[params.TEMPERATURE + "_2"] = (
        "time",
        np.linspace(10.0, 12.0, n),
        {"long_name": "temperature 2", "units": "degC"},
    )

    plotter = TsDiagramPlotter(ds)
    # Should not raise ValueError about missing temperature.
    plotter.plot(output_file="test_ts_fix.png")
    assert True


def test_ts_plotter_accepts_bare_temperature():
    ds = _make_dataset(params.TEMPERATURE)
    plotter = TsDiagramPlotter(ds)
    plotter.plot(output_file="test_ts_fix2.png")
    assert True


def test_ts_plotter_rejects_when_no_temperature_at_all():
    ds = _make_dataset(params.TEMPERATURE + "_1")  # only subscripted
    plotter = TsDiagramPlotter(ds)
    with pytest.raises(ValueError):
        plotter.plot()
