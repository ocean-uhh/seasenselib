import argparse
import json

import numpy as np
import xarray as xr

from seasenselib.cli.commands.data_commands import _write_processing_protocol, ShowCommand


def test_processing_protocol_written(tmp_path):
    output_path = tmp_path / "out.nc.processing.protocol.json"

    args = argparse.Namespace(
        input="input.cnv",
        output="out.nc",
        output_format="netcdf",
        pipeline_profile="default",
        pipeline_file=None,
        pipeline_apply_stages=None,
        pipeline_skip_stages=None,
        pipeline_apply_handlers=None,
        pipeline_skip_handlers=None,
        default_latitude=54.0,
        default_longitude=10.0,
        raw_only=False,
        processing_protocol=str(output_path),
    )

    dataset = xr.Dataset({"temperature": ("time", [1.0, 2.0])})
    metadata = {
        "stages_applied": ["mapping", "finalization"],
        "unit_conversions": ["temperature: degC -> K"],
        "transformations": [
            {
                "handler": "example",
                "transformation": "example_transform",
                "description": "Example transformation.",
                "variables": ["temperature"],
            }
        ],
        "warnings": ["example warning"],
    }

    _write_processing_protocol(output_path, metadata, dataset, args, "convert")

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["command"] == "convert"
    assert payload["input_file"] == "input.cnv"
    assert payload["output_file"] == "out.nc"
    assert payload["pipeline_profile"] == "default"
    assert payload["default_latitude"] == 54.0
    assert payload["default_longitude"] == 10.0
    assert payload["stages_applied"] == ["mapping", "finalization"]
    assert payload["unit_conversions"] == {"temperature": ["degC -> K"]}
    assert payload["transformations"][0]["transformation"] == "example_transform"
    assert "temperature" in payload["data_variables"]


def test_show_writes_processing_protocol(tmp_path):
    output_path = tmp_path / "input.cnv.processing.protocol.json"

    dataset = xr.Dataset({"temperature": ("time", [1.0, 2.0])})
    metadata = {
        "stages_applied": ["mapping"],
        "warnings": ["example warning"],
    }

    class DummyIO:
        def read_data(self, *args, **kwargs):
            if kwargs.get("return_metadata"):
                return dataset, metadata
            return dataset

    args = argparse.Namespace(
        input="input.cnv",
        input_format=None,
        header_input=None,
        schema="summary",
        mapping=None,
        no_sanitize=False,
        raw_only=False,
        pipeline_profile=None,
        pipeline_file=None,
        pipeline_apply_stages=None,
        pipeline_skip_stages=None,
        pipeline_apply_handlers=None,
        pipeline_skip_handlers=None,
        default_latitude=None,
        default_longitude=None,
        metadata=None,
        metadata_file=None,
        processing_protocol=str(output_path),
    )

    cmd = ShowCommand(DummyIO())
    result = cmd.execute(args)

    assert result.success
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["command"] == "show"
    assert payload["input_file"] == "input.cnv"
    assert payload["stages_applied"] == ["mapping"]


def test_show_command_returns_errors_without_printing(capsys):
    class DummyIO:
        def read_data(self, *args, **kwargs):
            raise ValueError("reader failed")

    args = argparse.Namespace(
        input="input.cnv",
        input_format=None,
        header_input=None,
        schema="summary",
        mapping=None,
        no_sanitize=False,
        raw_only=False,
        pipeline_profile=None,
        pipeline_file=None,
        pipeline_apply_stages=None,
        pipeline_skip_stages=None,
        pipeline_apply_handlers=None,
        pipeline_skip_handlers=None,
        default_latitude=None,
        default_longitude=None,
        metadata=None,
        metadata_file=None,
        reader_args=None,
        processing_protocol=None,
    )

    result = ShowCommand(DummyIO()).execute(args)

    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err
    assert not result.success
    assert result.message == "reader failed"


def test_show_example_uses_bounded_xarray_preview(monkeypatch, capsys):
    dataset = xr.Dataset(
        {
            "vel": (
                ("dir", "range", "time"),
                np.arange(4 * 40 * 100).reshape(4, 40, 100),
            ),
            "temperature": ("time", np.arange(100)),
        },
        coords={
            "dir": ("dir", [1, 2, 3, 4]),
            "range": ("range", np.arange(40)),
            "time": ("time", np.arange(100)),
        },
    )

    def fail_to_dataframe(self, *args, **kwargs):
        raise AssertionError("show example must not materialize the full DataFrame")

    class DummyIO:
        def read_data(self, *args, **kwargs):
            return dataset

    monkeypatch.setattr(xr.Dataset, "to_dataframe", fail_to_dataframe)

    args = argparse.Namespace(
        input="large.nc",
        input_format=None,
        header_input=None,
        schema="example",
        mapping=None,
        no_sanitize=False,
        raw_only=False,
        pipeline_profile=None,
        pipeline_file=None,
        pipeline_apply_stages=None,
        pipeline_skip_stages=None,
        pipeline_apply_handlers=None,
        pipeline_skip_handlers=None,
        default_latitude=None,
        default_longitude=None,
        metadata=None,
        metadata_file=None,
        reader_args=None,
        processing_protocol=None,
    )

    result = ShowCommand(DummyIO()).execute(args)

    assert result.success
    output = capsys.readouterr().out
    assert "Example values" in output
    assert "vel [dir=1, range=0, time=0:5]" in output
    assert "temperature [time=0:5]" in output
