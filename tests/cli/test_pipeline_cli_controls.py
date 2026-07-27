import argparse
import ast
from pathlib import Path
import re

import pytest

from seasenselib.cli.commands.data_commands import (
    _build_reader_kwargs,
    _build_stage_kwargs,
    _build_writer_kwargs,
)
from seasenselib.cli.commands.info_commands import ListCommand
from seasenselib.cli.commands.plot_commands import PlotCommand
from seasenselib.cli.parser import ArgumentParser
from seasenselib.core.exceptions import ReaderError, ValidationError
from seasenselib.core.factories import ReaderFactory
from seasenselib.pipeline.config import PipelineConfig


def _base_args(**overrides):
    defaults = dict(
        raw_only=False,
        pipeline_profile=None,
        pipeline_file=None,
        pipeline_apply_stages=None,
        pipeline_skip_stages=None,
        pipeline_apply_handlers=None,
        pipeline_skip_handlers=None,
        default_latitude=None,
        default_longitude=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_build_stage_kwargs_profile():
    args = _base_args(pipeline_profile="default")
    stage_kwargs = _build_stage_kwargs(args)
    assert "pipeline_config" in stage_kwargs
    assert isinstance(stage_kwargs["pipeline_config"], PipelineConfig)
    assert stage_kwargs["pipeline_config"].global_config.get("profile") == "default"


def test_build_stage_kwargs_apply_stages():
    args = _base_args(pipeline_apply_stages="mapping,validation")
    stage_kwargs = _build_stage_kwargs(args)
    cfg = stage_kwargs["pipeline_config"]
    names = [stage.name for stage in cfg.pipeline]
    assert names == ["mapping", "validation"]


def test_build_stage_kwargs_skip_stages():
    args = _base_args(pipeline_skip_stages="validation")
    stage_kwargs = _build_stage_kwargs(args)
    cfg = stage_kwargs["pipeline_config"]
    names = [stage.name for stage in cfg.pipeline]
    assert names == [
        "mapping",
        "unit_handling",
        "transformation",
        "derivation",
        "metadata_extraction",
        "metadata_enrichment",
        "finalization",
    ]


def test_build_stage_kwargs_apply_handlers():
    args = _base_args(pipeline_apply_handlers="metadata_enrichment:cf")
    stage_kwargs = _build_stage_kwargs(args)
    cfg = stage_kwargs["pipeline_config"]
    stage = next(s for s in cfg.pipeline if s.name == "metadata_enrichment")
    assert stage.config.get("handlers") == ["cf"]


def test_build_stage_kwargs_raw_only_conflicts():
    args = _base_args(raw_only=True, pipeline_profile="default")
    with pytest.raises(ValueError):
        _build_stage_kwargs(args)


def test_build_stage_kwargs_default_latitude_patches_derivation():
    args = _base_args(default_latitude=54.0, default_longitude=10.0)
    stage_kwargs = _build_stage_kwargs(args)
    cfg = stage_kwargs["pipeline_config"]
    stage = next(s for s in cfg.pipeline if s.name == "derivation")

    assert stage.config["default_latitude"] == 54.0
    assert stage.config["default_longitude"] == 10.0
    assert stage.config["depth"] == {
        "use_default_latitude": True,
        "default_latitude": 54.0,
    }


def test_build_stage_kwargs_default_latitude_requires_derivation():
    args = _base_args(
        pipeline_skip_stages="derivation",
        default_latitude=54.0,
        default_longitude=10.0,
    )

    with pytest.raises(ValueError, match="derivation stage"):
        _build_stage_kwargs(args)


def test_build_stage_kwargs_default_coordinates_reject_nan():
    args = _base_args(default_latitude=float("nan"))

    with pytest.raises(ValueError, match="default_latitude"):
        _build_stage_kwargs(args)


def test_build_reader_kwargs_parses_reader_args():
    args = argparse.Namespace(
        no_sanitize=True,
        reader_args=[
            "latitude=30.5",
            "round_digits=10",
            "strict=false",
            "label=MAPR",
        ],
    )

    reader_kwargs = _build_reader_kwargs(args)

    assert reader_kwargs == {
        "_validate_reader_args": True,
        "sanitize_input": False,
        "latitude": 30.5,
        "round_digits": 10,
        "strict": False,
        "label": "MAPR",
    }


def test_build_reader_kwargs_does_not_send_reader_defaults_globally():
    args = argparse.Namespace(
        no_sanitize=False,
        reader_args=[],
    )

    assert _build_reader_kwargs(args) == {}


def test_build_reader_kwargs_rejects_invalid_reader_arg():
    args = argparse.Namespace(
        no_sanitize=False,
        reader_args=["round_digits"],
    )

    with pytest.raises(ValidationError):
        _build_reader_kwargs(args)


def test_build_writer_kwargs_uses_default_netcdf_name_sanitizing():
    args = argparse.Namespace(sanitize_netcdf_names=True)

    assert _build_writer_kwargs(args) == {}


def test_build_writer_kwargs_can_disable_netcdf_name_sanitizing():
    args = argparse.Namespace(sanitize_netcdf_names=False)

    assert _build_writer_kwargs(args) == {"sanitize_names": False}


def test_convert_parser_accepts_reader_arg():
    parser = ArgumentParser().create_command_parser("convert", lightweight=True)

    args = parser.parse_args([
        "-i", "file.LOG",
        "-f", "mapr-log",
        "-o", "out.nc",
        "-F", "netcdf",
        "--reader-arg", "latitude=30.0",
        "--reader-arg", "round_digits=10",
    ])

    assert args.reader_args == ["latitude=30.0", "round_digits=10"]


def test_convert_parser_sanitizes_netcdf_names_by_default():
    parser = ArgumentParser().create_command_parser("convert", lightweight=True)

    args = parser.parse_args([
        "-i", "file.cnv",
        "-f", "sbe-cnv",
        "-o", "out.nc",
        "-F", "netcdf",
    ])

    assert args.sanitize_netcdf_names is True


def test_convert_parser_accepts_no_sanitize_netcdf_names():
    parser = ArgumentParser().create_command_parser("convert", lightweight=True)

    args = parser.parse_args([
        "-i", "file.cnv",
        "-f", "sbe-cnv",
        "-o", "out.nc",
        "-F", "netcdf",
        "--no-sanitize-netcdf-names",
    ])

    assert args.sanitize_netcdf_names is False


def test_convert_parser_accepts_default_latitude():
    parser = ArgumentParser().create_command_parser("convert", lightweight=True)

    args = parser.parse_args([
        "-i", "file.cnv",
        "-f", "sbe-cnv",
        "-o", "out.nc",
        "-F", "netcdf",
        "--default-latitude", "54.0",
        "--default-longitude", "10.0",
    ])

    assert args.default_latitude == 54.0
    assert args.default_longitude == 10.0


def test_plot_parser_accepts_mapping_and_default_coordinates():
    parser = ArgumentParser().create_plot_parser_for_plotter("depth-profile")

    args = parser.parse_args([
        "-i", "file.cnv",
        "-m", "temperature=tv290C",
        "--default-latitude", "54.0",
        "--default-longitude", "10.0",
        "--reader-arg", "sanitize-input=false",
        "--processing-protocol",
    ])

    assert args.mapping == ["temperature=tv290C"]
    assert args.default_latitude == 54.0
    assert args.default_longitude == 10.0
    assert args.reader_args == ["sanitize-input=false"]
    assert args.processing_protocol is True


def test_plot_command_passes_processing_controls_to_reader(monkeypatch):
    captured = {}

    class FakeData:
        def __bool__(self):
            return True

    class FakeIO:
        def read_data(self, *args, **kwargs):
            captured["read_args"] = args
            captured["read_kwargs"] = kwargs
            return FakeData()

    class FakePlotter:
        def __init__(self, data):
            self.data = data

        def plot(self, **kwargs):
            captured["plot_kwargs"] = kwargs

    class FakeDiscovery:
        def get_class_by_key(self, key):
            return FakePlotter if key == "fake-plot" else None

    import seasenselib.core.autodiscovery as autodiscovery

    monkeypatch.setattr(autodiscovery, "PlotterDiscovery", FakeDiscovery)

    args = _base_args(
        plotter="fake-plot",
        input="file.cnv",
        input_format="sbe-cnv",
        header_input=None,
        output="plot.png",
        title=None,
        list_plotters=False,
        no_sanitize=False,
        reader_args=["sanitize-input=false"],
        mapping=["temperature=tv290C"],
        metadata=None,
        metadata_file=None,
        processing_protocol=None,
        default_latitude=54.0,
        default_longitude=10.0,
        dot_size=4,
        verbose=False,
        verbose_level=None,
        verbose_log=None,
    )

    result = PlotCommand(FakeIO()).execute(args)

    assert result.success
    read_kwargs = captured["read_kwargs"]
    assert read_kwargs["mapping"] == {"tv290C": "temperature"}
    assert read_kwargs["sanitize_input"] is False
    assert read_kwargs["_validate_reader_args"] is True

    cfg = read_kwargs["pipeline_config"]
    derivation = next(stage for stage in cfg.pipeline if stage.name == "derivation")
    assert derivation.config["default_latitude"] == 54.0
    assert derivation.config["default_longitude"] == 10.0
    assert derivation.config["depth"]["use_default_latitude"] is True

    assert captured["plot_kwargs"] == {
        "output_file": "plot.png",
        "dot_size": 4,
    }


def test_list_parser_accepts_reader_args_resource():
    parser = ArgumentParser().create_command_parser("list", lightweight=True)

    args = parser.parse_args([
        "reader-args",
        "--filter",
        "nortek-csv",
        "--sort",
        "reader",
    ])

    assert args.resource_type == "reader-args"
    assert args.filter == "nortek-csv"
    assert args.sort == "reader"


def test_reader_arg_help_points_to_discovery_command(capsys):
    parser = ArgumentParser().create_command_parser("convert", lightweight=True)

    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])

    output = capsys.readouterr().out
    assert "seasenselib list reader-args --filter FORMAT" in output
    assert "names are validated for the selected reader" in output
    assert re.search(r"(?<![\w-])--no-sanitize(?![\w-])", output) is None
    assert "--no-fix-coords" not in output


