Developers Guide
================

This guide provides detailed information about using SeaSenseLib for oceanographic data processing, including both modern and legacy APIs for users who need advanced control or are extending the library.

Quick Start (Simplified API)
----------------------------

SeaSenseLib provides a simple, unified API for common oceanographic data tasks:

**Using the Library in Python:**

.. code-block:: python

   import seasenselib as ssl

   # Read any supported format into an xarray dataset
   dataset = ssl.read("sea-practical-2023.cnv")

   # Create oceanographic plots
   ssl.plot('depth-profile', dataset, title="CTD Profile")
   ssl.plot('ts-diagram', dataset, title="T-S Diagram")
   ssl.plot('time-series', dataset, parameters=['temperature'])

   # Export to various formats
   ssl.write(dataset, 'output.nc')   # NetCDF
   ssl.write(dataset, 'output.csv')  # CSV

**Using the Command Line:**

.. code-block:: bash

   # Convert a CNV file to NetCDF
   seasenselib convert -i input.cnv -o output.nc

   # Show file summary
   seasenselib show -i input.cnv

   # Create plots with unified command
   seasenselib plot ts-diagram -i output.nc -o ts_diagram.png
   seasenselib plot depth-profile -i output.nc -o profile.png
   seasenselib plot time-series -i output.nc -p temperature

   # List available formats and plotters
   seasenselib list readers
   seasenselib list plotters

Modern API vs Legacy API
------------------------

SeaSenseLib offers two approaches: a modern unified API for simplicity and a legacy class-based API. Here, we keep the legacy version for reference, which may primarily be useful for users planning to extend the library.


**Modern API (Recommended for most users):**

.. code-block:: python

   import seasenselib as ssl
   
   # Simple, automatic format detection
   data = ssl.read('mooring_data.rsk')
   ssl.plot('time-series', data, parameters=['temperature'])
   ssl.write(data, 'output.nc')

**Legacy API:**

.. code-block:: python

   from seasenselib.readers import RbrRskReader
   from seasenselib.plotters import TimeSeriesPlotter
   from seasenselib.writers import NetCdfWriter
   
   # Explicit class instantiation and control
   reader = RbrRskReader('mooring_data.rsk')
   dataset = reader.get_data()
   
   plotter = TimeSeriesPlotter(dataset)
   plotter.plot(['temperature'], output_file='temp_series.png')
   
   writer = NetCdfWriter(dataset)
   writer.write('output.nc')

**Architecture Overview:**

The modern API (``ssl.read()``, ``ssl.plot()``, ``ssl.write()``) provides convenient wrappers around the underlying reader, plotter, and writer classes. When you call ``ssl.read()``, it:

1. Detects the file format automatically
2. Selects the appropriate reader class
3. Returns the standardized xarray Dataset

This gives you the simplicity of the modern API while maintaining access to the full power of the underlying architecture when needed.

Readers Overview
----------------

SeaSenseLib supports reading data from various oceanographic instruments and file formats. All readers convert instrument-specific data into standardized xarray Datasets for consistent data processing.

**Quick Example (Modern API):**

.. code-block:: python

   import seasenselib as ssl
   
   # Automatic format detection
   dataset = ssl.read("profile_001.cnv")
   
   # Explicit format specification
   dataset = ssl.read("mooring_data.rsk", file_format='rbr-rsk')
   
   # Multi-file formats (e.g., Nortek with header)
   dataset = ssl.read("current_data.dat", 
                     file_format='nortek-ascii', 
                     header_file="current_data.hdr")

**Advanced Usage (Legacy API):**

For users needing fine control over the reading process:

.. code-block:: python

   from seasenselib.readers import SbeCnvReader, RbrRskAutoReader
   
   # Direct class instantiation
   reader = SbeCnvReader("profile_001.cnv")
   dataset = reader.get_data()
   
   # Access reader-specific methods
   reader = RbrRskAutoReader("mooring_data.rsk")
   dataset = reader.get_data()

**SeaBird CTD Instruments**

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # CNV files (profiles and time series)
   profile_data = ssl.read("ctd_profile.cnv")
   timeseries_data = ssl.read("microcat_timeseries.cnv")
   
   # ASCII format
   ascii_data = ssl.read("sbe_data.asc", file_format='sbe-ascii')

*Legacy API:*

The ``SbeCnvReader`` handles SeaBird CNV files, commonly used for CTD profile data:

.. code-block:: python

   from seasenselib.readers import SbeCnvReader, SbeAsciiReader
   
   # CNV format reader
   reader = SbeCnvReader("profile_001.cnv")
   dataset = reader.get_data()
   
   # ASCII format reader
   reader = SbeAsciiReader("sbe_data.asc")
   dataset = reader.get_data()

**RBR Instruments**

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # Native RSK format (auto-detection)
   dataset = ssl.read("solo_temp.rsk")
   
   # MATLAB exports
   dataset = ssl.read("rbr_export.mat", file_format='rbr-matlab')
   dataset = ssl.read("rsktools_export.mat", file_format='rbr-matlab-rsktools')

*Legacy API:*

The ``RbrRskReader`` family handles RBR RSK files from moored instruments:

.. code-block:: python

   from seasenselib.readers import RbrRskAutoReader, RbrMatlabReader
   
   # Auto-detect RSK format version
   reader = RbrRskAutoReader("solo_temp.rsk")
   dataset = reader.get_data()
   
   # MATLAB format reader
   reader = RbrMatlabReader("rbr_export.mat")
   dataset = reader.get_data()

**Nortek Aquadopp Instruments**

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # Nortek ASCII format (requires both data and header files)
   dataset = ssl.read("aquadopp.dat", 
                     file_format='nortek-ascii',
                     header_file="aquadopp.hdr")

*Legacy API:*

.. code-block:: python

   from seasenselib.readers import NortekAsciiReader
   
   # Explicit file specification
   reader = NortekAsciiReader("aquadopp.dat", "aquadopp.hdr")
   dataset = reader.get_data()

**Standard Formats**

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # NetCDF files
   dataset = ssl.read("ocean_data.nc")
   
   # CSV files
   dataset = ssl.read("sensor_data.csv")

*Legacy API:*

For standard formats, use the general readers:

.. code-block:: python

   from seasenselib.readers import NetCdfReader, CsvReader
   
   # NetCDF reader
   reader = NetCdfReader("ocean_data.nc")
   dataset = reader.get_data()
   
   # CSV reader  
   reader = CsvReader("sensor_data.csv")
   dataset = reader.get_data()

**Parameter Mapping**

When instrument files use non-standard parameter names, you can map them to standard names:

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # Parameter mapping during read
   dataset = ssl.read("custom_names.cnv", mapping={
       'temperature': 'tv290C',
       'pressure': 'prdM',
       'salinity': 'sal00'
   })

*CLI mapping:*

.. code-block:: bash

   # CLI mapping example  
   seasenselib convert -i input.cnv -o output.nc -m temperature=tv290C pressure=prdM

*Legacy API:*

.. code-block:: python

   from seasenselib.readers import SbeCnvReader
   
   # Parameter mapping in constructor
   reader = SbeCnvReader("custom_names.cnv", mapping={
       'temperature': 'tv290C',
       'pressure': 'prdM',
       'salinity': 'sal00'
   })

Writers Overview
----------------

SeaSenseLib can export processed data to various formats for further analysis or sharing.

**Quick Example (Modern API):**

.. code-block:: python

   import seasenselib as ssl
   
   # Automatic format detection from extension
   ssl.write(dataset, 'output.nc')    # NetCDF
   ssl.write(dataset, 'output.csv')   # CSV
   ssl.write(dataset, 'output.xlsx')  # Excel

**Advanced Usage (Legacy API):**

For users needing fine control over export settings:

.. code-block:: python

   from seasenselib.writers import NetCdfWriter, CsvWriter
   
   # Custom NetCDF export
   writer = NetCdfWriter(dataset, global_attributes={
       'title': 'CTD Profile Station 001',
       'institution': 'University of Hamburg'
   })
   writer.write("output.nc")

**NetCDF Export**

NetCDF is the recommended format for oceanographic data as it preserves metadata and follows CF conventions.

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # Simple export
   ssl.write(dataset, 'output.nc')
   
   # Explicit format specification
   ssl.write(dataset, 'output.nc', file_format='netcdf')

*Legacy API:*

.. code-block:: python

   from seasenselib.writers import NetCdfWriter
   
   # Basic export
   writer = NetCdfWriter(dataset)
   writer.write("output.nc")
   
   # With custom global attributes
   writer = NetCdfWriter(dataset, global_attributes={
       'title': 'CTD Profile Station 001',
       'institution': 'University of Hamburg'
   })
   writer.write("output.nc")

