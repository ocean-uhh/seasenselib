Supported File Formats
======================

SeaSenseLib supports reading data from various oceanographic instruments and file formats. This page provides a complete reference of all supported format keys.

Format Keys Reference
--------------------

Format keys can be used with ``ssl.read(filename, file_format='key')`` when automatic detection fails or you need to override the default reader choice.

.. list-table:: Supported Oceanographic Instruments
   :header-rows: 1
   :widths: 15 15 15 20 35

   * - Manufacturer
     - Instrument
     - File Extensions
     - Format Key
     - Description
   * - Anderaa
     - RCM
     - ``.mat``
     - ``rcm-matlab``
     - RCM MATLAB export format
   * - Generic
     - CSV
     - ``.csv``
     - ``csv``
     - Comma-separated values format
   * - Generic
     - NetCDF
     - ``.nc``
     - ``netcdf``
     - Network Common Data Form (CF-compliant)
   * - Nortek
     - Aquadopp
     - ``.dat`` + ``.hdr``
     - ``nortek-ascii``
     - Nortek ASCII format (requires header file)
   * - RBR
     - Solo T
     - ``.rsk``
     - ``rbr-rsk``
     - RBR RSK native format (auto reader)
   * - RBR
     - Solo T
     - ``.rsk``
     - ``rbr-rsk-default``
     - RBR RSK default reader
   * - RBR
     - Solo T
     - ``.rsk``
     - ``rbr-rsk-legacy``
     - RBR RSK legacy format
   * - RBR
     - TR1050
     - ``.mat``
     - ``rbr-matlab``
     - RBR MATLAB export format
   * - RBR
     - TR1050
     - ``.mat``
     - ``rbr-matlab-legacy``
     - RBR MATLAB legacy format
   * - RBR
     - TR1050
     - ``.mat``
     - ``rbr-matlab-rsktools``
     - RBR MATLAB RSKtools export
   * - RBR
     - Various
     - ``.txt``, ``.dat``
     - ``rbr-ascii``
     - RBR ASCII format
   * - SeaBird
     - SBE37 MicroCAT
     - ``.cnv``
     - ``sbe-cnv``
     - SeaBird CNV format (time series)
   * - SeaBird
     - SBE 911
     - ``.cnv``
     - ``sbe-cnv``
     - SeaBird CNV format (CTD profiles)
   * - SeaBird
     - SBE16 Seacat
     - ``.cnv``
     - ``sbe-cnv``
     - SeaBird CNV format (CTD data)
   * - SeaBird
     - SBE56
     - ``.cnv``
     - ``sbe-cnv``
     - SeaBird CNV format (thermistor data)
   * - SeaBird
     - Various
     - ``.txt``, ``.dat``
     - ``sbe-ascii``
     - SeaBird ASCII format
   * - Sea & Sun
     - TOB
     - ``.tob``
     - ``seasun-tob``
     - Seasun TOB format
   * - Teledyne/RDI
     - ADCP
     - ``.mat``
     - ``adcp-matlab-uhhds``
     - ADCP MATLAB UHHDS format
   * - Teledyne/RDI
     - ADCP
     - ``.mat``
     - ``adcp-matlab-rdadcp``
     - ADCP MATLAB RDADCP format

Usage Examples
--------------

**Automatic Detection (Recommended):**

SeaSenseLib can automatically detect format for files with unique extensions:

.. code-block:: python

   import seasenselib as ssl
   
   # Automatic detection for unique extensions
   dataset = ssl.read('your_file.cnv')     # SeaBird CNV files
   dataset = ssl.read('logger_data.rsk')   # RBR RSK files (auto-selects modern/legacy)
   dataset = ssl.read('grid_data.nc')      # NetCDF files
   dataset = ssl.read('sensor_data.csv')   # CSV files
   dataset = ssl.read('tob_data.tob')      # Seasun TOB files

**Explicit Format Specification:**

.. code-block:: python

   # When automatic detection fails
   dataset = ssl.read('data.txt', file_format='sbe-ascii')
   
   # For ambiguous extensions like .mat
   rbr_data = ssl.read('logger_export.mat', file_format='rbr-matlab')
   adcp_data = ssl.read('current_data.mat', file_format='adcp-matlab-uhhds')

**Multi-file Formats:**

.. code-block:: python

   # Nortek instruments require both data and header files
   nortek_data = ssl.read('current_meter.dat',
                          file_format='nortek-ascii',
                          header_file='current_meter.hdr')

Format Detection Summary
------------------------

**Auto-detected formats** (unique file extensions):
   
- ``.cnv`` → ``sbe-cnv`` (SeaBird CNV files)
- ``.rsk`` → ``rbr-rsk`` (RBR RSK files - automatically selects modern/legacy reader)
- ``.nc`` → ``netcdf`` (NetCDF files)
- ``.csv`` → ``csv`` (CSV files)
- ``.tob`` → ``seasun-tob`` (Sea & Sun TOB files)

**Requires explicit format keys** (ambiguous extensions):

- ``.mat`` files: ``rbr-matlab``, ``rcm-matlab``, ``adcp-matlab-uhhds``, ``adcp-matlab-rdadcp``
- ``.txt/.dat`` files: ``rbr-ascii``, ``sbe-ascii``, ``nortek-ascii``
- Multi-file formats: ``nortek-ascii`` (requires both ``.dat`` and ``.hdr`` files)

When to Use Format Keys
-----------------------

Use explicit format specification when:

- Files have ambiguous extensions (e.g., ``.txt``, ``.dat``, ``.mat``)
- You need to override the default reader choice
- Working with multi-file formats like Nortek instruments
- Auto-detection fails for any reason

Checking Available Formats
---------------------------

Use the command line to see all available readers:

.. code-block:: bash

   seasenselib list readers

This will show you the current list of supported formats in your SeaSenseLib installation.