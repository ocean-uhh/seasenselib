User Guide
==========

SeaSenseLib provides a simple, unified API for oceanographic data processing. This guide shows you how to read, process, and visualize data from various oceanographic instruments.  This guide covers the generalised API for working with the library.  

- For the legacy API, see the :ref:`developers_guide`.
- For a complete walkthrough with examples, see the `Demo Notebook <https://ocean-uhh.github.io/seasenselib/demo-output.html>`_.
- For a examples loading different moored instrument formats, see the `Mooring Demo Notebook <https://ocean-uhh.github.io/seasenselib/demo_mooring-output.html>`_.
- For a list of supported formats and instruments, see :doc:`supported_formats`.

Quick Start
-----------

**Basic Usage:**

.. code-block:: python

   import seasenselib as ssl

   # Read any supported format
   dataset = ssl.read("your_data_file.cnv")

   # Create plots
   ssl.plot('ts-diagram', dataset, title="T-S Diagram")
   ssl.plot('depth-profile', dataset, title="CTD Profile")

   # Export data
   ssl.write(dataset, 'output.nc')

Reading Data
------------

SeaSenseLib automatically detects file formats and converts data to standardized xarray Datasets:

.. code-block:: python

   import seasenselib as ssl

   # Automatic format detection
   ctd_data = ssl.read("profile.cnv")           # SeaBird CTD
   rbr_data = ssl.read("logger.rsk")            # RBR instruments  
   netcdf_data = ssl.read("data.nc")            # NetCDF files

   # Explicit format specification (when needed)
   nortek_data = ssl.read("current.dat", 
                         file_format='nortek-ascii',
                         header_file="current.hdr")

**Supported Formats:**

- **SeaBird**: CNV files from CTD casts and moorings
- **RBR**: RSK native format and MATLAB exports
- **Nortek**: Aquadopp current meter data
- **NetCDF**: CF-compliant oceanographic data
- **CSV**: Comma-separated sensor data
- **ADCP**: MATLAB format current profiler data

For a complete list of format keys and usage examples, see :doc:`supported_formats`.

Creating Plots
--------------

Generate standard oceanographic visualizations with simple commands:

**Temperature-Salinity Diagrams:**

.. code-block:: python

   ssl.plot('ts-diagram', dataset, title="Station T-S Diagram")
   ssl.plot('ts-diagram', dataset, output_file="ts_plot.png")

**Vertical Profiles:**

.. code-block:: python

   ssl.plot('depth-profile', dataset, title="CTD Cast")

**Time Series:**

.. code-block:: python

   # Single parameter
   ssl.plot('time-series', dataset, parameters=['temperature'])
   
   # Multiple parameters
   ssl.plot('time-series', dataset, 
            parameters=['temperature', 'salinity'],
            title="Mooring Data")

Exporting Data
--------------

Save processed data in various formats:

.. code-block:: python

   # NetCDF (recommended for oceanographic data)
   ssl.write(dataset, 'processed_data.nc')
   
   # CSV for spreadsheets
   ssl.write(dataset, 'data_export.csv')
   
   # Excel format
   ssl.write(dataset, 'report.xlsx')

Data Processing
---------------

SeaSenseLib includes basic processing tools:

.. code-block:: python

   from seasenselib.processors import SubsetProcessor, StatisticsProcessor

   # Extract data subsets
   subset = SubsetProcessor(dataset)
   shallow_data = subset.set_parameter_name('pressure').set_parameter_value_max(50).get_subset()
   
   # Calculate statistics
   stats = StatisticsProcessor(dataset, 'temperature')
   temperature_stats = stats.get_all_statistics()
   print(f"Mean temperature: {temperature_stats['mean']:.2f}°C")

Command Line Interface
----------------------

Use SeaSenseLib from the command line for common workflows:

.. code-block:: bash

   # Convert data formats
   seasenselib convert -i input.cnv -o output.nc
   
   # Show file information
   seasenselib show -i data_file.cnv
   
   # Create plots
   seasenselib plot ts-diagram -i data.nc -o ts_diagram.png
   seasenselib plot depth-profile -i data.nc -o profile.png
   seasenselib plot time-series -i data.nc -p temperature

   # List available formats
   seasenselib list readers

Working with Different Instruments
----------------------------------

**CTD Profile Data (SeaBird):**

.. code-block:: python

   # Read vertical cast data
   ctd_cast = ssl.read("station001.cnv")
   ssl.plot('depth-profile', ctd_cast, title="Station 001")
   ssl.plot('ts-diagram', ctd_cast, title="Water Mass Analysis")

**Moored Time Series (SeaBird MicroCAT):**

.. code-block:: python

   # Read mooring data
   mooring = ssl.read("microcat_series.cnv") 
   ssl.plot('time-series', mooring, 
            parameters=['temperature', 'salinity'],
            title="Mooring Time Series")

**RBR Temperature Loggers:**

.. code-block:: python

   # Native RSK format
   rbr_data = ssl.read("solo_logger.rsk")
   ssl.plot('time-series', rbr_data, parameters=['temperature'])
   
   # MATLAB export
   rbr_matlab = ssl.read("rbr_export.mat", file_format='rbr-matlab')

**Current Meter Data (Nortek):**

.. code-block:: python

   # Requires both data and header files
   current_data = ssl.read("aquadopp.dat",
                          file_format='nortek-ascii', 
                          header_file="aquadopp.hdr")
   ssl.plot('time-series', current_data, 
            parameters=['east_velocity', 'north_velocity'])


Getting Help
------------

- **Documentation**: Full API reference and examples at `https://ocean-uhh.github.io/seasenselib/ <https://ocean-uhh.github.io/seasenselib/>`_
- **Command help**: ``seasenselib --help`` or ``seasenselib <command> --help``
- **Supported formats**: ``seasenselib list readers``
- **Issues**: Report problems at `http://github.com/ocean-uhh/seasenselib/issues <http://github.com/ocean-uhh/seasenselib/issues>`_

For advanced usage, custom readers, or library extension, see the :doc:`developers_guide`.