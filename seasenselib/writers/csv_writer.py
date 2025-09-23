"""
Module for writing sensor data to CSV files.
"""

from seasenselib.writers.base import AbstractWriter
import seasenselib.parameters as params

class CsvWriter(AbstractWriter):
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
    write(file_name: str, coordinate = params.TIME):
        Writes the xarray Dataset to a CSV file with the specified file name and coordinate.
        The coordinate parameter specifies which coordinate to use for selecting the data.
    file_extension: str
        The default file extension for this writer, which is '.csv'.
    """

    def write(self, file_name: str, coordinate=params.TIME, **kwargs):
        """ Writes the xarray Dataset to a CSV file with the specified file name and coordinate.

        Parameters:
        -----------
        file_name (str):
            The name of the output CSV file where the data will be saved.
        coordinate (str):
            The coordinate to use for selecting the data. Default is params.TIME.
            This should be a valid coordinate present in the xarray Dataset.
        **kwargs:
            Additional keyword arguments (unused in this implementation).
        """

        # Select the data corresponding to the specified coordinate
        data = self.data.sel({coordinate: self.data[coordinate].values})

        # Convert the selected data to a pandas dataframe
        df = data.to_dataframe()

        # Write the dataframe to the CSV file
        df.to_csv(file_name, index=True)

    @staticmethod
    def file_extension() -> str:
        """Get the default file extension for this writer.
        
        Returns:
        --------
        str
            The file extension for CSV files, which is '.csv'.
        """
        return '.csv'