**CSV Export**

Export to CSV for use in spreadsheet applications.

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # Simple CSV export
   ssl.write(dataset, 'output.csv')

*Legacy API:*

.. code-block:: python

   from seasenselib.writers import CsvWriter
   
   # Custom CSV export
   writer = CsvWriter(dataset)
   writer.write("output.csv")

**Excel Export**

Create Excel files.

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # Simple Excel export
   ssl.write(dataset, 'output.xlsx')

*Legacy API:*

.. code-block:: python

   from seasenselib.writers import ExcelWriter
   
   # Custom Excel export
   writer = ExcelWriter(dataset)
   writer.write("output.xlsx")

Plotters Overview
-----------------

SeaSenseLib provides specialized plotting tools for oceanographic data visualization.

**Quick Example (Modern API):**

.. code-block:: python

   import seasenselib as ssl
   
   # Create common oceanographic plots
   ssl.plot('ts-diagram', dataset, title="T-S Diagram")
   ssl.plot('depth-profile', dataset, title="CTD Profile")
   ssl.plot('time-series', dataset, parameters=['temperature'])
   
   # Save plots to files
   ssl.plot('ts-diagram', dataset, output_file="ts_diagram.png")

**Advanced Usage (Legacy API):**

For users needing fine control over plot customization:

.. code-block:: python

   from seasenselib.plotters import TsDiagramPlotter, TimeSeriesPlotter
   
   # Advanced customization
   plotter = TsDiagramPlotter(dataset)
   plotter.plot(title="Station 001", dot_size=50, show_density_isolines=False)

**Temperature-Salinity Diagrams**

T-S diagrams show the relationship between temperature and salinity with density isolines.

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # Simple T-S diagram
   ssl.plot('ts-diagram', dataset, title="Station 001 T-S Diagram")
   
   # Save to file
   ssl.plot('ts-diagram', dataset, output_file="ts_diagram.png")

*Legacy API:*

.. code-block:: python

   from seasenselib.plotters import TsDiagramPlotter
   
   plotter = TsDiagramPlotter(dataset)
   plotter.plot(title="Station 001 T-S Diagram")
   
   # Custom styling options
   plotter.plot(title="Custom T-S", dot_size=80, colormap='plasma', 
                show_density_isolines=True, output_file="ts_diagram.png")

**Vertical Profiles**

Display CTD casts as vertical profiles showing parameter variation with depth.

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # Standard depth profile
   ssl.plot('depth-profile', dataset, title="CTD Profile")

*Legacy API:*

.. code-block:: python

   from seasenselib.plotters import DepthProfilePlotter
   
   plotter = DepthProfilePlotter(dataset)
   plotter.plot(title="CTD Profile")
   
   # Customize displayed parameters
   plotter.plot(parameters=['temperature', 'salinity', 'oxygen'])

**Time Series**

Plot parameter evolution over time for moored data.

*Modern API:*

.. code-block:: python

   import seasenselib as ssl
   
   # Single parameter
   ssl.plot('time-series', dataset, parameters=['temperature'], 
            title="Temperature Time Series")
   
   # Multiple parameters
   ssl.plot('time-series', dataset, parameters=['temperature', 'salinity'],
            dual_axis=True, title="Multi-parameter Series")

*Legacy API:*

.. code-block:: python

   from seasenselib.plotters import TimeSeriesPlotter
   
   # Single parameter with customization
   plotter = TimeSeriesPlotter(dataset)
   plotter.plot(['temperature'], title="Temperature Time Series", 
                colors=['red'], line_styles=['--'])
   
   # Multiple parameters with dual axis
   plotter.plot(['temperature', 'salinity'], dual_axis=True,
                left_params=['temperature'], right_params=['salinity'])

Data Processing
---------------

**Subsetting Data**

Extract specific time periods or depth ranges:

.. code-block:: python

   from seasenselib.processors import SubsetProcessor
   
   # Time subset
   processor = SubsetProcessor(dataset)
   subset = processor.subset_time('2023-01-01', '2023-01-31')
   
   # Depth subset
   depth_subset = processor.subset_depth(10, 100)  # 10-100m depth

**Resampling**

Change the temporal resolution of time series data:

.. code-block:: python

   from seasenselib.processors import ResampleProcessor
   
   processor = ResampleProcessor(dataset)
   hourly_data = processor.resample('1H', method='mean')

