---
title: 'SeaSenseLib: An Extensible Library for Processing Oceanographic Sensor Data'
tags:
  - python
  - oceanography
  - marine science
  - sensor data
  - xarray
  - netcdf
  - cf-conventions
  - acdd
  - fair
authors:
  - name: Eleanor Frajka-Williams
    orcid: 0000-0001-8773-7838
    equal-contrib: true
    affiliation: 1
  - name: Yves Sorge
    orcid: 0009-0007-0043-9207
    equal-contrib: true
    affiliation: 1
affiliations:
 - name: Institute of Oceanography, University of Hamburg, Germany
   index: 1
   ror: 00g30e956
date: 26 April 2026
bibliography: paper.bib
---

# Summary

`SeaSenseLib` is a Python library for reading raw oceanographic sensor formats, then standardizing and re-exporting them in a common format.  It converts diverse inputs into CF/ACDD-compliant netCDF files with canonical variable names, normalized units and preserved raw metadata. Processing is deterministic and avoids scientific interpretation or quality control, ensuring reproducible, researcher-controlled downstream analysis. `SeaSenseLib` provides a unified I/O layer, a configurable pipeline model for data standardization, optional plotting functions, and an extensible plugin system for adding new readers, writers and processing components without modifying the core library. 


# Statement of need

Oceanographic research relies heavily on *in situ* observations from CTD instruments, moored platforms, and other systems. These instruments often record data in manufacturer- or instrument-specific formats (e.g., Sea-Bird `.hex` or `.cnv` or `.asc`, RBR `.rsk` or `.hex`, ADCP binary `.000`, Nortek Aquadopp `.aqd`) with inconsistent variable names and partially standardized units. As a result, researchers frequently maintain self-developed scripts tailored to individual datasets.  General libraries such as `xarray` [@Hoyer:2017] and `netCDF4` [@NetCDF:2026] offer powerful tools for handling multidimensional data, but they do not address the challenges of reading heterogeneous raw sensor formats or assigning standardized metadata.  `SeaSenseLib` fills this gap by providing a general-purpose and extensible solution for processing oceanographic sensor data from various instruments using a consistent interface. The library reads a variety of file formats and converts them into standardized `xarray` datasets, with support for CF Conventions (Climate and Forecast) [@CFConventions:2017] and ACDD metadata (Attribute Convention for Data Discovery) [@ACDD:2023]. The result is an analysis-ready representation of raw observations ("Level-1" -- metadata-enriched, standardized sensor datasets without quality control).  `SeaSenseLib` facilitates reproducible processing, interoperability, and long-term archiving, and supports community-driven expansion by using a plugin-based architecture in which new routines can be added without modifying the library’s code.


# State of the field

Existing open-source tools cover parts of this workflow.  Analysis-oriented packages come with readers attached: the R package `oce` [@Kelley:2022] offers extensive analysis functions alongside readers for common formats, and `ocean_data_tools` [@Ferris:2020] provides MATLAB routines for accessing selected data sources.  In both, format support exists to serve analysis, so neither provides a general cross-format harmonization of variables, units and metadata, nor a model for transforming heterogeneous raw structures into a common schema.  

Processing toolkits take the opposite approach and bundle conversion together with the science.  The Python package `stglib` [@Nowacki:2024] includes broad instrument support with established processing routines for time-series products, including QA/QC and wave-related outputs.  It requires the user to normalise formats at an earlier stage (e.g., convert MicroCAT data to `.asc`,  RBR to `.txt`, and ADCP to `.mat` using Velocity software).  Project-specific parsers such as `ocean-data-parser` [@CIOOS:2026] from the CIOOS ecosystem (Canadian Integrated Ocean Observing System) are written for particular formats and data sources from DFO but also some formats from RBR and Sea-Bird manufacturers.

