"""
Unit tests for the SubsetProcessor class in seasenselib.processors module.
"""

import unittest
import numpy as np
import pandas as pd
import xarray as xr

from seasenselib.processors import SubsetProcessor

class TestSubsetProcessor(unittest.TestCase):
    """Unit tests for the SubsetProcessor class."""

    def setUp(self):
        """Set up a dummy xarray dataset for testing."""

        # Create a dummy xarray dataset with a 'time' variable/coordinate
        # and with extra data variables for parameter slicing.
        times = pd.date_range("2020-01-01", periods=5, freq="h")
        self.dataset = xr.Dataset(
            {
                "time": ("time", times),
                "salinity": ("time", [30, 32, 34, 36, 38]),
                "depth": ("time", [100, 150, 200, 250, 300])
            }
        )

    def test_slice_by_sample_number_both(self):
        """Test slicing by sample indices."""

        # Slice using both sample indices.
        subsetter = SubsetProcessor(self.dataset)
        subsetter.set_sample_min(1)  # second sample
        subsetter.set_sample_max(3)  # fourth sample

        subset = subsetter.get_subset()
        # The __slice_by_sample_number method uses the time values at the given indices
        # to construct a slice label selection on the "time" variable.
        # With times [0, 1, 2, 3, 4] (as datetime values), a slice from times[1] to times[3]
        # should include times at 1, 2 and 3.
        expected_times = self.dataset["time"].values[1:4]
        np.testing.assert_array_equal(subset["time"].values, expected_times)

    def test_slice_by_time(self):
        """Test slicing by time boundaries."""

        # Slice using time boundaries.
        subsetter = SubsetProcessor(self.dataset)
        subsetter.set_time_min("2020-01-01T01:00:00")
        subsetter.set_time_max("2020-01-01T03:00:00")

        subset = subsetter.get_subset()
        # Use the same slice selection on the original dataset for expected results.
        expected = self.dataset.sel(time=slice(pd.Timestamp("2020-01-01T01:00:00"),
                                                 pd.Timestamp("2020-01-01T03:00:00")))
        np.testing.assert_array_equal(subset["time"].values, expected["time"].values)

    def test_slice_by_parameter_value(self):
        """Test slicing by a data variable's values."""

        # Slice the dataset based on a data variable's values.
        # The "salinity" values are [30, 32, 34, 36, 38]. 
        # We choose to keep values between 32 and 36.
        subsetter = SubsetProcessor(self.dataset)
        subsetter.set_parameter_name("salinity")
        subsetter.set_parameter_value_min(32)
        subsetter.set_parameter_value_max(36)

        subset = subsetter.get_subset()
        # Expected salinity values (and corresponding time values) are at indices 1, 2, 3.
        expected_salinity = np.array([32, 34, 36])
        np.testing.assert_array_equal(subset["salinity"].values, expected_salinity)

        expected_times = self.dataset["time"].values[1:4]
        np.testing.assert_array_equal(subset["time"].values, expected_times)

    def test_invalid_parameter_name(self):
        """Test setting an invalid parameter name."""

        # If a parameter name that is not a variable in the dataset is set,
        # a ValueError should be raised.
        subsetter = SubsetProcessor(self.dataset)
        with self.assertRaises(ValueError):
            subsetter.set_parameter_name("nonexistent")

if __name__ == "__main__":
    unittest.main()
