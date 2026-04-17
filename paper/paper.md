---
title: 'SeaSenseLib: An extensible library for processing oceanographic sensor data'
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

`SeaSenseLib` is a Python library for reading, standardizing, and exporting heterogenous raw oceanographic sensor formats. It converts format-specific inputs into CF/ACDD-compliant netCDF files with canonical variable names, normalized units and preserved raw metadata. Processing is deterministic and deliberately avoids scientific interpretation or quality control, ensuring reproducible, researcher-controlled downstream analysis. `SeaSenseLib` provides a unified I/O layer, a configurable pipeline model for data standardization, optional plotting functions, and an extensible plugin system for adding new readers, writers and processing components without modifying the core library. 


# Statement of need

Oceanographic research relies heavily on in-situ observations from CTD instruments, moored platforms, and other systems. These instruments often record data in manufacturer- or instrument-specific formats (e.g., Sea-Bird `.cnv`, RBR `.rsk`) with inconsistent variable names, partially standardized units, and heterogeneous metadata quality. As a result, researchers frequently maintain self-developed scripts tailored to individual datasets, which increases maintenance burden, reduces reproducibility, and complicates sharing as well as long-term reuse. 

While general libraries such as `xarray` [@Hoyer:2017] and `netCDF4` [@NetCDF:2026] offer powerful tools for working with multidimensional data but do not address the challenges of converting heterogeneous raw sensor formats or standardized metadata for interoperable Level-1 data products. In this context, “Level-1” refers to metadata-enriched, standardized sensor datasets that have not yet undergone scientific interpretation or advanced quality control.

`SeaSenseLib` fills this gap by providing a general-purpose and extensible solution for processing oceanographic sensor data from various instruments using a consistent and unified interface. The library reads various file formats and converts them into standardized `xarray` datasets, enabling uniform data processing, preparation, and visualization independent of the original instrument source, with built-in support for CF Conventions (Climate and Forecast) [@CFConventions:2017] and ACDD metadata (Attribute Convention for Data Discovery) [@ACDD:2023]. The result is an analysis-ready representation of raw observations that facilitates reproducible processing, interoperability, and long-term archiving, while creating FAIR-compliant data products and supporting community-driven expansion by using a plugin-based architecture in which new routines can be added without modifying the library’s code.


# State of Field

Various open-source tools already support specific components of the oceanographic data workflow, but they address only parts of the overall problem. The R package `oce` [@TODO:2026], for example,  offers extensive analysis functions and readers for some common formats, but focuses on data analysis rather than on a generic, cross-format harmonization of variables, units, and metadata. `OceanDataTools.jl` [@TODO:2026] provides readers and tools in Julia for accessing selected data sources, but does not follow a conceptual model to transform heterogeneous raw data structures into a standardized, declarative data model. Both tools primarily address analysis or format-specific data access, but not the reproducible transformation and standardization of heterogeneous input data.

`stglib` [@TODO:2026] is a widely used Python toolkit with broad instrument support and established processing scripts for oceanographic time-series products, including QA/QC controls and wave-related outputs. Architecturally, this solution integrates raw-format conversion with substantial downstream processing routines in a single toolkit, with strengths in operational breadth and instrument-oriented processing pathways.

In addition to these general-purpose tools, there are project-specific parsers such as the `ocean-data-parser` [@TODO:2026] from the CIOOS ecosystem, which are technically valuable but were each developed for specific formats or data sources and do not offer a generally extensible metadata layer, a configurable standard workflow, or a plugin-based extension model.

`SeaSenseLib` differs from these approaches primary in design focus: it is engineered as an early, modular standardization component that converts heterogeneous raw sensor files into deterministic, metadata-harmonized Level-1 netCDF datasets (CF/ACDD-oriented), with canonical variable mapping, unit normalization, and preserved provenance. With support for multiple formats and plugin-based extensibility, SeaSenseLib is designed as a reusable building block that can be embedded into project-specific processing pipelines and workflow engines across diverse institutional contexts, rather than prescribing one end-to-end processing stack.


