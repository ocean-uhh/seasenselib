SeaSenseLib Overview
====================

SeaSenseLib reads oceanographic sensor data from many instrument formats, standardizes it, and lets you convert or visualize it — all through a single, consistent interface built on `xarray <https://docs.xarray.dev/>`_ Datasets.

This page describes how the pieces fit together. For installation see :doc:`installation`, for the full list of formats see :doc:`supported_formats`, and for detailed signatures see :doc:`api_reference`.

Where it fits in a data workflow
--------------------------------

A typical SeaSenseLib workflow has three steps:

1. **Read** a raw instrument file into an xarray ``Dataset``. During reading, an optional processing *pipeline* normalizes variable names and units, derives parameters, and adds CF/ACDD-compliant metadata.
2. **Process** the Dataset further if needed — subset, resample, or compute statistics — using standard xarray operations or the built-in processors.
3. **Write** the Dataset to a standard format (NetCDF, CSV, Excel), or **plot** it (depth profile, time series, T-S diagram).

::

   raw instrument file
          │
          ▼
     ssl.read()  ──►  xarray.Dataset  ──►  ssl.write()  ──►  .nc / .csv / .xlsx
        (+ pipeline)        │
                            └──────────►  ssl.plot()   ──►  figure

A minimal example
-----------------

.. code-block:: python

   import seasenselib as ssl

   # Read a SeaBird CNV file. Format is auto-detected from the extension.
   ds = ssl.read("station001.cnv")

   # Inspect it — it is a standard xarray Dataset.
   print(ds)

   # Write it out as a CF-compliant NetCDF file.
   ssl.write(ds, "station001.nc", file_format="netcdf")

   # Or make a T-S diagram.
   ssl.plot("ts-diagram", ds, output_file="station001_ts.png")

When automatic format detection is not enough (ambiguous extensions such as ``.mat`` or ``.hex``), pass an explicit ``file_format`` key — see :doc:`supported_formats`.

The processing pipeline
-----------------------

By default, reading applies a processing pipeline that turns raw data into a standardized Level-1 dataset. You can choose how much processing to apply with the ``pipeline_profile`` argument:

.. code-block:: python

   ds = ssl.read("station001.cnv", pipeline_profile="minimal")  # mapping only
   ds = ssl.read("station001.cnv", pipeline_profile="default")  # conservative L1
   ds = ssl.read("station001.cnv", pipeline_profile="full")     # all stages

- ``minimal`` — variable-name mapping and finalization only.
- ``default`` — conservative Level-1 processing (no unit conversion).
- ``full`` — the complete Level-1 pipeline with all stages and handlers.

For raw, unprocessed data, use the CLI ``--raw-only`` flag or skip the pipeline stages you do not want. The pipeline is fully configurable; its stages, profiles, and public API are described in :doc:`user_guide` and :doc:`api_reference`.

Command-line interface
----------------------

Everything above is also available from the command line:

.. code-block:: bash

   seasenselib convert -i station001.cnv -o station001.nc
   seasenselib list readers

Run ``seasenselib --help`` to see all commands.
