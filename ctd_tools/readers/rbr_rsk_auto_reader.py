"""
Module for reading RBR RSK data files into xarray Datasets.
"""

import sqlite3
import xarray as xr
from packaging.version import Version
from .base import AbstractReader
from .rbr_rsk_reader import RbrRskReader
from .rbr_rsk_legacy_reader import RbrRskLegacyReader


class RbrRskAutoReader(AbstractReader):
    """
    Facade for reading RBR .rsk files, automatically selecting the correct reader
    based on the file's type and version.

    This class checks the type and version of the RSK file and initializes either
    the RbrRskReader for modern files or the RbrRskLegacyReader for legacy files.
    It reads the data and returns it as an xarray Dataset.      

    Attributes
    ----------
    input_file : str
        The path to the input file containing the RBR data.
    mapping : dict, optional
        A dictionary mapping names used in the input file to standard names.
    data : xr.Dataset | None
        The processed sensor data as an xarray Dataset, or None if not yet processed.

    Methods
    -------
    get_data() -> xr.Dataset | None
        Returns the processed data as an xarray Dataset.
    _select_and_read()
        Selects the appropriate reader based on the RSK file type and version,
        and reads the data into an xarray Dataset.
    """

    def __init__(self, input_file: str, mapping: dict | None = None):
        super().__init__(input_file, mapping)
        self._reader_format_name = None
        self._reader_format_key = None
        self._select_and_read()

    def _select_and_read(self):
        """ Selects the appropriate reader based on the RSK file type and version.

        This method connects to the SQLite database within the RSK file, checks the
        type and version of the database, and initializes either the RbrRskReader
        or the RbrRskLegacyReader accordingly. 
        """

        # Connect to the SQLite database of the RSK file to check type and version
        con = sqlite3.connect(self.input_file)
        try:
            dbinfo = con.execute("SELECT type, version FROM dbInfo").fetchone()
            if dbinfo is None:
                raise ValueError("dbInfo table not found in RSK file.")
            db_type, db_version = dbinfo
        finally:
            con.close()

        # Check if version is >= minimum supported
        is_modern = (
            (db_type.lower() == "full" and Version(db_version) >= Version("2.0.0")) or
            (db_type.lower() == "epdesktop" and Version(db_version) >= Version("1.13.4"))
        )

        # Select the appropriate reader based on the type and version
        if is_modern:
            reader = RbrRskReader(self.input_file, self.mapping)
        else:
            reader = RbrRskLegacyReader(self.input_file, self.mapping)

        # Read the data using the selected reader
        self.data = reader.get_data()
        self._reader_format_name = reader.format_name
        self._reader_format_key = reader.format_key

    @staticmethod
    def format_key() -> str:
        return 'rbr-rsk'

    @staticmethod
    def format_name() -> str:
        return 'RBR RSK'

    @staticmethod
    def file_extension() -> str | None:
        return '.rsk'
