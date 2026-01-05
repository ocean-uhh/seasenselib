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
date: 26 January 2026
bibliography: paper.bib
---

# Summary



# Statement of need

Oceanographic research relies heavily on in-situ sensor data collected, for example, by CTD instruments and moored observation systems. However, this data is typically available in many different and proprietary formats, often with inconsistent parameter naming, limited metadata, and varying degrees of documentation. As a result, researchers often develop their own ad hoc scripts to process and analyze individual data sets, leading to extra work, reduced reproducibility, and barriers to data sharing and long-term reuse. While libraries such as `xarray` [@Hoyer:2017] and `netCDF4` [@NetCDF:2026] provide powerful tools for data analysis, they do not solve the challenges of dealing with heterogeneous raw sensor formats or harmonizing metadata across different instruments and sensors.

`SeaSenseLib` fills this gap by providing a general and extensible solution for processing oceanographic sensor data from various instruments using a consistent and uniform interface. The library reads and converts different file formats into standardized `xarray` datasets, enabling uniform data handling, processing, and visualization independent of the original instrument source. With built-in support for CF conventions and OceanSITES metadata, `SeaSenseLib` reduces the technical barriers for creating interoperable and FAIR (Findable, Accessible, Interoperable, Reusable) compliant data products suitable for archiving in marine data archives. Using a plugin-based architecture, individual new reading, writing, and plotting routines can be added without changing the libraries' code, supporting community-driven extension and long-term maintainability. `SeaSenseLib` thus meets the need for reproducible, standardized, and shareable workflows in oceanographic data processing.

# Design and Approach



# Functionality



# Acknowledgements

We acknowledge contributions from Isabelle Schmitz during the genesis of this project.


# References