# Design and approach

`SeaSenseLib` follows a multi-stage processing architecture. First, instrument-specific readers convert raw data into an xarray data structure, using existing libraries such as `pycnv` [@TODO:2026] and `pyrsktools` [@TODO:2026] where available. Data then passes through a configurable pipeline to be converted to a canonical data model through the harmonization of variable names. To achieve this, user-defined rules, format-specific mappings, and more general fallback-based mappings are combined. This process allows very different input data to be converted into a common internal schema, which is necessary as identical physical quantities often are recorded in different formats under different names.

Metadata is extracted by instrument-specific readers from file headers, variable attributes, as well as instrument-specific information, and is adapted to CF and ACDD conventions via the internal pipeline using modular components. Derivable physical quantities are then calculated, if the parameters needed are available. A validation unit checks structure, units, and metadata before data is exported as standardized netCDF files. A key design goal of the pipeline is transparent and reproducible data processing without embedded decisions, as those should remain under the researcher’s control. Provenance for the entire transformation can be recorded to ensure transparency and reproducibility.

Extensibility is provided through Python entry points. External packages can register new readers, writers, convention handlers, derive functions, or plotters, which are automatically detected at runtime. This design enables long-term adaptability as new instruments, formats, and conventions emerge. In summary, the functionality includes the import of heterogeneous sensor data formats, their transformation into a standardized internal data model, convention-based metadata enrichment, and export to standardized output formats.

`SeaSenseLib` is intentionally designed as a modular component rather than an all-in-one processing suite. Its primary responsibility is deterministic conversion and standardization of heterogeneous raw sensor formats into harmonized Level-1 netCDF datasets. Workflow orchestration is deliberately out of scope and can be handled by specialized pipeline/workflow engines, enabling clean separation of responsibilities and easier integration into diverse research infrastructures.


# Research Impact Statement

`SeaSenseLib` has been adopted in academic research workflows for processing oceanographic sensor data. For example, it has been used within the Experimental Oceanography research group at the University of Hamburg for datasets collected in the Denmark Strait as part of the EPOC project [@TODO:2026]. Users report reduced preprocessing effort and improved consistency of derived Level-1 datasets.  

The combination of an extensible design, a focus on CF and ACDD conventions, and integration into the Python ecosystem makes `SeaSenseLib` well suitable for data-intensive projects involving moored observations, CTD profiling, and data analysis workflows. The software thus provides a foundation for robust, reproducible, and FAIR-oriented data products suitable for both scientific analysis and long-term archiving. 

Version 0.5.0 of the software, on which this article is based, has been archived and released for referencing [@SeaSenseLib:2026].


# Development History

`SeaSenseLib` originated in June 2023 as a grassroots project under the name ctd-tools, developed following an oceanographic field campaign in the North Sea to support visualization and standardized conversion of heterogeneous sensor data. Early versions focused on Sea-Bird and RBR formats and were iteratively extended in response to practical research needs. 

In 2024, the library proved useful in a data recovery effort within the Experimental Oceanography group at the University of Hamburg, where it was used to harmonize historical mooring datasets (2006–2018), demonstrating its value for consistent long-term data processing. 

In 2025, supported by dedicated funding, the project was expanded beyond CTD-focused workflows to support a broader range of sensor types, leading to its renaming as `SeaSenseLib`. A subsequent refactoring introduced modular, plugin-based architecture, enabling extensibility across formats and research workflows.


# Acknowledgements

We acknowledge contributions from Isabelle Schmitz during the genesis of this project. 
Parts of this work were supported by the European Union’s Horizon 2020 research 
and innovation programme under grant agreement No. 803140 (TERIFIC – Targeted Experiment 
to Reconcile Increased Freshwater with Increased Convection).


# AI Usage Disclosure

AI-assisted tools (GitHub Copilot and Claude Sonnet 4.6) were used during code refactoring to modernize the implementation without altering the existing functionality. All outputs were reviewed, validated, and corrected by the authors.


# References

