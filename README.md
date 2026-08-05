<picture align="center" style="display: block; margin-bottom: 2em">
  <source media="(prefers-color-scheme: dark)" srcset="assets/images/banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/images/banner-light.svg">
  <img alt="SeaSenseLib Logo" src="assets/images/banner-light.svg" style="width:100%; max-width: 400px;">
</picture>

-----------------

# SeaSenseLib

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20044197.svg)](https://doi.org/10.5281/zenodo.20044197)
[![Available on pypi](https://img.shields.io/pypi/v/seasenselib.svg)](https://pypi.python.org/pypi/seasenselib/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-sphinx-blue)](https://ocean-uhh.github.io/seasenselib/)
[![CI - Test](https://github.com/ocean-uhh/seasenselib/actions/workflows/ci.yml/badge.svg)](https://github.com/ocean-uhh/seasenselib/actions/workflows/ci.yml)

SeaSenseLib is a library for reading and standardizing different raw oceanographic sensor formats. It converts format-specific inputs (e.g. Sea-Bird cnv, RBR rsk) into CF/ACDD-compatible Level-1 netCDF files with canonical variable names, normalized units and preserved raw metadata. Processing is deterministic and applies no scientific interpretation or quality control. SeaSenseLib provides a pipeline model, a unified I/O layer, and optional plotting utilities.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [How to Use SeaSenseLib](#how-to-use-seasenselib)
  - [Quick Start - Basic Workflow](#quick-start---basic-workflow)
  - [Working with Different Data Formats](#working-with-different-data-formats)
  - [Using Reader, Writer, and Plotter Classes Directly](#using-reader-writer-and-plotter-classes-directly)
- [CLI Usage](#cli-usage)
  - [Example Data](#example-data)
  - [Converting a File to netCDF](#converting-a-file-to-netcdf)
  - [Reader-Specific Options](#reader-specific-options)
  - [Parameter Mapping](#parameter-mapping)
  - [Metadata Enrichment](#metadata-enrichment)
  - [Pipeline Control](#pipeline-control)
  - [Showing a Data Summary](#showing-a-data-summary)
  - [Plotting Data](#plotting-data)
- [Extending SeaSenseLib with Plugins](#extending-seasenselib-with-plugins)
- [Development](#development)
- [Project Status](#project-status)
  - [Contributing](#contributing)
  - [License](#license)

## Features

- Decode multiple raw sensor formats into xarray / netCDF.
- Normalize variable names and units in a format-agnostic way.
- Preserve all raw metadata in an opaque container.
- Generate ACDD fields (title, summary, keywords) when absent.
- Plugin mechanism for adding additional formats.
- Optional plotting utilities for quick inspection.

## Installation

To install SeaSenseLib, we strongly recommend using a scientific Python distribution. 
If you already have Python, you can install SeaSenseLib with:

```bash
pip install seasenselib
```

Now you're ready to use the library.

## How to Use SeaSenseLib

SeaSenseLib is designed to make working with oceanographic data easy and intuitive, whether you're analyzing CTD profiles, processing mooring data, or creating publication-ready plots in Jupyter notebooks.

### Quick Start - Basic Workflow

The most common workflow: read sensor data, analyze it, create plots, and save results.

```python
import seasenselib as ssl

# 1. Read CTD data (auto-detects .cnv format)
ds = ssl.read("profile.cnv")

# 2. Quick data overview
print(ds)

# 3. Create plots
ssl.plot('time-series', ds, parameters=['temperature', 'salinity'])
ssl.plot('ts-diagram', ds) 

# 4. Save data as netCDF (auto-detects .nc format)
ssl.write(ds, 'profile.nc')
```

By default, SeaSenseLib runs the Level‑1 processing pipeline. Use the CLI flags below to apply/skip stages or handlers, or switch profiles.

### Working with Different Data Formats

SeaSenseLib supports different oceanographic instrument formats. Here's how to work with different formats by specifying the format or letting it auto-detect based on file extension:

```python
import seasenselib as ssl

# Seabird CTD data
sbe_data = ssl.read("station_001.cnv", file_format='sbe-cnv')

# RBR logger data  
rbr_data = ssl.read("temperature_logger.rsk", file_format='rbr-rsk')

# RDI raw ADCP data
adcp_data = ssl.read("DS2_2025_recovery.000", file_format='rdi-raw')

# See all supported readers
readers = ssl.list_readers()
for reader in readers:
    print(f"- {reader['key']:<20} : {reader['name']} ")

# Auto-detect format from file extension
data = ssl.read("myfile.cnv")  # Automatically detects 'sbe-cnv'
```

### Using Reader, Writer, and Plotter Classes Directly

Example code for using SeaSenseLib with explicit usage of reader, writer, and plotter classes:

```python
import seasenselib as ssl

# Read CTD data from CNV file
reader = ssl.readers.SbeCnvReader("profile.cnv")
ds = reader.data

# Write dataset with CTD data to netCDF file
writer = ssl.writers.NetCdfWriter(ds)
writer.write('profile.nc')

# Plot CTD data
plotter = ssl.plotters.TimeSeriesPlotter(ds)
plotter.plot(parameters=['temperature'])
```

## CLI Usage

You can use the library for reading, converting, and plotting data based on different sensor files.
This chapter describes how to run the program from CLI. 

After installing as a Python package, you can run it via CLI by just using the package name: 

```bash
seasenselib
```
The various features of the library can be executed by using different commands. To invoke a command, simply append 
it as an argument to the program call via CLI (see following example section for some examples). The 
following table gives a short overview of the available commands.

| Command | Description |
|---|---|
| `list` | Display supported readers, writers, plotters, parameters, reader arguments, pipeline stages, handlers, and profiles. |
| `convert` | Converts a file of a specific instrument format to a netCDF, CSV, or Excel file. |
| `show` | Shows the summary for a input file of a specific instrument format.  |
| `plot` | Plots data from the input file using a specified plot type. |

Every command uses different parameters. To get more information about how to use the 
program and each command, just run it with the `--help` (or `-h`) argument:

```bash
seasenselib --help
```

To get help for a single command, add `--help` (or `-h`) argument after typing the command name:

```bash
seasenselib convert --help
```

### Example Data

In the `examples` directory of the [code repository](https://github.com/ocean-uhh/seasenselib) you'll find example files from real research cruises.

- The file `sea-practical-2023.cnv` contains data from a vertical CTD profile (one downcast) with parameters `temperature`, `salinity`, `pressure`, `oxygen`, `turbidity`.
- The file `denmark-strait-ds-m1-17.cnv` contains data from an instrument moored over six days in a depth of around 650 m with parameters `temperature`, `salinity`, `pressure`.

The following examples will guide you through all available commands using the file `sea-practical-2023.cnv`. Please note: these examples are the simplest way to work with data. The behavior of the program can be adjusted with additional arguments, as you can figure out by calling the help via CLI.

### Converting a File to netCDF

Use the following command to convert a file to a netCDF file:

```bash
seasenselib convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc
```

As you can see, format detection works for this command via file extension (`.nc` for netCDF or `.csv` for CSV), but you can also specify it via argument `--format` (or `-f`).

Write a processing protocol for reproducibility or enable verbose logging (both can be used together):

```bash
# Write a processing protocol for reproducibility
seasenselib convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc --processing-protocol

# Enable verbose logging to console
seasenselib convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc --verbose --verbose-level info

# Enable verbose logging to a file
seasenselib convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc --verbose-log run.log --verbose-level debug
```

### Reader-Specific Options

Some formats expose additional reader options. Discover them with:

```bash
seasenselib list reader-args
seasenselib list reader-args --filter nortek-csv
```

Pass a listed option with `--reader-arg`:

```bash
seasenselib convert -i "Average Velocity.csv" -f nortek-csv -o output.nc --reader-arg units-file=Units.csv
```

Reader argument names are validated for the selected or detected input format.

### Explicit Fallback Coordinates

SeaSenseLib does not guess missing coordinates by default. If you want derivations
to use fallback coordinates when the input data has none, provide them explicitly:

```bash
seasenselib convert -i mooring.cnv -o output.nc --default-latitude 54.0 --default-longitude 10.0 --processing-protocol
```

These values are treated as processing assumptions, not as instrument metadata.
Pressure-to-depth derivation only needs latitude. TEOS-10 absolute salinity and
conservative temperature need both latitude and longitude. Use a processing
protocol to record the assumptions for reproducibility.

### Parameter Mapping

Important note: Our example files work out of the box. But in some cases your input files are using variable names (also called "channels" or "columns") for the parameter values, which
are not known to SeaSenseLib. If you get an error due to missing parameters while converting or if you miss parameters during further data processing, e.g. something essential like the temperature, then a parameter mapping might be necessary. 

A parameter mapping is performed with the argument `--mapping` (or `-m`), which is followed by a list of mapping pairs separated with spaces. A mapping pair consists of a standard parameter name that we use within SeaSenseLib and the corresponding name of the variable (column / channel) from the input file. Example for a mapping which works for the example above:

```bash
seasenselib convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc -m temperature=tv290C pressure=prdM salinity=sal00 depth=depSM
```

### Metadata Enrichment

You can also inject metadata during conversion using `--metadata-file` (JSON with `global` and `variables` sections) or `--metadata` (inline JSON). Example:

```bash
seasenselib convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc --metadata '{"global": {"platform": "RV Ludwig Prandtl", "cruise": "UHHSP2023", "institution": "University of Hamburg"}, "variables": {"temperature": {"long_name": "Sea Water Temperature", "units": "degree_Celsius"}}}'
``` 
Or with a metadata JSON file:

```bash
seasenselib convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc --metadata-file metadata.json
``` 

For level-1 metadata, we recommend providing following global attributes in the `global` section of the metadata JSON for CF/ACDD compliance and better discoverability:

- `title`: A short, descriptive title for the dataset.
- `summary`: A paragraph describing the dataset, analogous to an abstract for a paper.
- `keywords`: A comma-separated list of keywords describing the dataset.
- `institution`:  The name of the institution principally responsible for originating this data.
- `project`: The name of the project(s) principally responsible for originating this data.
- `source`: The method of production of the original data. 
- `platform`: The platform from which the data was collected.
- `license`: The license under which the dataset is available.
- `product_version`: Version identifier of the data file or product as assigned by the data creator. 
- `references`: References to related publications or datasets.

For recommended ACDD (Attribute Convention for Data Discovery 1-3) attributes, see: [https://wiki.esipfed.org/Attribute_Convention_for_Data_Discovery_1-3](https://wiki.esipfed.org/Attribute_Convention_for_Data_Discovery_1-3)

For recommended CF Conventions attributes, see: [https://cfconventions.org/](https://cfconventions.org/)


### Pipeline Control

The processing pipeline of SeaSenseLib performs a series of processing stages and steps ("handlers") to convert raw data into a standardized format after reading the input file. By default, most stages and handlers are applied by the "default" pipeline profile, but you can fully control the pipeline execution with CLI flags to apply or skip specific stages or handlers, or switch between built-in profiles.

You can inspect pipeline stages, handlers, and profiles from the CLI:

```bash
# Show available stages
seasenselib list pipeline-stages

# Show available handlers
seasenselib list pipeline-handlers

# Show available pipeline profiles
seasenselib list pipeline-profiles
```

Apply or skip whole stages or individual handlers:

```bash

# Apply stages "mapping" and "unit_handling"
seasenselib show -i examples/sea-practical-2023.cnv --pipeline-apply-stages mapping,unit_handling

# Skip "acdd_auto" handler in "metadata_enrichment" stage
seasenselib show -i examples/sea-practical-2023.cnv --pipeline-skip-handlers metadata_enrichment:acdd_auto
```

Use a built-in profile or provide a custom pipeline file:

```bash
# Use built-in "default" profile
seasenselib convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc --pipeline-profile default

# Use own custom pipeline file 
seasenselib convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc --pipeline-file my_pipeline.json
```

To return raw variables without processing:

```bash
seasenselib show -i examples/sea-practical-2023.cnv --raw-only
```

#### Note on global attributes and metadata handling

SeaSenseLib organizes global attributes into three clear buckets:

1. **CF/ACDD attributes**  
   Standards-compliant attributes (e.g., `Conventions`, `title`, `summary`, `keywords`, `geospatial_*`, `time_coverage_*`) stay at the top level for interoperability.

2. **raw_\* attributes + raw_metadata container**  
   Raw provenance is stored in `raw_*` attributes (e.g., `raw_format`, `raw_filename`, `raw_sha256`, `raw_mtime_utc`) and a structured JSON container (`raw_metadata`, described by `raw_metadata_schema`).  
   Rule: any *non‑whitelisted* global attributes are moved by the pipeline into `raw_metadata.blocks.other.global_attributes`.  
   This keeps top‑level metadata clean while preserving all original reader information.  

3. **processor_\* attributes**  
   Conversion provenance (e.g., `processor_name`, `processor_version`, `processor_module`, `processor_level`) stays at the top level.

### Showing a Data Summary

For the created netCDF file:

```bash
seasenselib show -i output/sea-practical-2023.nc
```

Format detection works also for this command via file extension (`.nc` for netCDF).

### Plotting Data

Plot a T-S diagram:

```bash
seasenselib plot ts-diagram -i examples/sea-practical-2023.cnv
```

Plot a CTD depth profile:

```bash
seasenselib plot depth-profile -i examples/sea-practical-2023.cnv
```

Plot a time series for two parameters:

```bash
seasenselib plot time-series -i examples/sea-practical-2023.cnv -p temperature salinity --dual-axis
```

To save the plots into a file instead showing on screen, just add the parameter `--output` (or `-o`) followed by the path of the output file. 
The file extension determines in which format the plot is saved. Use `.png` for PNG, `.pdf` for PDF, and `.svg` for SVG.

## Extending SeaSenseLib with Plugins

SeaSenseLib supports a plugin system that allows you to add support for additional data formats without modifying the core library. Plugins use Python entry points for automatic discovery.

### Quick Start

**1. Install the example plugin:**

```bash
pip install examples/example-plugin
```

**2. Use it immediately:**

```bash
# Plugin appears automatically (here: example-json)
seasenselib list readers

# Use like any built-in format
seasenselib convert -i examples/example-plugin/data.json -o output.nc
```

### Creating Your Own Plugin

**1. Create a reader class:**

```python
# my_plugin/my_reader.py
from seasenselib.readers.base import AbstractReader
import xarray as xr

class MyFormatReader(AbstractReader):
    def __init__(self, input_file: str):
        self.input_file = input_file
        self._read_file()

    def _read_file(self):
        # Implement your file reading logic here.
        # For example, read the file and store data in self.data
        pass
    
    @staticmethod
    def format_key() -> str:
        return "my-format"
    
    @staticmethod
    def format_name() -> str:
        return "My Custom Format"
    
    @staticmethod
    def file_extension() -> str:
        return ".myf"

    @classmethod
    def file_extensions(cls) -> tuple[str, ...]:
        return (".myf", ".myformat")
```

**2. Register via entry points in `pyproject.toml`:**

```toml
[project.entry-points."seasenselib.readers"]
my_format = "my_plugin.my_reader:MyFormatReader"
```

**3. Install and use:**

```bash
pip install -e .
seasenselib convert -i data.myf -o output.nc 
```

### Plugin Requirements

Your plugin must:
- Inherit from `AbstractReader`, `AbstractWriter`, or `AbstractPlotter`
- Implement `format_key()` and `format_name()` class methods (using `@classmethod`)
- Provide a `data` property (for readers) or `write()` method (for writers)

### Resources

- **[Example Plugin](examples/example-plugin/)** - Working reference implementation (JSON reader/writer)
- **Entry Point Groups**: `seasenselib.readers`, `seasenselib.writers`, `seasenselib.plotters`

## Development

Start here to set up your local development environment: clone the repository, create and activate a Python virtual environment, install all dependencies, and run tests or build the package. These steps ensure you work in an isolated, reproducible setup so you can experiment with the code, add new features, or fix issues before submitting changes.

1. **Clone the repo**  

   ```bash
   git clone https://github.com/ocean-uhh/seasenselib.git
   cd seasenselib
   ```

2. **Create and activate a virtual environment**

   - Linux/macOS:

     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

   - Windows (CMD):

     ```
     python -m venv venv
     venv\Scripts\activate.bat
     ```

   - Windows (PowerShell):

     ```
     python -m venv venv
     venv\Scripts\Activate.ps1
     ```

3. **Upgrade packaging tools and install dependencies**

   ```bash
   pip install --upgrade pip setuptools wheel
   pip install -e ".[dev]"
   ```

The environment is now ready.

Useful commands: 

- **Run tests**

  ```bash
  python -m pytest tests/
  ```

- **Execute the application**

  ```bash
  python -m seasenselib
  ```

- **Build distributions**

  ```bash
  python -m build
  ```

- **Deactivate/Quit the virtual environment**

  ```bash
  deactivate
  ```

## Project Status

SeaSenseLib is a community-driven open source project in active development. The core library and CLI are functional, but we are still working on documentation, testing, and adding support for more formats. The focus is on building a solid foundation with a clean architecture and extensible plugin system with wide support for different data formats. We welcome contributions and feedback to help us improve the library.

### Contributing

Pull requests are welcome! Please open an issue first to discuss what you would like to change.

### License

SeaSenseLib is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
