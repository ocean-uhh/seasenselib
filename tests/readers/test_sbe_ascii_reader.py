"""Tests for SeaBird ASCII reader."""

import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from seasenselib.readers.sbe_ascii_reader import _extract_date, SbeAsciiReader

FIXTURES = Path(__file__).parent / "fixtures"
ASC_FIXTURE = FIXTURES / "4049_caldip_short.asc"


class TestExtractDate(unittest.TestCase):
    """Tests for supported datetime parsing patterns in `_extract_date`."""

    def test_extract_date_day_mon_year(self):
        result = _extract_date("30 Mar 2026 03:00:01")
        self.assertEqual(result, datetime(2026, 3, 30, 3, 0, 1))

    def test_extract_date_month_day_year_dash(self):
        result = _extract_date("03-30-2026 03:00:01")
        self.assertEqual(result, datetime(2026, 3, 30, 3, 0, 1))

    def test_extract_date_day_month_year_dash(self):
        result = _extract_date("30-03-2026 03:00:01")
        self.assertEqual(result, datetime(2026, 3, 30, 3, 0, 1))

    def test_extract_date_year_month_day_dash(self):
        result = _extract_date("2026-03-30 03:00:01")
        self.assertEqual(result, datetime(2026, 3, 30, 3, 0, 1))

    def test_extract_date_raises_for_invalid_string(self):
        with self.assertRaises(ValueError):
            _extract_date("not a valid datetime")


@pytest.mark.skipif(not ASC_FIXTURE.exists(), reason="fixture 4049_caldip_short.asc not present")
class TestSbeAsciiConductivityUnits:
    def test_conductivity_unit_is_sm_in_reader(self):
        """Reader reports the accurate format unit S/m; pipeline normalises to mS cm-1."""
        raw_ds = SbeAsciiReader(str(ASC_FIXTURE))._load_data()
        assert raw_ds["conductivity"].attrs["units"] == "S/m"

    def test_conductivity_values_in_sm_range(self):
        """Values should be in S/m range (~3–5) — no conversion in reader."""
        raw_ds = SbeAsciiReader(str(ASC_FIXTURE))._load_data()
        median_cond = float(np.median(raw_ds["conductivity"].values))
        assert 0.5 < median_cond < 10.0, (
            f"Expected conductivity in S/m range (0.5–10), got median {median_cond:.3f}"
        )

    def test_conductivity_unit_source_attr_present(self):
        raw_ds = SbeAsciiReader(str(ASC_FIXTURE))._load_data()
        assert "conductivity_unit_source" in raw_ds["conductivity"].attrs

    def test_conductivity_normalised_to_mS_cm_after_pipeline(self):
        """After the full pipeline, conductivity must be in mS cm-1."""
        ds = SbeAsciiReader(str(ASC_FIXTURE)).data
        assert ds["conductivity"].attrs["units"] == "mS cm-1"
        median_cond = float(np.median(ds["conductivity"].values))
        assert 20.0 < median_cond < 60.0, (
            f"Expected conductivity in mS cm-1 range (20–60) after pipeline, got {median_cond:.3f}"
        )

    def test_temperature_unit_not_unicode_degree_sign(self):
        """Reader must not set the Unicode '°C' string — it's not in any normalisation table."""
        reader = SbeAsciiReader(str(ASC_FIXTURE))
        raw_ds = reader._load_data()
        assert raw_ds["temperature"].attrs.get("units") != "°C", (
            "Reader still uses the Unicode degree sign, which is absent from unit_normalizations.json"
        )
