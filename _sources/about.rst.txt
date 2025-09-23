About SeaSenseLib
===============

SeaSenseLib is a Python library for reading, converting, and plotting oceanographic sensor data from various instruments and formats. The package is designed to work seamlessly with data from moored instruments and CTD profiles, supporting multiple file formats commonly used in oceanographic research.

**Key Features:**

* **Multiple Format Support**: Read data from Seabird CNV files, RBR RSK files, NetCDF, CSV, Nortek ASCII, and more
* **Flexible Data Processing**: Convert between formats, resample data, extract subsets, and calculate statistics
* **Rich Visualization**: Create T-S diagrams, vertical profiles, and time series plots
* **Command-Line Interface**: Easy-to-use CLI for common data processing tasks
* **Extensible Architecture**: Modular design allows easy addition of new readers, writers, and plotters
* **Parameter Mapping**: Handle different column naming conventions across file formats

**Supported Instruments:**

* Seabird CTD instruments (CNV format)
* RBR CTD and moored instruments (RSK format)
* Nortek ADCP instruments (ASCII format)
* Sea & Sun Technology instruments (TOB format)
* General CSV and NetCDF files

**Project Goals:**

SeaSenseLib aims to simplify the process of working with oceanographic sensor data by providing:

1. **Standardized Data Access**: Convert proprietary formats to standard xarray Datasets
2. **Consistent API**: Uniform interface across different instrument types
3. **CF Convention Support**: Ensure output data follows Climate and Forecast metadata conventions
4. **Research Reproducibility**: Enable easy sharing and reprocessing of oceanographic datasets
5. **Educational Use**: Provide tools suitable for teaching oceanographic data analysis

**Who Should Use SeaSenseLib:**

* Oceanographic researchers working with CTD and mooring data
* Students learning oceanographic data analysis
* Data managers converting legacy datasets
* Anyone needing to visualize or process oceanographic sensor data

**Community and Support:**

SeaSenseLib is developed and maintained by the oceanographic community. We welcome contributions, bug reports, and feature requests through our GitHub repository.