import pytest
import xarray as xr

import seasenselib.api as api


def test_read_accepts_pathlike_file_arguments(monkeypatch, tmp_path):
    captured = {}
    metadata_file = tmp_path / "metadata.json"
    metadata_file.write_text('{"global": {"title": "Path API test"}}', encoding="utf-8")

    class DummyIOManager:
        def read_data(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return xr.Dataset()

    monkeypatch.setattr(api, "DataIOManager", DummyIOManager)

    ds = api.read(
        tmp_path / "input.cnv",
        file_format="sbe-cnv",
        header_file=tmp_path / "input.hdr",
        metadata_file=metadata_file,
    )

    assert isinstance(ds, xr.Dataset)
    assert captured["args"][:3] == (
        str(tmp_path / "input.cnv"),
        "sbe-cnv",
        str(tmp_path / "input.hdr"),
    )
    assert captured["kwargs"]["user_metadata"]["global"]["title"] == "Path API test"


def test_read_accepts_pathlike_pipeline_file(monkeypatch, tmp_path):
    captured = {}

    class DummyIOManager:
        def read_data(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return xr.Dataset()

    monkeypatch.setattr(api, "DataIOManager", DummyIOManager)

    import seasenselib.pipeline as pipeline

    def fake_from_file(cls, filename):
        captured["pipeline_file"] = filename
        return cls()

    monkeypatch.setattr(
        pipeline.PipelineConfig,
        "from_file",
        classmethod(fake_from_file),
    )

    ds = api.read(tmp_path / "input.cnv", pipeline_file=tmp_path / "pipeline.json")

    assert isinstance(ds, xr.Dataset)
    assert captured["args"][0] == str(tmp_path / "input.cnv")
    assert captured["pipeline_file"] == str(tmp_path / "pipeline.json")


def test_write_accepts_pathlike_filename(monkeypatch, tmp_path):
    captured = {}
    ds = xr.Dataset()

    class DummyIOManager:
        def write_data(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(api, "DataIOManager", DummyIOManager)

    api.write(ds, tmp_path / "output.nc")

    assert captured["args"] == (ds, str(tmp_path / "output.nc"), None)
    assert captured["kwargs"] == {}


def test_plot_accepts_pathlike_output_file(monkeypatch, tmp_path):
    captured = {}
    ds = xr.Dataset()

    class DummyPlotter:
        def __init__(self, dataset):
            captured["dataset"] = dataset

        def plot(self, **kwargs):
            captured["plot_kwargs"] = kwargs

    class DummyDiscovery:
        def get_class_by_key(self, plotter_key):
            captured["plotter_key"] = plotter_key
            return DummyPlotter

    import seasenselib.core.autodiscovery as autodiscovery

    monkeypatch.setattr(autodiscovery, "PlotterDiscovery", DummyDiscovery)

    api.plot("dummy", ds, output_file=tmp_path / "plot.png")

    assert captured["plotter_key"] == "dummy"
    assert captured["dataset"] is ds
    assert captured["plot_kwargs"]["output_file"] == str(tmp_path / "plot.png")


def test_read_exposes_default_coordinates_to_pipeline(monkeypatch):
    captured = {}

    class DummyIOManager:
        def read_data(self, *args, **kwargs):
            captured.update(kwargs)
            return xr.Dataset()

    monkeypatch.setattr(api, "DataIOManager", DummyIOManager)

    ds = api.read(
        "input.cnv",
        default_latitude=54.0,
        default_longitude=10.0,
    )

    assert isinstance(ds, xr.Dataset)
    cfg = captured["pipeline_config"]
    derivation = next(stage for stage in cfg.pipeline if stage.name == "derivation")
    assert derivation.config["default_latitude"] == 54.0
    assert derivation.config["default_longitude"] == 10.0
    assert derivation.config["depth"] == {
        "use_default_latitude": True,
        "default_latitude": 54.0,
    }


def test_read_rejects_default_coordinates_without_pipeline():
    with pytest.raises(ValueError, match="default latitude/longitude"):
        api.read("input.cnv", use_steps=False, default_latitude=54.0)
