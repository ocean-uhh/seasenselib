"""
Unit tests for the SeaSenseLib public API.

These tests cover the main entry points that users interact with:
- ssl.read() - reading sensor data files
- ssl.write() - writing data to files  
- ssl.list_readers(), ssl.list_writers(), ssl.list_plotters() - discovery
- ssl.formats() - legacy format listing

This test suite provides high-impact coverage since API calls touch
most core modules (autodiscovery, factories, readers, writers).
"""

import unittest
import tempfile
import os
from pathlib import Path
import xarray as xr
import numpy as np
import pandas as pd

import seasenselib as ssl
from seasenselib.core.exceptions import ReaderError, WriterError, FormatDetectionError


class TestSeaSenseLibAPI(unittest.TestCase):
    """Test suite for SeaSenseLib public API functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Create minimal test dataset
        times = pd.date_range("2020-01-01", periods=3, freq="h")
        self.test_dataset = xr.Dataset({
            'time': ('time', times),
            'temperature': ('time', [15.1, 15.2, 15.3]),
            'salinity': ('time', [35.0, 35.1, 35.2]),
        })
        self.test_dataset.attrs['title'] = 'Test Dataset'
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_list_readers(self):
        """Test ssl.list_readers() function."""
        readers = ssl.list_readers()
        
        # Should return a list
        self.assertIsInstance(readers, list)
        self.assertGreater(len(readers), 0, "Should have at least one reader")
        
        # Each reader should be a dict with required keys
        for reader in readers:
            self.assertIsInstance(reader, dict)
            self.assertIn('key', reader)
            self.assertIn('name', reader)
            self.assertIn('class_name', reader)
            
            # Values should be non-empty strings
            self.assertIsInstance(reader['key'], str)
            self.assertIsInstance(reader['name'], str)
            self.assertIsInstance(reader['class_name'], str)
            self.assertTrue(reader['key'].strip())
            self.assertTrue(reader['name'].strip())
            self.assertTrue(reader['class_name'].strip())

    def test_list_writers(self):
        """Test ssl.list_writers() function."""
        writers = ssl.list_writers()
        
        # Should return a list
        self.assertIsInstance(writers, list)
        self.assertGreater(len(writers), 0, "Should have at least one writer")
        
        # Each writer should be a dict with required keys  
        for writer in writers:
            self.assertIsInstance(writer, dict)
            self.assertIn('key', writer)
            self.assertIn('name', writer)
            self.assertIn('class_name', writer)

    def test_list_plotters(self):
        """Test ssl.list_plotters() function."""
        plotters = ssl.list_plotters()
        
        # Should return a list
        self.assertIsInstance(plotters, list)
        self.assertGreater(len(plotters), 0, "Should have at least one plotter")
        
        # Each plotter should be a dict with required keys
        for plotter in plotters:
            self.assertIsInstance(plotter, dict)
            self.assertIn('key', plotter)
            self.assertIn('name', plotter) 
            self.assertIn('class_name', plotter)

    def test_list_all(self):
        """Test ssl.list_all() function."""
        all_resources = ssl.list_all()
        
        # Should return a dict with readers, writers, plotters
        self.assertIsInstance(all_resources, dict)
        self.assertIn('readers', all_resources)
        self.assertIn('writers', all_resources)
        self.assertIn('plotters', all_resources)
        
        # Each section should be a list
        self.assertIsInstance(all_resources['readers'], list)
        self.assertIsInstance(all_resources['writers'], list)
        self.assertIsInstance(all_resources['plotters'], list)

    def test_formats_legacy(self):
        """Test ssl.formats() legacy function."""
        formats = ssl.formats()
        
        # Should return a list of format dictionaries (not just strings)
        self.assertIsInstance(formats, list)
        self.assertGreater(len(formats), 0, "Should have at least one format")
        
        # Each format should be a dict with required keys
        for fmt in formats:
            self.assertIsInstance(fmt, dict)
            self.assertIn('key', fmt)
            self.assertIn('name', fmt)
            self.assertIn('class_name', fmt)

    def test_write_netcdf(self):
        """Test ssl.write() with NetCDF output."""
        output_file = os.path.join(self.temp_dir, "test_output.nc")
        
        # Write dataset to NetCDF
        ssl.write(self.test_dataset, output_file)
        
        # File should exist
        self.assertTrue(os.path.exists(output_file))
        
        # Should be readable as NetCDF
        read_back = xr.open_dataset(output_file)
        self.assertIn('temperature', read_back)
        self.assertIn('salinity', read_back)
        read_back.close()

    def test_write_csv(self):
        """Test ssl.write() with CSV output."""
        output_file = os.path.join(self.temp_dir, "test_output.csv")
        
        # Write dataset to CSV
        ssl.write(self.test_dataset, output_file)
        
        # File should exist  
        self.assertTrue(os.path.exists(output_file))
        
        # Should be readable as CSV
        import pandas as pd
        df = pd.read_csv(output_file)
        self.assertIn('temperature', df.columns)
        self.assertIn('salinity', df.columns)

    def test_write_with_explicit_format(self):
        """Test ssl.write() with explicit format specification."""
        output_file = os.path.join(self.temp_dir, "test_output.custom")
        
        # Write with explicit format (using file_format parameter)
        ssl.write(self.test_dataset, output_file, file_format='netcdf')
        
        # File should exist
        self.assertTrue(os.path.exists(output_file))

    def test_write_invalid_format(self):
        """Test ssl.write() with invalid format."""
        output_file = os.path.join(self.temp_dir, "test_output.unknown")
        
        # Should raise RuntimeError for unknown extension without format hint
        with self.assertRaises(RuntimeError):
            ssl.write(self.test_dataset, output_file)

    def test_read_nonexistent_file(self):
        """Test ssl.read() with nonexistent file."""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.cnv")
        
        # Should raise ReaderError for nonexistent file
        with self.assertRaises(ReaderError):
            ssl.read(nonexistent_file)

    def test_read_with_invalid_format_hint(self):
        """Test ssl.read() with invalid format hint."""
        # Create a dummy file
        dummy_file = os.path.join(self.temp_dir, "dummy.txt")
        with open(dummy_file, 'w') as f:
            f.write("dummy content")
        
        # Should raise FormatDetectionError for invalid format hint
        with self.assertRaises(FormatDetectionError):
            ssl.read(dummy_file, file_format="nonexistent-format")

    def test_readers_have_expected_formats(self):
        """Test that common expected readers are available."""
        readers = ssl.list_readers()
        reader_keys = [r['key'] for r in readers]
        
        # Should have some common readers (these exist based on the codebase analysis)
        expected_readers = ['sbe-cnv', 'netcdf']
        for expected in expected_readers:
            self.assertIn(expected, reader_keys, 
                         f"Expected reader '{expected}' not found in {reader_keys}")

    def test_writers_have_expected_formats(self):
        """Test that common expected writers are available."""
        writers = ssl.list_writers()
        writer_keys = [w['key'] for w in writers]
        
        # Should have some common writers
        expected_writers = ['netcdf', 'csv']
        for expected in expected_writers:
            self.assertIn(expected, writer_keys,
                         f"Expected writer '{expected}' not found in {writer_keys}")

    def test_round_trip_netcdf(self):
        """Test write then read round-trip with NetCDF."""
        # Write to NetCDF
        nc_file = os.path.join(self.temp_dir, "round_trip.nc")
        ssl.write(self.test_dataset, nc_file)
        
        # Read back
        read_dataset = ssl.read(nc_file)
        
        # Should be an xarray Dataset
        self.assertIsInstance(read_dataset, xr.Dataset)
        
        # Should have the same variables
        self.assertIn('temperature', read_dataset)
        self.assertIn('salinity', read_dataset)
        
        # Values should be approximately the same
        np.testing.assert_array_almost_equal(
            self.test_dataset['temperature'].values,
            read_dataset['temperature'].values
        )

    def test_api_functions_exist(self):
        """Test that all expected API functions exist."""
        # Main functions
        self.assertTrue(hasattr(ssl, 'read'))
        self.assertTrue(hasattr(ssl, 'write'))
        self.assertTrue(hasattr(ssl, 'plot'))
        
        # Discovery functions
        self.assertTrue(hasattr(ssl, 'list_readers'))
        self.assertTrue(hasattr(ssl, 'list_writers'))
        self.assertTrue(hasattr(ssl, 'list_plotters'))
        self.assertTrue(hasattr(ssl, 'list_all'))
        
        # Legacy function
        self.assertTrue(hasattr(ssl, 'formats'))
        
        # All should be callable
        self.assertTrue(callable(ssl.read))
        self.assertTrue(callable(ssl.write))
        self.assertTrue(callable(ssl.plot))
        self.assertTrue(callable(ssl.list_readers))
        self.assertTrue(callable(ssl.list_writers))
        self.assertTrue(callable(ssl.list_plotters))
        self.assertTrue(callable(ssl.list_all))
        self.assertTrue(callable(ssl.formats))


if __name__ == '__main__':
    unittest.main()