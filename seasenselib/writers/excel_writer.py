"""
Module for writing sensor data to Excel files.
"""

from seasenselib.writers.base import AbstractWriter
import seasenselib.parameters as params

class ExcelWriter(AbstractWriter):
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
    write(file_name: str, coordinate = params.TIME):
        Writes the xarray Dataset to an Excel file with the specified file name and coordinate.
        The coordinate parameter specifies which coordinate to use for selecting the data.
    file_extension: str
        The default file extension for this writer, which is '.xlsx'.
    """

    def write(self, file_name: str, coordinate=params.TIME, **kwargs):
        """ Writes the xarray Dataset to an Excel file with the specified file name and coordinate.

        Parameters:
        -----------
        file_name (str):
            The name of the output Excel file where the data will be saved.
        coordinate (str):
            The coordinate to use for selecting the data. Default is params.TIME.
            This should be a valid coordinate present in the xarray Dataset.
        **kwargs:
            Additional keyword arguments (unused in this implementation).

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

    @staticmethod
    def file_extension() -> str:
        """Get the default file extension for this writer.

        Returns:
        --------
        str
            The file extension for Excel files, which is '.xlsx'.
        """
        return '.xlsx'
