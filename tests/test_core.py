"""
Unit tests for SeaSenseLib core modules.

These tests cover the core functionality that supports the API:
- Format detection and validation
- Reader and writer factories
- Autodiscovery system basics

These are high-impact tests since core modules are used by all other components.
"""

import unittest
import tempfile
import os
import xarray as xr
import pandas as pd

from seasenselib.core.autodiscovery import FormatDetector, ReaderDiscovery, WriterDiscovery
from seasenselib.core.factories import ReaderFactory, WriterFactory
from seasenselib.core.exceptions import FormatDetectionError, ReaderError, WriterError


class TestFormatDetector(unittest.TestCase):
    """Test suite for format detection functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_detect_format_cnv(self):
        """Test format detection for CNV files."""
        # Create a dummy CNV file
        cnv_file = os.path.join(self.temp_dir, "test.cnv")
        with open(cnv_file, 'w') as f:
            f.write("dummy cnv content")
        
        # Should detect sbe-cnv format
        format_key = FormatDetector.detect_format(cnv_file)
        self.assertEqual(format_key, "sbe-cnv")

    def test_detect_format_netcdf(self):
        """Test format detection for NetCDF files."""
        # Create a dummy NetCDF file
        nc_file = os.path.join(self.temp_dir, "test.nc")
        with open(nc_file, 'w') as f:
            f.write("dummy nc content")
        
        # Should detect netcdf format
        format_key = FormatDetector.detect_format(nc_file)
        self.assertEqual(format_key, "netcdf")

    def test_detect_format_with_hint(self):
        """Test format detection with explicit hint."""
        # Create a dummy file
        dummy_file = os.path.join(self.temp_dir, "test.xyz")
        with open(dummy_file, 'w') as f:
            f.write("dummy content")
        
        # Should use the hint
        format_key = FormatDetector.detect_format(dummy_file, format_hint="sbe-cnv")
        self.assertEqual(format_key, "sbe-cnv")

    def test_detect_format_invalid_hint(self):
        """Test format detection with invalid hint."""
        dummy_file = os.path.join(self.temp_dir, "test.xyz")
        with open(dummy_file, 'w') as f:
            f.write("dummy content")
        
        # Should raise error for invalid hint
        with self.assertRaises(FormatDetectionError):
            FormatDetector.detect_format(dummy_file, format_hint="nonexistent")

    def test_detect_format_nonexistent_file(self):
        """Test format detection with nonexistent file."""
        nonexistent = os.path.join(self.temp_dir, "nonexistent.cnv")
        
        # Should raise error for nonexistent file
        with self.assertRaises(FormatDetectionError):
            FormatDetector.detect_format(nonexistent)

    def test_detect_format_unknown_extension(self):
        """Test format detection with unknown extension."""
        unknown_file = os.path.join(self.temp_dir, "test.unknown")
        with open(unknown_file, 'w') as f:
            f.write("dummy content")
        
        # Should raise error for unknown extension
        with self.assertRaises(FormatDetectionError):
            FormatDetector.detect_format(unknown_file)

    def test_validate_output_format_netcdf(self):
        """Test output format validation for NetCDF."""
        nc_file = os.path.join(self.temp_dir, "output.nc")
        
        # Should validate netcdf format
        format_key = FormatDetector.validate_output_format(nc_file)
        self.assertEqual(format_key, "netcdf")

    def test_validate_output_format_csv(self):
        """Test output format validation for CSV."""
        csv_file = os.path.join(self.temp_dir, "output.csv")
        
        # Should validate csv format
        format_key = FormatDetector.validate_output_format(csv_file)
        self.assertEqual(format_key, "csv")

    def test_validate_output_format_with_hint(self):
        """Test output format validation with explicit hint."""
        custom_file = os.path.join(self.temp_dir, "output.custom")
        
        # Should use the hint
        format_key = FormatDetector.validate_output_format(custom_file, format_hint="netcdf")
        self.assertEqual(format_key, "netcdf")


class TestAutodiscovery(unittest.TestCase):
    """Test suite for autodiscovery functionality."""

    def test_reader_discovery_basic(self):
        """Test basic reader discovery functionality."""
        discovery = ReaderDiscovery()
        format_info = discovery.get_format_info()
        
        # Should find at least some readers
        self.assertIsInstance(format_info, list)
        self.assertGreater(len(format_info), 0)
        
        # Each entry should have required keys
        for info in format_info:
            self.assertIn('key', info)
            self.assertIn('name', info)
            self.assertIn('class_name', info)

    def test_writer_discovery_basic(self):
        """Test basic writer discovery functionality."""
        discovery = WriterDiscovery()
        format_info = discovery.get_format_info()
        
        # Should find at least some writers
        self.assertIsInstance(format_info, list)
        self.assertGreater(len(format_info), 0)
        
        # Each entry should have required keys
        for info in format_info:
            self.assertIn('key', info)
            self.assertIn('name', info)
            self.assertIn('class_name', info)

    def test_reader_discovery_by_format_key(self):
        """Test finding readers by format key."""
        discovery = ReaderDiscovery()
        
        # Should find sbe-cnv reader
        reader_class = discovery.get_reader_by_format_key("sbe-cnv")
        self.assertIsNotNone(reader_class)
        
        # Should return None for nonexistent format
        reader_class = discovery.get_reader_by_format_key("nonexistent-format")
        self.assertIsNone(reader_class)

    def test_writer_discovery_by_format_key(self):
        """Test finding writers by format key."""
        discovery = WriterDiscovery()
        
        # Should find netcdf writer
        writer_class = discovery.get_writer_by_format_key("netcdf")
        self.assertIsNotNone(writer_class)
        
        # Should return None for nonexistent format
        writer_class = discovery.get_writer_by_format_key("nonexistent-format")
        self.assertIsNone(writer_class)


class TestFactories(unittest.TestCase):
    """Test suite for factory functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create minimal test dataset for writer tests
        times = pd.date_range("2020-01-01", periods=3, freq="h")
        self.test_dataset = xr.Dataset({
            'time': ('time', times),
            'temperature': ('time', [15.1, 15.2, 15.3]),
        })

    def tearDown(self):
        """Clean up test files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_reader_factory_netcdf(self):
        """Test reader factory with NetCDF format."""
        factory = ReaderFactory()
        
        # Create a minimal netcdf file for testing
        nc_file = os.path.join(self.temp_dir, "test.nc")
        self.test_dataset.to_netcdf(nc_file)
        
        # Should create reader successfully
        reader = factory.create_reader("netcdf", nc_file)
        self.assertIsNotNone(reader)
        self.assertTrue(hasattr(reader, 'data'))

    def test_reader_factory_invalid_format(self):
        """Test reader factory with invalid format."""
        factory = ReaderFactory()
        dummy_file = os.path.join(self.temp_dir, "dummy.txt")
        
        with open(dummy_file, 'w') as f:
            f.write("dummy")
        
        # Should raise error for unknown format
        with self.assertRaises(ReaderError):
            factory.create_reader("nonexistent-format", dummy_file)

    def test_writer_factory_netcdf(self):
        """Test writer factory with NetCDF format."""
        factory = WriterFactory()
        
        # Should create writer successfully
        writer = factory.create_writer("netcdf", self.test_dataset)
        self.assertIsNotNone(writer)
        self.assertTrue(hasattr(writer, 'write'))

    def test_writer_factory_csv(self):
        """Test writer factory with CSV format."""
        factory = WriterFactory()
        
        # Should create writer successfully
        writer = factory.create_writer("csv", self.test_dataset)
        self.assertIsNotNone(writer)
        self.assertTrue(hasattr(writer, 'write'))

    def test_writer_factory_invalid_format(self):
        """Test writer factory with invalid format."""
        factory = WriterFactory()
        
        # Should raise error for unknown format
        with self.assertRaises(WriterError):
            factory.create_writer("nonexistent-format", self.test_dataset)

    def test_writer_factory_supported_formats(self):
        """Test getting supported formats from writer factory."""
        factory = WriterFactory()
        
        formats = factory.get_supported_formats()
        self.assertIsInstance(formats, list)
        self.assertGreater(len(formats), 0)
        
        # Should have common formats
        self.assertIn("netcdf", formats)
        self.assertIn("csv", formats)


if __name__ == '__main__':
    unittest.main()