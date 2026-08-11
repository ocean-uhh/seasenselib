"""Tests for conductivity unit inference and conversion helper."""

import numpy as np
import pytest

from seasenselib.readers.utils.conductivity_units import infer_conductivity_unit, to_mS_cm


class TestInferConductivityUnit:
    def test_sm_range(self):
        values = np.array([3.2, 3.5, 3.8])
        assert infer_conductivity_unit(values) == "S/m"

    def test_mscm_range(self):
        values = np.array([32.0, 34.5, 38.0])
        assert infer_conductivity_unit(values) == "mS/cm"

    def test_uscm_range(self):
        values = np.array([32000.0, 34500.0, 38000.0])
        assert infer_conductivity_unit(values) == "uS/cm"

    def test_raises_out_of_range(self):
        values = np.array([0.3, 0.3, 0.3])
        with pytest.raises(ValueError, match="fits no known range"):
            infer_conductivity_unit(values)

    def test_raises_all_nan(self):
        values = np.array([np.nan, np.nan])
        with pytest.raises(ValueError, match="no finite values"):
            infer_conductivity_unit(values)

    def test_ignores_nan_in_otherwise_valid_array(self):
        values = np.array([3.2, np.nan, 3.5])
        assert infer_conductivity_unit(values) == "S/m"

    def test_matching_declared_no_warning(self, recwarn):
        values = np.array([3.2, 3.5])
        infer_conductivity_unit(values, declared="S/m")
        assert len(recwarn) == 0

    def test_mismatched_declared_warns(self):
        import warnings
        values = np.array([32.0, 34.0])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            infer_conductivity_unit(values, declared="S/m")
        assert any("mismatch" in str(warning.message).lower() for warning in w)

    def test_declared_cf_space_notation_alias(self):
        """S m-1 is an alias for S/m — no warning when values are in S/m range."""
        values = np.array([3.2, 3.5])
        result = infer_conductivity_unit(values, declared="S m-1")
        assert result == "S/m"

    def test_declared_mscm_cf_alias(self):
        values = np.array([32.0, 34.0])
        result = infer_conductivity_unit(values, declared="mS cm-1")
        assert result == "mS/cm"


class TestToMsCm:
    def test_from_sm(self):
        values = np.array([3.5, 4.0])
        converted, unit = to_mS_cm(values, "S/m")
        np.testing.assert_allclose(converted, [35.0, 40.0])
        assert unit == "mS cm-1"

    def test_from_sm_space_notation(self):
        values = np.array([3.5])
        converted, unit = to_mS_cm(values, "S m-1")
        np.testing.assert_allclose(converted, [35.0])
        assert unit == "mS cm-1"

    def test_from_mscm(self):
        values = np.array([35.0, 40.0])
        converted, unit = to_mS_cm(values, "mS/cm")
        np.testing.assert_allclose(converted, [35.0, 40.0])
        assert unit == "mS cm-1"

    def test_from_mscm_cf_notation(self):
        values = np.array([35.0])
        converted, unit = to_mS_cm(values, "mS cm-1")
        np.testing.assert_allclose(converted, [35.0])
        assert unit == "mS cm-1"

    def test_from_uscm(self):
        values = np.array([35000.0])
        converted, unit = to_mS_cm(values, "uS/cm")
        np.testing.assert_allclose(converted, [35.0])
        assert unit == "mS cm-1"

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError, match="Unrecognised"):
            to_mS_cm(np.array([3.5]), "kg m-3")
