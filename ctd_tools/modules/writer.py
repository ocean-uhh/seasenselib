import xarray as xr
import ctd_tools.ctd_parameters as ctdparams

class NetCdfWriter:
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
    """

    def __init__(self, data: xr.Dataset):
        """ Initializes the NetCdfWriter with the provided xarray Dataset.  

        Parameters:
        -----------
        data (xr.Dataset): 
            The xarray Dataset containing the CTD data to be written.

        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        """

        # Check if the provided data is an xarray Dataset
        if not isinstance(data, xr.Dataset):
            raise TypeError("Data must be an xarray Dataset.")

        # Set the data attribute to the provided xarray Dataset
        self.data = data

    def write(self, file_name: str):
        """ Writes the xarray Dataset to a netCDF file with the specified file name.

        Parameters:
        -----------
        file_name (str): 
            The name of the output netCDF file where the data will be saved.
        """

        self.data.to_netcdf(file_name)

class CsvWriter:
    """ Writes sensor data from a xarray Dataset to a CSV file. 
    
    This class is used to save sensor data in a CSV format, which is a common format for
    tabular data. The provided data is expected to be in an xarray Dataset format.  

    Example usage:
        writer = CsvWriter(data)
        writer.write("output_file.csv")

    Attributes:
    ------------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be written to a CSV file.

    Methods:
    ------------
    __init__(data: xr.Dataset):
        Initializes the CsvWriter with the provided xarray Dataset.
    write(file_name: str, coordinate = ctdparams.TIME):
        Writes the xarray Dataset to a CSV file with the specified file name and coordinate.
        The coordinate parameter specifies which coordinate to use for selecting the data.
    """

    def __init__(self, data: xr.Dataset):
        """ Initializes the CsvWriter with the provided xarray Dataset.

        Parameters:
        -----------
        data (xr.Dataset):
            The xarray Dataset containing the CTD data to be written.

        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        """

        # Check if the provided data is an xarray Dataset
        if not isinstance(data, xr.Dataset):
            raise TypeError("Data must be an xarray Dataset.")

        # Set the data attribute to the provided xarray Dataset
        self.data = data

    def write(self, file_name: str, coordinate = ctdparams.TIME):
        """ Writes the xarray Dataset to a CSV file with the specified file name and coordinate.

        Parameters:
        -----------
        file_name (str):
            The name of the output CSV file where the data will be saved.
        coordinate (str):
            The coordinate to use for selecting the data. Default is ctdparams.TIME.
            This should be a valid coordinate present in the xarray Dataset.
        """

        # Select the data corresponding to the specified coordinate
        data = self.data.sel({coordinate: self.data[coordinate].values})

        # Convert the selected data to a pandas dataframe
        df = data.to_dataframe()

        # Write the dataframe to the CSV file
        df.to_csv(file_name, index=True)

class ExcelWriter:
    """ Writes sensor data from a xarray Dataset to an Excel file. 
    
    This class is used to save sensor data in an Excel format, which is commonly used for
    tabular data. The provided data is expected to be in an xarray Dataset format.

    Example usage:
        writer = ExcelWriter(data)
        writer.write("output_file.xlsx")

    Attributes:
    ------------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be written to an Excel file.   

    Methods:
    ------------
    __init__(data: xr.Dataset):
        Initializes the ExcelWriter with the provided xarray Dataset.
    write(file_name: str, coordinate = ctdparams.TIME):
        Writes the xarray Dataset to an Excel file with the specified file name and coordinate.
        The coordinate parameter specifies which coordinate to use for selecting the data.
    """

    def __init__(self, data: xr.Dataset):
        """ Initializes the ExcelWriter with the provided xarray Dataset.

        Parameters:
        -----------
        data (xr.Dataset):
            The xarray Dataset containing the CTD data to be written.

        Raises:
        -------
        TypeError:
            If the provided data is not an xarray Dataset.
        """

        # Check if the provided data is an xarray Dataset
        if not isinstance(data, xr.Dataset):
            raise TypeError("Data must be an xarray Dataset.")

        # Set the data attribute to the provided xarray Dataset
        self.data = data

    def write(self, file_name: str, coordinate = ctdparams.TIME):
        """ Writes the xarray Dataset to an Excel file with the specified file name and coordinate.

        Parameters:
        -----------
        file_name (str):
            The name of the output Excel file where the data will be saved.
        coordinate (str):
            The coordinate to use for selecting the data. Default is ctdparams.TIME.
            This should be a valid coordinate present in the xarray Dataset.

        Raises:
        -------
        ValueError:
            If the provided coordinate is not found in the dataset.
        """

        # Check if the provided coordinate is valid
        if coordinate not in self.data.coords:
            raise ValueError(f"Coordinate '{coordinate}' not found in the dataset.")

        # Select the data corresponding to the specified coordinate
        data = self.data.sel({coordinate: self.data[coordinate].values})

        # Convert the selected data to a pandas dataframe
        df = data.to_dataframe()

        # Write the dataframe to the Excel file
        df.to_excel(file_name, engine='openpyxl')
