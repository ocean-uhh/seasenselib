# CTD Tools

A collection of tools for reading, converting, and plotting of CTD data.

## Installation

First you have to checkout the project to your device by using git. Open a terminal and enter the following command:

```bash
$ git clone https://gitlab.rrz.uni-hamburg.de/ifmeo-sea-practical/ctd-tools.git
```

Change into the project's directory:

```bash
$ cd ctd-tools
```

Then install all required packages for this Python project.

1. If you use pipenv:

   ```bash
   $ pipenv install
   ```

2. If you use pip:

   ```bash
   $ pip install -r requirements.txt
   ```
3. Or via python:

   ```bash
   $ python -m pip install -r requirements.txt
   ```

Now you're ready to use the program.

## CLI Usage

You can use the tool for reading, converting, and plotting CTD data based on Seabird CNV files.
This chapter describes how to run the program from CLI. The following tables gives a short overview
of the available commands.

| Command | Description |
|---|---|
| `convert` | Converts a Seabird CNV file to a netCDF or CSV. |
| `show` | Shows the summary for a netCDF, CSV, or CNV file.  |
| `plot-ts` | Plots a T-S diagram based on data from a netCDF, CSV, or CNV file. |
| `plot-profile` | Plots a vertical CTD profile based on data from a netCDF, CSV, or CNV file. |
| `plot-series` | Plots a time series based on a given parameter from a netCDF, CSV, or CNV file. |

Every command uses different parameters. To get more information about how to use the program, just run it with the `--help` (or `-h`) argument:

```bash
$ python src/main.py --help
```

To get help for a single command, add `--help` (or `-h`) argument after typing the command name:

```bash
$ python src/main.py convert --help
```

## Example data

In the `examples` directory you'll find example Seabird CNV files from real research cruises.

- The file `sea-practical-2023.cnv` contains data from a vertical CTD profile (one downcast) with parameters `temperature`, `salinity`, `pressure`, `oxygen`, `turbidity`.
- The file `denmark-strait-ds-m1-17.cnv` contains data from an instrument moored over six days in a depth of around 650 m with parameters `temperature`, `salinity`, `pressure`.

The following examples will guide you through all available commands using the example file `sea-practical-2023.cnv`. (Please note: these examples are the simplest way to work with data. The behavior of the program can be adjusted with additional arguments, as you can figure out by calling the help via CLI.)

### Converting a CNV file to netCDF

Use the following command to convert a CNV file to a netCDF file:

```bash
$ python src/main.py convert -i examples/sea-practical-2023.cnv -o output/sea-practical-2023.nc -f netcdf
```

### Showing the summary of a netCDF

For the created netCDF file:

```bash
$ python src/main.py show -i output/sea-practical-2023.nc
```

As you can see, format detection works for this command via file extension (.nc for netCDF, .csv for CSV, .cnv for CNV).

### Plotting a T-S diagram, vertical profile and time series from a netCDF file

Plot a T-S diagram:

```bash
$ python src/main.py plot-ts -i output/sea-practical-2023.nc
```

Plot a vertical CTD profile:

```bash
$ python src/main.py plot-profile -i output/sea-practical-2023.nc
```

Plot a time series for 'temperature' parameter:

```bash
$ python src/main.py plot-series -i output/sea-practical-2023.nc -p temperature
```

As you can see, format detection works also for this command via file extension (.nc for netCDF, .csv for CSV, .cnv for CNV).

