User Guide
==========

This guide provides detailed information about using CTD Tools for oceanographic data processing.

Quick Start
-----------

Here's a simple example to get you started with CTD Tools:

**Using the Library in Python:**

.. code-block:: python

   from ctd_tools.readers import SbeCnvReader, NetCdfReader
   from ctd_tools.writers import NetCdfWriter
   from ctd_tools.plotters import TimeSeriesPlotter

   # Read CTD data from CNV file
   reader = SbeCnvReader("sea-practical-2023.cnv")
   dataset = reader.get_data()

   # Write dataset to netCDF file
   writer = NetCdfWriter(dataset)
   writer.write('sea-practical-2023.nc')

   # Plot temperature time series
   plotter = TimeSeriesPlotter(dataset)
   plotter.plot(parameter_name='temperature')

**Using the Command Line:**

.. code-block:: bash

   # Convert a CNV file to NetCDF
   ctd-tools convert -i input.cnv -o output.nc

   # Show file summary
   ctd-tools show -i input.cnv

   # Plot a T-S diagram
   ctd-tools plot-ts -i output.nc

   # Plot a vertical profile
   ctd-tools plot-profile -i output.nc

   # Plot temperature time series
   ctd-tools plot-series -i output.nc -p temperature

Readers Overview
----------------

CTD Tools supports reading data from various oceanographic instruments and file formats. Each reader converts instrument-specific data into standardized xarray Datasets for consistent data processing.

**Seabird CTD Instruments**

The ``SbeCnvReader`` handles Seabird CNV files, which are commonly used for CTD profile data:

.. code-block:: python

   from ctd_tools.readers import SbeCnvReader
   
   # Read a CNV file
   reader = SbeCnvReader("profile_001.cnv")
   dataset = reader.get_data()
   
   # Access data variables
   temperature = dataset['temperature']
   salinity = dataset['salinity']
   pressure = dataset['pressure']

**Parameter Mapping**

Different instruments may use different column names for the same parameters. Use parameter mapping to standardize names:

.. code-block:: bash

   # CLI mapping example
   ctd-tools convert -i input.cnv -o output.nc -m temperature=tv290C pressure=prdM salinity=sal00

.. code-block:: python

   # Python mapping example
   reader = SbeCnvReader("input.cnv", parameter_mapping={
       'temperature': 'tv290C',
       'pressure': 'prdM', 
       'salinity': 'sal00'
   })

**RBR Instruments**

The ``RbrRskReader`` family handles RBR RSK files from moored instruments:

.. code-block:: python

   from ctd_tools.readers import RbrRskReader, RbrRskAutoReader
   
   # Auto-detect RSK format version
   reader = RbrRskAutoReader("mooring_data.rsk")
   dataset = reader.get_data()
   
   # Or use specific version
   reader = RbrRskReader("mooring_data.rsk")
   dataset = reader.get_data()

**NetCDF and CSV Files**

For standard formats, use the general readers:

.. code-block:: python

   from ctd_tools.readers import NetCdfReader, CsvReader
   
   # Read NetCDF files
   nc_reader = NetCdfReader("data.nc")
   dataset = nc_reader.get_data()
   
   # Read CSV files
   csv_reader = CsvReader("data.csv")
   dataset = csv_reader.get_data()

Writers Overview
----------------

CTD Tools can export processed data to various formats for further analysis or sharing.

**NetCDF Export**

NetCDF is the recommended format for oceanographic data as it preserves metadata and follows CF conventions:

.. code-block:: python

   from ctd_tools.writers import NetCdfWriter
   
   writer = NetCdfWriter(dataset)
   writer.write("output.nc")
   
   # With custom attributes
   writer = NetCdfWriter(dataset, global_attributes={
       'title': 'CTD Profile Station 001',
       'institution': 'University of Hamburg'
   })
   writer.write("output.nc")

**CSV Export**

Export to CSV for use in spreadsheet applications:

.. code-block:: python

   from ctd_tools.writers import CsvWriter
   
   writer = CsvWriter(dataset)
   writer.write("output.csv")

