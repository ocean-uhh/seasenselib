from __future__ import annotations

import logging

import numpy as np
import pytest
import xarray as xr

from seasenselib.core.exceptions import WriterError
from seasenselib.writers.netcdf_writer import NetCdfWriter


def test_netcdf_writer_sanitizes_slashes_by_default(tmp_path):
    ds = xr.Dataset({"cond0S/m": ("time", np.array([1.0, 2.0]))})
    output = tmp_path / "sanitized_by_default.nc"

    NetCdfWriter(ds).write(str(output))

    assert "cond0S/m" in ds.data_vars
    with xr.open_dataset(output) as written:
        assert "cond0S_m" in written.data_vars
        assert written["cond0S_m"].attrs["original_name"] == "cond0S/m"


def test_netcdf_writer_logs_when_names_are_sanitized(tmp_path, caplog):
    ds = xr.Dataset({"cond0S/m": ("time", np.array([1.0, 2.0]))})
    output = tmp_path / "sanitized_log.nc"

    with caplog.at_level(
        logging.INFO,
        logger="seasenselib.writers.netcdf_writer",
    ):
        NetCdfWriter(ds).write(str(output))

    assert "Sanitized 1 NetCDF name(s)" in caplog.text
    assert "'cond0S/m' -> 'cond0S_m'" in caplog.text


def test_netcdf_writer_preserves_existing_file_when_validation_fails(tmp_path):
    existing = xr.Dataset({"temperature": ("time", np.array([10.0]))})
    output = tmp_path / "existing.nc"
    existing.to_netcdf(output)
    original_bytes = output.read_bytes()

    invalid = xr.Dataset({"cond0S/m": ("time", np.array([1.0, 2.0]))})

    with pytest.raises(WriterError, match="NetCDF output cannot be created"):
        NetCdfWriter(invalid).write(str(output), sanitize_names=False)

    assert output.read_bytes() == original_bytes


def test_netcdf_writer_can_sanitize_slashes_in_names(tmp_path):
    ds = xr.Dataset(
        {"cond0S/m": ("sample/id", np.array([1.0, 2.0]))},
        coords={"sample/id": np.array([0, 1])},
    )
    output = tmp_path / "sanitized.nc"

    NetCdfWriter(ds).write(str(output), sanitize_names=True)

    assert "cond0S/m" in ds.data_vars
    with xr.open_dataset(output) as written:
        assert "sample_id" in written.dims
        assert "sample_id" in written.coords
        assert "cond0S_m" in written.data_vars
        assert written["cond0S_m"].attrs["original_name"] == "cond0S/m"
        assert written["sample_id"].attrs["original_name"] == "sample/id"


def test_netcdf_writer_sanitized_name_collision_fails_cleanly(tmp_path):
    ds = xr.Dataset(
        {
            "cond0S/m": ("time", np.array([1.0, 2.0])),
            "cond0S_m": ("time", np.array([3.0, 4.0])),
        }
    )
    output = tmp_path / "collision.nc"

    with pytest.raises(WriterError, match="duplicate name 'cond0S_m'"):
        NetCdfWriter(ds).write(str(output))

    assert not output.exists()


def test_netcdf_writer_writes_valid_dataset_with_cleaned_attrs(tmp_path):
    ds = xr.Dataset(
        {"conductivity": ("time", np.array([1.0, 2.0]))},
        attrs={"config": {"sensor": "SBE37"}, "optional": None},
    )
    ds["conductivity"].attrs["metadata"] = {"units_source": "CNV"}
    output = tmp_path / "valid.nc"

    NetCdfWriter(ds).write(str(output))

    with xr.open_dataset(output) as written:
        assert list(written.data_vars) == ["conductivity"]
        assert written["conductivity"].values.tolist() == [1.0, 2.0]
        assert written.attrs["config"] == '{"sensor": "SBE37"}'
        assert written.attrs["optional"] == ""
        assert (
            written["conductivity"].attrs["metadata"] == '{"units_source": "CNV"}'
        )


def test_netcdf_writer_moves_datetime_units_attrs_to_encoding(tmp_path):
    ds = xr.Dataset(
        {"temperature": ("time", np.array([1.0, 2.0]))},
        coords={
            "time": np.array(
                ["2026-01-01T00:00:00", "2026-01-01T00:00:01"],
                dtype="datetime64[ns]",
            )
        },
    )
    ds["time"].attrs["units"] = "seconds since 1970-01-01"
    ds["time"].attrs["calendar"] = "proleptic_gregorian"
    ds["time"].attrs["long_name"] = "Time"
    output = tmp_path / "time_units.nc"

    NetCdfWriter(ds).write(str(output))

    assert ds["time"].attrs["units"] == "seconds since 1970-01-01"
    assert ds["time"].attrs["calendar"] == "proleptic_gregorian"
    with xr.open_dataset(output) as written:
        assert written["time"].values.tolist() == ds["time"].values.tolist()
        assert written["time"].attrs["long_name"] == "Time"

    with xr.open_dataset(output, decode_times=False) as raw:
        assert raw["time"].attrs["units"] == "seconds since 1970-01-01"
        assert raw["time"].attrs["calendar"] == "proleptic_gregorian"
