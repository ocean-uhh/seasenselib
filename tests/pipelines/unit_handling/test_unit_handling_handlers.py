import numpy as np
import pytest
import xarray as xr

from seasenselib.pipeline.unit_handling.handlers.unit_normalizer import UnitNormalizer
import seasenselib.pipeline.unit_handling.handlers.unit_converter as converter_mod


def test_unit_normalizer_basic_relabel():
    ds = xr.Dataset({"temperature": (["time"], [10.0, 11.0])})
    ds["temperature"].attrs["units"] = "degC"
    normalizer = UnitNormalizer(strict=False, auto_convert=True)

    result, issues, relabels = normalizer.normalize(ds)
    assert result["temperature"].attrs["units"] == "degC"
    assert issues == []
    assert relabels


def test_unit_normalizer_strict_missing_units():
    ds = xr.Dataset({"temperature": (["time"], [10.0, 11.0])})
    normalizer = UnitNormalizer(strict=True, auto_convert=False)
    with pytest.raises(ValueError):
        normalizer.normalize(ds)


def test_unit_normalizer_missing_units_non_strict():
    ds = xr.Dataset({"temperature": (["time"], [10.0, 11.0])})
    normalizer = UnitNormalizer(strict=False, auto_convert=False)
    _, issues, relabels = normalizer.normalize(ds)
    assert issues
    assert relabels == []


def test_unit_normalizer_mS_cm_relabel():
    """mS/cm → mS cm-1 via unit_normalizations lookup."""
    ds = xr.Dataset({"conductivity": (["time"], [32.0, 34.0])})
    ds["conductivity"].attrs["units"] = "mS/cm"
    normalizer = UnitNormalizer(strict=False, auto_convert=True)

    result, issues, relabels = normalizer.normalize(ds)
    assert result["conductivity"].attrs["units"] == "mS cm-1"
    assert any("mS/cm" in r for r in relabels)
    assert issues == []


def test_unit_normalizer_declared_vs_expected_mismatch():
    """Declared mS/cm against expected mS cm-1 issues a warning (not error) in non-strict mode."""
    ds = xr.Dataset({"conductivity": (["time"], [32.0, 34.0])})
    # Give it a unit that auto_convert won't touch but expected_units disagrees with
    ds["conductivity"].attrs["units"] = "mS cm-1"
    normalizer = UnitNormalizer(
        strict=False,
        auto_convert=True,
        expected_units={"conductivity": "S m-1"},  # deliberately wrong expected
    )

    with pytest.warns(UserWarning, match="conductivity"):
        _, issues, relabels = normalizer.normalize(ds)
    assert issues
    assert relabels == []


def test_unit_normalizer_declared_vs_expected_strict():
    """Declared unit that disagrees with expected raises ValueError in strict mode."""
    ds = xr.Dataset({"conductivity": (["time"], [32.0, 34.0])})
    ds["conductivity"].attrs["units"] = "mS cm-1"
    normalizer = UnitNormalizer(
        strict=True,
        auto_convert=True,
        expected_units={"conductivity": "S m-1"},
    )

    with pytest.raises(ValueError, match="conductivity"):
        normalizer.normalize(ds)


class TestConductivityNormalizer:
    from seasenselib.pipeline.unit_handling.handlers.conductivity_normalizer import (
        ConductivityNormalizer,
    )

    def _make_ds(self, values, units):
        ds = xr.Dataset({"conductivity": (["time"], np.array(values, dtype=float))})
        ds["conductivity"].attrs["units"] = units
        return ds

    def test_sm_converted_to_mscm(self):
        from seasenselib.pipeline.unit_handling.handlers.conductivity_normalizer import ConductivityNormalizer
        ds = self._make_ds([3.5, 4.0, 3.8], "S/m")
        result, norms = ConductivityNormalizer().normalize(ds)
        np.testing.assert_allclose(result["conductivity"].values, [35.0, 40.0, 38.0])
        assert result["conductivity"].attrs["units"] == "mS cm-1"
        assert norms

    def test_sm_space_notation_converted(self):
        from seasenselib.pipeline.unit_handling.handlers.conductivity_normalizer import ConductivityNormalizer
        ds = self._make_ds([3.5], "S m-1")
        result, norms = ConductivityNormalizer().normalize(ds)
        np.testing.assert_allclose(result["conductivity"].values, [35.0])
        assert result["conductivity"].attrs["units"] == "mS cm-1"

    def test_already_mscm_not_double_converted(self):
        from seasenselib.pipeline.unit_handling.handlers.conductivity_normalizer import ConductivityNormalizer
        ds = self._make_ds([35.0, 40.0], "mS cm-1")
        result, norms = ConductivityNormalizer().normalize(ds)
        np.testing.assert_allclose(result["conductivity"].values, [35.0, 40.0])
        assert norms == []

    def test_provenance_attr_set(self):
        from seasenselib.pipeline.unit_handling.handlers.conductivity_normalizer import ConductivityNormalizer
        ds = self._make_ds([3.5], "S/m")
        result, _ = ConductivityNormalizer().normalize(ds)
        assert result["conductivity"].attrs.get("conductivity_normalised_from") == "S/m"

    def test_non_conductivity_variable_untouched(self):
        from seasenselib.pipeline.unit_handling.handlers.conductivity_normalizer import ConductivityNormalizer
        ds = xr.Dataset({"temperature": (["time"], np.array([10.0]))})
        ds["temperature"].attrs["units"] = "S/m"  # absurd but should not be touched
        result, norms = ConductivityNormalizer().normalize(ds)
        assert result["temperature"].attrs["units"] == "S/m"
        assert norms == []


def test_unit_converter_no_units_no_conversion():
    ds = xr.Dataset({"temperature": (["time"], [10.0, 11.0])})
    converter = converter_mod.UnitConverter(expected_units={"temperature": "K"})
    result, conversions = converter.convert(ds)
    assert result is ds
    assert conversions == []


def test_unit_converter_with_pint_if_available():
    if not converter_mod._HAS_PINT:
        pytest.skip("pint not available")

    ds = xr.Dataset({"temperature": (["time"], np.array([0.0, 10.0]))})
    ds["temperature"].attrs["units"] = "degC"
    converter = converter_mod.UnitConverter(
        expected_units={"temperature": "K"},
        conversion_mode="duplicate_keep_original",
        original_suffix="_orig",
    )
    result, conversions = converter.convert(ds)

    assert "temperature_orig" in result
    assert result["temperature"].attrs["units"] == "K"
    assert result["temperature"].attrs.get("units_original") == "degC"
    assert conversions
