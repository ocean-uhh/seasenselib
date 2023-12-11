# CTD Tools

A library for reading, converting, and plotting of CTD data based on Seabird CNV files.

## Installation

To install CTD Tools, we strongly recommend using a scientific Python distribution. 
If you already have Python, you can install CTD Tools with:

```bash
$ pip install ctd-tools
```

Now you're ready to use the library.

## How to import CTD Tools

Example code for using the CTD Tools library in your project:

```python
from ctd_tools.modules.reader import CnvReader, NetCdfReader
from ctd_tools.modules.writer import NetCdfWriter
from ctd_tools.modules.plotter import CtdPlotter

# Read CTD data from CNV file
reader = CnvReader("sea-practical-2023.cnv")
dataset = reader.get_data()

# Write dataset with CTD data to netCDF file
writer = NetCdfWriter(dataset)
writer.write('sea-practical-2023.nc')

# Plot CTD data
plotter = CtdPlotter(dataset)
plotter.plot_profile() # vertical profile
plotter.plot_ts_diagram() # T-S diagram
plotter.plot_time_series(parameter_name='temperature') # time series
```

## CLI Usage

You can use the tool for reading, converting, and plotting CTD data based on Seabird CNV files.
This chapter describes how to run the program from CLI. 

After installing as a Python package, you can run it via CLI by just using the package name: 

```bash
$ ctd-tools
```
The various features of the tool can be executed by using different commands. To invoke a command, simply append 
it as an argument to the program call via CLI (see following example section for some examples). The 
following table gives a short overview of the available commands.

| Command | Description |
|---|---|
| `convert` | Converts a Seabird CNV file to a netCDF or CSV. |
| `show` | Shows the summary for a netCDF, CSV, or CNV file.  |
| `plot-ts` | Plots a T-S diagram based on data from a netCDF, CSV, or CNV file. Via argument you can plot on screen or into a file. |
| `plot-profile` | Plots a vertical CTD profile based on data from a netCDF, CSV, or CNV file. Via argument you can plot on screen or into a file. |
| `plot-series` | Plots a time series based on a given parameter from a netCDF, CSV, or CNV file. Via argument you can plot on screen or into a file. |

Every command uses different parameters. To get more information about how to use the 
program and each command, just run it with the `--help` (or `-h`) argument:

```bash
$ ctd-tools --help
```

To get help for a single command, add `--help` (or `-h`) argument after typing the command name:

```bash
$ ctd-tools convert --help
```

## Example data

In the `examples` directory of the [code repository on GitLab](https://gitlab.rrz.uni-hamburg.de/ifmeo-sea-practical/ctd-tools) you'll find example Seabird CNV files from real research cruises.

- The file `sea-practical-2023.cnv` contains data from a vertical CTD profile (one downcast) with parameters `temperature`, `salinity`, `pressure`, `oxygen`, `turbidity`.
- The file `denmark-strait-ds-m1-17.cnv` contains data from an instrument moored over six days in a depth of around 650 m with parameters `temperature`, `salinity`, `pressure`.

The following examples will guide you through all available commands using the file `sea-practical-2023.cnv`. (Please note: these examples are the simplest way to work with data. The behavior of the program can be adjusted with additional arguments, as you can figure out by calling the help via CLI.)

### Converting a CNV file to netCDF

Use the following command to convert a CNV file to a netCDF file:

```bash
$ ctd-tools convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc
```

As you can see, format detection works for this command via file extension (`.nc` for netCDF or `.csv` for CSV), but you can also specify it via argument `--format` (or `-f`).

Important note: Our example files work out of the box. But in some cases your Seabird CNV files are using column names (so called "channels") for the parameter values, which
are not known of our program or the `pycnv` library which we're using. If you get an error due to missing parameters while converting or if you miss parameters during further data processing, e.g. something essential like the temperature, then a parameter mapping might be necessary. A parameter mapping is performed with the argument `--mapping` (or `-m`), which is followed by a list of mapping pairs separated with spaces. A mapping pair consists of a standard parameter name that we use within the program and the corresponding name of the column or channel from the Seabird CNV file. Example for a mapping which works for the example above:

```bash
$ ctd-tools convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc -m temperature=tv290C pressure=prdM salinity=sal00 depth=depSM
```

### Showing the summary of a netCDF

For the created netCDF file:

```bash
$ ctd-tools show -i output/sea-practical-2023.nc
```

Again, format detection works also for this command via file extension (`.nc` for netCDF, `.csv` for CSV, `.cnv` for CNV).

### Plotting a T-S diagram, vertical profile and time series from a netCDF file

Plot a T-S diagram:

```bash
$ ctd-tools plot-ts -i output/sea-practical-2023.nc
```

Plot a vertical CTD profile:

```bash
$ ctd-tools plot-profile -i output/sea-practical-2023.nc
```

Plot a time series for 'temperature' parameter:

```bash
$ ctd-tools plot-series -i output/sea-practical-2023.nc -p temperature
```

Also for this command, format detection works via file extension (`.nc` for netCDF, `.csv` for CSV, `.cnv` for CNV).

To save the plots into a file instead showing on screen, just add the parameter `--output` (or `-o`) followed by the path of the output file. 
The file extension determines in which format the plot is saved. Use `.png` for PNG, `.pdf` for PDF, and `.svg` for SVG.