**Excel Export**

Create Excel files with multiple sheets:

.. code-block:: python

   from ctd_tools.writers import ExcelWriter
   
   writer = ExcelWriter(dataset)
   writer.write("output.xlsx")

Plotters Overview
-----------------

CTD Tools provides specialized plotting tools for oceanographic data visualization.

**Temperature-Salinity Diagrams**

T-S diagrams show the relationship between temperature and salinity with density isolines:

.. code-block:: python

   from ctd_tools.plotters import TsDiagramPlotter
   
   plotter = TsDiagramPlotter(dataset)
   plotter.plot(title="Station 001 T-S Diagram")
   
   # Save to file
   plotter.plot(output_file="ts_diagram.png")

**Vertical Profiles**

Display CTD casts as vertical profiles:

.. code-block:: python

   from ctd_tools.plotters import ProfilePlotter
   
   plotter = ProfilePlotter(dataset)
   plotter.plot(title="CTD Profile")
   
   # Customize parameters
   plotter.plot(parameters=['temperature', 'salinity', 'oxygen'])

**Time Series**

Plot parameter evolution over time for moored data:

.. code-block:: python

   from ctd_tools.plotters import TimeSeriesPlotter
   
   plotter = TimeSeriesPlotter(dataset)
   plotter.plot('temperature', title="Temperature Time Series")
   
   # Multiple parameters with dual axis
   from ctd_tools.plotters import TimeSeriesPlotterMulti
   
   multi_plotter = TimeSeriesPlotterMulti(dataset)
   multi_plotter.plot(['temperature', 'salinity'], dual_axis=True)

Data Processing
---------------

**Subsetting Data**

Extract specific time periods or depth ranges:

.. code-block:: python

   from ctd_tools.processors import SubsetProcessor
   
   # Time subset
   processor = SubsetProcessor(dataset)
   subset = processor.subset_time('2023-01-01', '2023-01-31')
   
   # Depth subset
   depth_subset = processor.subset_depth(10, 100)  # 10-100m depth

**Resampling**

Change the temporal resolution of time series data:

.. code-block:: python

   from ctd_tools.processors import ResampleProcessor
   
   processor = ResampleProcessor(dataset)
   hourly_data = processor.resample('1H', method='mean')

**Statistics**

Calculate statistics for your data:

.. code-block:: python

   from ctd_tools.processors import StatisticsProcessor
   
   processor = StatisticsProcessor(dataset)
   stats = processor.calculate_statistics(['temperature', 'salinity'])

Command Line Usage
------------------

CTD Tools provides a comprehensive command-line interface for common tasks:

**Format Information**

.. code-block:: bash

   # List supported formats
   ctd-tools formats

**Data Conversion**

.. code-block:: bash

   # Convert CNV to NetCDF
   ctd-tools convert -i input.cnv -o output.nc
   
   # Convert with parameter mapping
   ctd-tools convert -i input.cnv -o output.nc -m temperature=tv290C pressure=prdM
   
   # Convert to CSV
   ctd-tools convert -i input.nc -o output.csv

**Data Inspection**

.. code-block:: bash

   # Show file summary
   ctd-tools show -i data.nc
   
   # Show specific format
   ctd-tools show -i data.cnv

**Plotting**

.. code-block:: bash

   # Create T-S diagram
   ctd-tools plot-ts -i data.nc -o ts_diagram.png
   
   # Create vertical profile
   ctd-tools plot-profile -i data.nc -o profile.png
   
   # Create time series
   ctd-tools plot-series -i data.nc -p temperature -o temp_series.png
   
   # Multiple parameters with dual axis
   ctd-tools plot-series -i data.nc -p temperature salinity --dual-axis

Working with Examples
---------------------

The CTD Tools repository includes example data files in the ``examples/`` directory. These files demonstrate typical use cases:

* ``sea-practical-2023.cnv``: Vertical CTD profile data
* ``denmark-strait-ds-m1-17.cnv``: Time series from moored instrument

Use these files to test functionality and learn the data processing workflow.