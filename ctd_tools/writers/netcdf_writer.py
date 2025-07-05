"""
Module for writing sensor data to netCDF files.
"""

from ctd_tools.writers.base import AbstractWriter

class NetCdfWriter(AbstractWriter):
    """ Writes sensor data from a xarray Dataset to a netCDF file. 
    
    This class is used to save sensor data in a netCDF format, which is commonly used for
    storing large datasets, especially in the field of oceanography and environmental science.
    The provided data is expected to be in an xarray Dataset format.

    Example usage:
        writer = NetCdfWriter(data)
        writer.write("output_file.nc")
    
    Attributes:
    ------------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be written to a netCDF file.

    Methods:
    ------------
    __init__(data: xr.Dataset):
        Initializes the NetCdfWriter with the provided xarray Dataset.
    write(file_name: str):
        Writes the xarray Dataset to a netCDF file with the specified file name.
    file_extension: str
        The default file extension for this writer, which is '.nc'.
    """

    def write(self, file_name: str, **kwargs):
        """ Writes the xarray Dataset to a netCDF file with the specified file name.

        Parameters:
        -----------
        file_name (str): 
            The name of the output netCDF file where the data will be saved.
        """
        self.data.to_netcdf(file_name)

    @staticmethod
    def file_extension() -> str:
        """Get the default file extension for this writer.

        Returns:
        --------
        str
            The file extension for netCDF files, which is '.nc'.
        """
        return '.nc'
