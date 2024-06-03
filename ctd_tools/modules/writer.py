import xarray as xr
import ctd_tools.ctd_parameters as ctdparams

class NetCdfWriter:
    """ Writes CTD data from a xarray Dataset to a netCDF file. """

    def __init__(self, data: xr.Dataset):
        self.data = data

    def write(self, file_name: str):
        self.data.to_netcdf(file_name)

class CsvWriter:
    """ Writes CTD data from a xarray Dataset to a CSV file. """

    def __init__(self, data: xr.Dataset):
        self.data = data

    def write(self, file_name: str, coordinate = ctdparams.TIME):
        # Select the data corresponding to the specified coordinate
        data = self.data.sel({coordinate: self.data[coordinate].values})

        # Convert the selected data to a pandas dataframe
        df = self.data.to_dataframe()

        # Write the dataframe to the CSV file
        df.to_csv(file_name, index=True)

class ExcelWriter:
    """ Writes CTD data from a xarray Dataset to an Excel file. """

    def __init__(self, data: xr.Dataset):
        self.data = data

    def write(self, file_name: str, coordinate = ctdparams.TIME):
        # Select the data corresponding to the specified coordinate
        data = self.data.sel({coordinate: self.data[coordinate].values})

        # Convert the selected data to a pandas dataframe
        df = self.data.to_dataframe()

        # Write the dataframe to the CSV file
        df.to_excel(file_name, engine='openpyxl')
