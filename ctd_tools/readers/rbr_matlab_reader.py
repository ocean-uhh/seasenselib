"""
Facade for reading RBR MATLAB .mat files, automatically selecting the correct reader
based on the root variable in the MATLAB structure.

If the root variable is "RBR", delegates to RbrMatlabLegacyReader.
If the root variable is "rsk", delegates to RbrMatlabRsktoolsReader.
Otherwise, raises an error.
"""

from __future__ import annotations
import scipy.io
from .base import AbstractReader
from .rbr_matlab_legacy_reader import RbrMatlabLegacyReader
from .rbr_matlab_rsktools_reader import RbrMatlabRsktoolsReader

class RbrMatlabReader(AbstractReader):
    """
    Facade for reading RBR Matlab .mat files, automatically selecting the correct reader
    based on the root variable in the MATLAB structure.
    """
    def __init__(self, input_file: str, mapping: dict | None = None):
        super().__init__(input_file, mapping)
        self._reader_format_name = None
        self._reader_format_key = None
        self._select_and_read()

    def _select_and_read(self):
        """
        Selects the appropriate reader based on the root variable in the MATLAB file.
        """

        # Load Matlab file to inspect root variable
        mat = scipy.io.loadmat(self.input_file, squeeze_me=True, struct_as_record=False)

        # Select the appropriate reader based on root variable
        if "RBR" in mat:
            reader = RbrMatlabLegacyReader(self.input_file, self.mapping)
        elif "rsk" in mat:
            reader = RbrMatlabRsktoolsReader(self.input_file, self.mapping)
        else:
            raise ValueError("Neither 'RBR' nor 'rsk' struct found in .mat file.")

        # Read the data using the selected reader
        self.data = reader.data if hasattr(reader, "data") \
            else reader.get_data() if hasattr(reader, "get_data") else None
        self._reader_format_name = reader.format_name
        self._reader_format_key = reader.format_key

    @staticmethod
    def format_key() -> str:
        return 'rbr-matlab'

    @staticmethod
    def format_name() -> str:
        return 'RBR Matlab'

    @staticmethod
    def file_extension() -> str | None:
        return None
