import pytest
import xarray as xr

import seasenselib.api as api


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