`SeaSenseLib` is specifically engineered as an early stage standardization component that converts heterogeneous raw sensor files into deterministic, CF/ACDD-oriented Level-1 netCDF, with canonical variable mapping, unit normalization, and preserved provenance. It is a reusable building block that project-specific pipelines can embed, rather than an end-to-end processing stack.


# Software design

`SeaSenseLib` processes data in stages.  Instrument-specific readers convert raw files into xarray structures, using existing libraries such as `seabirdscientific` [@SeaBird:2026], `pycnv` [@Holtermann:2026] and `pyrsktools` [@RBR:2026] where available. A configurable pipeline then maps variables onto a canonical data model, combining user-defined rules, format-specific mappings, and more general fallbacks. This process allows very different input data to be converted into a common internal schema, which is necessary as identical physical quantities often are recorded under different names in different formats.

Readers extract metadata from file headers and instrument-specific information, and modular pipeline components adapt it to CF and ACDD conventions. Optionally, derivable physical quantities are then calculated (e.g., salinity) where the required inputs are present.  A validation step checks structure, units, and metadata, and the result is exported as standardized netCDF. A key design goal of the pipeline is transparent and reproducible data processing without embedded decisions, as those should remain under the researcher’s control. Provenance for the entire transformation can be recorded to ensure transparency and reproducibility.  For example, a Nortek velocity record configured in beam coordinates is transformed to earth coordinates using the instrument's beam-to-XYZ matrix and attitude record, with the source frame, the matrix, and the orientation convention all recorded alongside the result.

Extensibility is provided through Python entry points. External packages can register new readers, writers, convention handlers, derive functions, or plotters, which are detected at runtime. This design means that new instruments, formats and conventions can be added without modifying the library, and the design stays adaptable as those emerge.


# Research impact statement

`SeaSenseLib` is used in academic research workflows for processing oceanographic sensor data. Within the Experimental Oceanography group at the University of Hamburg it was used for datasets collected in the Denmark Strait under the DS-MIXSED project.  The mooring array there had over 100 instruments across six moorings, comprising RDI ADCPs, Sea-Bird MicroCATs, Nortek Aquadopps, and RBRsolo T, TR-1050 and RBRduet loggers. Several of those instrument types were from different generations, and so had different file formats -- the number of formats to be read exceeded the number of instrument types. 

`SeaSenseLib` serves as the input layer for `oceanarray` [@FrajkaWilliams:2026], a separate package that performs the onward processing of moored array observations: instrument-level quality control, time gridding, and vertical gridding onto pressure. The division is deliberate and illustrates the intended role. `SeaSenseLib` produces harmonized Level-1 datasets, and domain-specific pipelines consume them without reimplementing format handling; `oceanarray` reaches Sea-Bird, RBR, Nortek and RDI instruments through this layer instead of carrying readers of its own.

`SeaSenseLib` therefore provides a foundation for reproducible, FAIR-oriented data products suitable for both scientific analysis and long-term archiving.

Version 0.6.1 of the software, on which this article is based, has been archived and released for referencing [@SeaSenseLib:2026].

# Development history

`SeaSenseLib` began in June 2023 as `ctd-tools`, written after a North Sea field campaign to convert and visualize heterogeneous sensor data, initially for Sea-Bird and RBR formats. Work on historical mooring records (2006--2018) in 2024 showed that a wider range of moored instruments was needed, and that the original design would not extend that far. In 2025, dedicated funding supported that expansion, prompting the rename to `SeaSenseLib` and a refactoring onto the current plugin-based architecture.


# Acknowledgements

We acknowledge contributions from Isabelle Schmitz during the genesis of this project.  Parts of this work were supported by the European Union’s Horizon 2020 research and innovation programme under grant agreement No. 803140 (TERIFIC -- Targeted Experiment to Reconcile Increased Freshwater with Increased Convection).


# AI usage disclosure

AI-assisted tools (GitHub Copilot and Claude Sonnet 4.6) were used during code refactoring to modernize the implementation without altering the existing functionality. All outputs were reviewed, validated, and corrected by the authors.


# References

