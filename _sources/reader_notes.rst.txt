Reader Notes
============

This page documents reader-specific interpretation choices that affect the
scientific meaning of decoded variables. The supported formats overview stays
short; details live here when a raw format needs extra care.

RDI raw ADCP
------------

The ``rdi-raw`` reader decodes Teledyne RD Instruments ADCP raw binary files
with MHKiT DOLfYN and keeps the decoded ADCP vector structure intact.
SeaSenseLib then applies conservative mappings through the normal processing
pipeline, for example ``temp`` to ``temperature`` and ``c_sound`` to
``speed_of_sound`` when the decoded metadata supports that interpretation.

RDI variable-leader environmental fields may contain measured values,
configured values, or unused placeholder fields. SeaSenseLib inspects decoded
RDI fixed-leader sensor-source and sensor-available flags when they are
present. Manual or fallback values are kept under RDI-specific names, such as
``rdi_salinity_setting`` and ``rdi_temperature_setting``, so downstream
processing does not silently treat them as measurements.

The transducer-depth field is kept as ``rdi_transducer_depth`` because it
describes the ADCP head, not the depth coordinate of each velocity cell. A
pressure field containing only zeros is kept as ``rdi_pressure_placeholder``
rather than mapped to canonical ``pressure``.

RDI salinity values are represented with CF-style dimensionless units
``1e-3``. Decoder-provided units such as ``psu`` remain available as
``original_units`` when present.

Source annotations
^^^^^^^^^^^^^^^^^^

Variables get source annotations only when the reader has defensible evidence.
For environmental and orientation fields covered by the RDI fixed-leader flags
(``c_sound``, ``temp``, ``salinity``, ``depth``, ``heading``, ``pitch`` and
``roll``), SeaSenseLib stores compact attributes such as ``sensor_source`` and
``sensor_source_basis``. Raw RDI evidence remains available as
``rdi_sensor_source_flag`` and ``rdi_sensor_available_flag``.

These source annotations are SeaSenseLib terms, not external standard
vocabulary terms. Their definitions and the decoded RDI flag evidence are
stored in ``raw_metadata.blocks.sensor_sources``.

Velocity
^^^^^^^^

Velocity is preserved as vector variable ``vel``. If ``coord_sys`` is
``earth``, the vector components can be interpreted as east, north, up and
error velocity after review. For ``beam``, ``inst``, ``ship`` or
``principal`` data, splitting into CF east/north/up variables would require
coordinate rotation or deployment-specific interpretation, so the reader does
not do this automatically.

The reader does not add ``sensor_source`` to velocity or quality variables
such as ``amp``, ``corr`` or ``prcnt_gd`` because the RDI fixed-leader source
flags do not provide equivalent per-variable evidence for those fields.