def test_list_reader_args_uses_reader_contract(monkeypatch):
    class FakeReader:
        @classmethod
        def format_key(cls):
            return "fake-format"

        @classmethod
        def format_name(cls):
            return "Fake Format"

        @classmethod
        def reader_args(cls):
            return [
                {
                    "name": "example_arg",
                    "cli_name": "example-arg",
                    "type": "int",
                    "default": 5,
                    "description": "Example reader option.",
                    "source": "declared",
                }
            ]

    class FakeDiscovery:
        def discover_classes(self):
            return {"FakeReader": FakeReader}

        def get_plugin_classes(self):
            return {}

    import seasenselib.core.autodiscovery as autodiscovery

    monkeypatch.setattr(autodiscovery, "ReaderDiscovery", FakeDiscovery)

    rows = ListCommand(None)._list_reader_args()

    assert rows == [
        {
            "reader": "fake-format",
            "reader_name": "Fake Format",
            "argument": "example_arg",
            "cli_name": "example-arg",
            "type": "int",
            "default": 5,
            "default_text": "5",
            "choices": [],
            "choices_text": "",
            "required": False,
            "description": "Example reader option.",
            "source": "declared",
            "class": "FakeReader",
            "is_plugin": False,
        }
    ]


def test_reader_args_table_uses_wrapped_help_style(capsys):
    args = argparse.Namespace(no_header=False, list_details=False)
    rows = [
        {
            "reader": "fake-format",
            "reader_name": "Fake Format",
            "argument": "example_arg",
            "cli_name": "example-arg",
            "type": "int",
            "default": 5,
            "default_text": "5",
            "choices": [],
            "choices_text": "",
            "required": False,
            "description": "Example reader option.",
            "source": "declared",
            "class": "FakeReader",
            "is_plugin": False,
        }
    ]

    ListCommand(None)._output_reader_args_table(rows, args)

    output = capsys.readouterr().out
    assert "Reader-specific arguments" in output
    assert "Use with: --reader-arg NAME=VALUE" in output
    assert "Fake Format (fake-format):" in output
    assert "  example-arg=INT" in output
    assert "Example reader option. (type: int; default: 5)" in output
    assert "+" not in output
    assert "|" not in output


def test_reader_factory_validates_cli_reader_kwargs():
    class FakeReader:
        @classmethod
        def format_key(cls):
            return "fake-format"

        @classmethod
        def reader_args(cls):
            return [
                {
                    "name": "encoding",
                    "cli_name": "encoding",
                    "type": "str",
                    "default": "latin-1",
                }
            ]

    ReaderFactory._validate_reader_kwargs(
        FakeReader,
        {"encoding": "utf-8", "mapping": {}},
        "fake-format",
    )

    with pytest.raises(ReaderError, match="Unsupported reader argument"):
        ReaderFactory._validate_reader_kwargs(
            FakeReader,
            {"time_dim": "other"},
            "fake-format",
        )


def test_sbe_cnv_reader_args_do_not_expose_default_latitude():
    path = Path(__file__).resolve().parents[2] / "seasenselib" / "readers" / "sbe_cnv_reader.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    reader_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SbeCnvReader"
    )
    reader_args = next(
        node for node in reader_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "reader_args"
    )
    arg_names = [
        call.args[0].value
        for call in ast.walk(reader_args)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "_reader_arg"
    ]

    assert arg_names == ["sanitize_input"]
