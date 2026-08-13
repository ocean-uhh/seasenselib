API Reference
=============

This section provides detailed API documentation for all SeaSenseLib modules.

Top-Level API Functions
-----------------------

These convenience functions are the main entry points for most users and are available directly on the ``seasenselib`` package (commonly imported as ``ssl``).

.. autofunction:: seasenselib.read

.. autofunction:: seasenselib.write

.. autofunction:: seasenselib.plot

.. autofunction:: seasenselib.formats

.. autofunction:: seasenselib.list_readers

.. autofunction:: seasenselib.list_writers

.. autofunction:: seasenselib.list_plotters

.. autofunction:: seasenselib.list_parameters

.. autofunction:: seasenselib.list_all

Readers
-------

.. automodule:: seasenselib.readers
   :no-members:
   :show-inheritance:

Base Reader Classes
^^^^^^^^^^^^^^^^^^^

.. autoclass:: seasenselib.readers.base.AbstractReader
   :members:
   :undoc-members:
   :show-inheritance:

Specific Reader Classes
^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: seasenselib.readers.SbeCnvReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.NetCdfReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.CsvReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RbrRskReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RbrRskAutoReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RbrAsciiReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RbrHexReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.NortekAsciiReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.NortekCsvReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.NortekRawReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.AdcpMatlabRdadcpReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.AdcpMatlabUhhdsReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RdiRawReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RbrMatlabLegacyReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RbrMatlabReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RbrMatlabRsktoolsReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RbrRskLegacyReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.RcmMatlabReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.SbeAsciiReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.SeasunTobReader
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.readers.SbeHexReader
   :members:
   :undoc-members:
   :show-inheritance:

Writers
-------

.. automodule:: seasenselib.writers
   :no-members:
   :show-inheritance:

Base Writer Classes
^^^^^^^^^^^^^^^^^^^

.. autoclass:: seasenselib.writers.base.AbstractWriter
   :members:
   :undoc-members:
   :show-inheritance:

Specific Writer Classes
^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: seasenselib.writers.NetCdfWriter
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.writers.CsvWriter
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.writers.ExcelWriter
   :members:
   :undoc-members:
   :show-inheritance:

Plotters
--------

.. automodule:: seasenselib.plotters
   :no-members:
   :show-inheritance:

Base Plotter Classes
^^^^^^^^^^^^^^^^^^^^

.. autoclass:: seasenselib.plotters.base.AbstractPlotter
   :members:
   :undoc-members:
   :show-inheritance:

Specific Plotter Classes
^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: seasenselib.plotters.TsDiagramPlotter
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.plotters.DepthProfilePlotter
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.plotters.TimeSeriesPlotter
   :members:
   :undoc-members:
   :show-inheritance:

Processors
----------

.. automodule:: seasenselib.processors
   :no-members:
   :show-inheritance:

Base Processor Classes
^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: seasenselib.processors.base.AbstractProcessor
   :members:
   :undoc-members:
   :show-inheritance:

Specific Processor Classes
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: seasenselib.processors.SubsetProcessor
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.processors.ResampleProcessor
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.processors.StatisticsProcessor
   :members:
   :undoc-members:
   :show-inheritance:

Pipeline System
---------------

The Level-1 processing pipeline transforms raw data into standardized, CF/ACDD-compliant datasets through a sequence of configurable stages. See the :doc:`user_guide` for a conceptual overview; the classes and factory functions below make up its public API.

.. automodule:: seasenselib.pipeline
   :no-members:
   :show-inheritance:

.. autoclass:: seasenselib.pipeline.Pipeline
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.pipeline.Stage
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.pipeline.StageContext
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.pipeline.TransformationStage
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.pipeline.PipelineConfig
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.pipeline.StageConfig
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.pipeline.StageRegistry
   :members:
   :undoc-members:
   :show-inheritance:

.. autofunction:: seasenselib.pipeline.default_pipeline

.. autofunction:: seasenselib.pipeline.minimal_pipeline

.. autofunction:: seasenselib.pipeline.create_pipeline

.. autofunction:: seasenselib.pipeline.list_available_pipelines

Core Infrastructure
-------------------

Lower-level classes used by the readers, writers, and top-level API. Most users will not need these directly.

.. autoclass:: seasenselib.core.DataIOManager
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.core.FormatDetector
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.core.ReaderFactory
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: seasenselib.core.WriterFactory
   :members:
   :undoc-members:
   :show-inheritance:

Exceptions
^^^^^^^^^^

.. autoclass:: seasenselib.core.SeaSenseLibError
   :members:
   :show-inheritance:

.. autoclass:: seasenselib.core.FormatDetectionError
   :members:
   :show-inheritance:

.. autoclass:: seasenselib.core.DependencyError
   :members:
   :show-inheritance:

.. autoclass:: seasenselib.core.ValidationError
   :members:
   :show-inheritance:

Canonical Parameters
--------------------

``seasenselib.parameters`` defines the canonical (standardized) variable names used throughout SeaSenseLib — for example ``TEMPERATURE = 'temperature'`` and ``SALINITY = 'salinity'``. Reader mappings translate instrument-specific column names onto these canonical names.

To list the canonical parameters available at runtime, use the top-level helper:

.. code-block:: python

   import seasenselib as ssl
   ssl.list_parameters()