**Statistics**

Calculate statistics for your data:

.. code-block:: python

   from seasenselib.processors import StatisticsProcessor
   
   processor = StatisticsProcessor(dataset)
   stats = processor.calculate_statistics(['temperature', 'salinity'])

Command Line Usage
------------------

SeaSenseLib provides a command-line interface for common tasks:

**Format Information**

.. code-block:: bash

   # List supported formats
   seasenselib formats

**Data Conversion**

.. code-block:: bash

   # Convert CNV to NetCDF
   seasenselib convert -i input.cnv -o output.nc
   
   # Convert with parameter mapping
   seasenselib convert -i input.cnv -o output.nc -m temperature=tv290C pressure=prdM
   
   # Convert to CSV
   seasenselib convert -i input.nc -o output.csv

**Data Inspection**

.. code-block:: bash

   # Show file summary
   seasenselib show -i data.nc
   
   # Show specific format
   seasenselib show -i data.cnv

**Plotting (Modern Commands)**

.. code-block:: bash

   # Create T-S diagram
   seasenselib plot ts-diagram -i data.nc -o ts_diagram.png
   
   # Create vertical profile
   seasenselib plot depth-profile -i data.nc -o profile.png
   
   # Create time series
   seasenselib plot time-series -i data.nc -p temperature -o temp_series.png
   
   # Multiple parameters with dual axis
   seasenselib plot time-series -i data.nc -p temperature salinity --dual-axis

**Plotting (Legacy Commands - Deprecated)**

.. code-block:: bash

   # Legacy commands (still supported but deprecated)
   seasenselib plot-ts -i data.nc -o ts_diagram.png
   seasenselib plot-profile -i data.nc -o profile.png
   seasenselib plot-series -i data.nc -p temperature -o temp_series.png

Format Key Reference
--------------------

For a complete list of all supported file formats and their format keys, see :doc:`supported_formats`.

Format keys are used with ``ssl.read(filename, file_format='key')`` when automatic detection fails or you need to override the default reader choice.

Troubleshooting and Migration
-----------------------------

**When to Use Explicit Format Keys**

Use explicit format specification when:

- Automatic detection fails
- You have files with extensions that do not map one-to-one with a reader (e.g., *.mat or *.dat) 
- You need to override the default reader choice

.. code-block:: python

   # Force specific format
   dataset = ssl.read("data.txt", file_format='sbe-ascii')

**Accessing Legacy Functionality**

The legacy API provides access to all reader/writer/plotter options:

.. code-block:: python

   from seasenselib.readers import SbeCnvReader
   
   # Access reader-specific validation methods
   reader = SbeCnvReader("data.cnv")
   reader.validate_format()  # Reader-specific method
   dataset = reader.get_data()

**Migration from Legacy to Modern API**

.. code-block:: python

   # Legacy approach
   from seasenselib.readers import SbeCnvReader
   from seasenselib.writers import NetCdfWriter
   from seasenselib.plotters import TsDiagramPlotter
   
   reader = SbeCnvReader("data.cnv")
   dataset = reader.get_data()
   writer = NetCdfWriter(dataset)
   writer.write("output.nc")
   plotter = TsDiagramPlotter(dataset)
   plotter.plot(title="T-S Diagram")

   # Modern equivalent
   import seasenselib as ssl
   
   dataset = ssl.read("data.cnv")
   ssl.write(dataset, "output.nc")
   ssl.plot('ts-diagram', dataset, title="T-S Diagram")

Working with Examples
---------------------

The SeaSenseLib repository includes example data files in the ``examples/`` directory covering multiple instrument types:

**CTD Profile Data:**
* ``sea-practical-2023.cnv``: SeaBird CTD vertical profile
* ``MSM121_054_1db.cnv``: Research cruise CTD data

**Time Series Data:**
* ``denmark-strait-ds-m1-17.cnv``: SeaBird MicroCAT mooring data

**Multi-instrument Dataset:**
* ``DSC18_477102.*``: Nortek Aquadopp files (dat, hdr, aqd, dia)
* ``DSE18_101647_20180827_1551.rsk``: RBR Solo T logger
* ``DSE18_013889_20180827_1349.mat``: RBR TR1050 MATLAB export
* ``DSE18_SBE05608482_2018_08_27.cnv``: SeaBird SBE56 thermistor

These files let you test the data processing with different file formats.