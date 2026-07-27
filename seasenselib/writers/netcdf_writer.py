"""
Module for writing sensor data to netCDF files.
"""
import logging
from pathlib import Path
import tempfile

import numpy as np

from seasenselib.core.exceptions import WriterError
from seasenselib.writers.base import AbstractWriter

logger = logging.getLogger(__name__)

_DATETIME_ENCODING_ATTRS = ("units", "calendar")


def _netcdf_name_with_slashes_replaced(name):
    """Return a NetCDF-safe name by replacing slash separators."""
    if isinstance(name, str) and "/" in name:
        return name.replace("/", "_")
    return name


def _build_netcdf_name_map(ds) -> dict:
    """Build a rename map for names containing slashes."""
    names = []
    seen = set()
    for source_names in (ds.dims, ds.coords, ds.data_vars):
        for name in source_names:
            if name not in seen:
                names.append(name)
                seen.add(name)
    final_names = {}
    name_map = {}
    for name in names:
        safe_name = _netcdf_name_with_slashes_replaced(name)
        previous_name = final_names.get(safe_name)
        if previous_name is not None and previous_name != name:
            raise WriterError(
                "NetCDF name sanitization would create duplicate name "
                f"'{safe_name}' from '{previous_name}' and '{name}'. "
                "Please provide explicit variable mappings instead."
            )

        final_names[safe_name] = name
        if safe_name != name:
            name_map[name] = safe_name

    return name_map


def _validate_netcdf_names(ds):
    """Raise a clear error when dataset names cannot be written to NetCDF."""
    invalid_names = []

    for kind, names in [
        ("dimension", ds.dims),
        ("coordinate", ds.coords),
        ("variable", ds.data_vars),
    ]:
        for name in names:
            if "/" in str(name):
                invalid_names.append((kind, name))

    if not invalid_names:
        return

    details = ", ".join(f"{kind} '{name}'" for kind, name in invalid_names)
    raise WriterError(
        "NetCDF output cannot be created because these names contain '/': "
        f"{details}. NetCDF/HDF5 uses '/' as a group separator. Rename or map "
        "these variables before writing, for example map 'cond0S/m' to "
        "'conductivity'. NetCDF name sanitization is enabled by default; if you "
        "disabled it, pass sanitize_names=True in the API or omit "
        "--no-sanitize-netcdf-names in the CLI to replace '/' with '_' "
        "automatically."
    )


def _dataset_with_netcdf_safe_names(ds):
    """Return a dataset with slash-containing names replaced by underscores."""
    name_map = _build_netcdf_name_map(ds)
    if not name_map:
        return ds

    renamed = ds.rename(name_map)
    for original_name, safe_name in name_map.items():
        if safe_name in renamed.data_vars or safe_name in renamed.coords:
            renamed[safe_name].attrs.setdefault("original_name", str(original_name))
    logger.info(
        "Sanitized %d NetCDF name(s) by replacing '/' with '_': %s",
        len(name_map),
        ", ".join(
            f"{original_name!r} -> {safe_name!r}"
            for original_name, safe_name in sorted(
                name_map.items(),
                key=lambda item: str(item[0]),
            )
        ),
    )
    return renamed


def _dataset_with_netcdf_safe_attrs(ds):
    """Return a shallow dataset copy with NetCDF-compatible attributes."""

    def clean_attr_value(value):
        """Convert attribute values to NetCDF-compatible types."""
        if isinstance(value, dict):
            import json

            return json.dumps(value)
        if value is None:
            return ""
        if isinstance(value, (list, tuple)) and len(value) > 0:
            try:
                str(value)
                return value
            except (TypeError, ValueError):
                import json

                return json.dumps(list(value))
        return value

    def clean_variable_metadata(var):
        """Return attrs and encoding safe for NetCDF writing."""
        attrs = {
            attr_name: clean_attr_value(attr_value)
            for attr_name, attr_value in var.attrs.items()
        }
        encoding = dict(var.encoding)

        if np.issubdtype(var.dtype, np.datetime64):
            for attr_name in _DATETIME_ENCODING_ATTRS:
                if attr_name not in attrs:
                    continue
                encoding[attr_name] = attrs.pop(attr_name)
        return attrs, encoding

    safe = ds.copy(deep=False)
    safe.attrs = {
        attr_name: clean_attr_value(attr_value)
        for attr_name, attr_value in ds.attrs.items()
    }

    for var_name, var in ds.data_vars.items():
        attrs, encoding = clean_variable_metadata(var)
        safe[var_name].attrs = attrs
        safe[var_name].encoding = encoding

    for coord_name, coord in ds.coords.items():
        attrs, encoding = clean_variable_metadata(coord)
        safe[coord_name].attrs = attrs
        safe[coord_name].encoding = encoding

    return safe


class NetCdfWriter(AbstractWriter):
    """ Writes sensor data from a xarray Dataset to a netCDF file. 
    
    This class is used to save sensor data in a netCDF format, which is
    commonly used for storing large datasets, especially in oceanography and
    environmental science.
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

    def write(self, file_name: str, sanitize_names: bool = True, **kwargs):
        """ Writes the xarray Dataset to a netCDF file with the specified file name.

        Parameters:
        -----------
        file_name (str): 
            The name of the output netCDF file where the data will be saved.
        sanitize_names : bool, optional
            If True, replace slashes in NetCDF dimension, coordinate, and variable
            names with underscores before writing. Enabled by default.
        """

        ds = self.data
        if sanitize_names:
            ds = _dataset_with_netcdf_safe_names(ds)
        else:
            _validate_netcdf_names(ds)
        safe_ds = _dataset_with_netcdf_safe_attrs(ds)

        output_path = Path(file_name)
        output_dir = (
            output_path.parent if output_path.parent != Path("") else Path(".")
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                dir=output_dir,
                prefix=f".{output_path.name}.",
                suffix=f".tmp{output_path.suffix or '.nc'}",
            ) as temp_file:
                temp_path = Path(temp_file.name)

            logger.info("Writing temporary netCDF file to '%s'", temp_path)
            safe_ds.to_netcdf(temp_path)
            temp_path.replace(output_path)
            logger.info("Wrote netCDF file to '%s'", output_path)
        except Exception as exc:
            if temp_path and temp_path.exists():
                temp_path.unlink()
            if isinstance(exc, WriterError):
                raise
            raise WriterError(
                f"Could not write netCDF file '{file_name}': {exc}"
            ) from exc

    @staticmethod
    def file_extension() -> str:
        """Get the default file extension for this writer.

        Returns:
        --------
        str
            The file extension for netCDF files, which is '.nc'.
        """
        return '.nc'

    @staticmethod
    def format_key() -> str:
        """Get the format key for this writer.
        
        Returns:
        --------
        str
            The format key 'netcdf'.
        """
        return 'netcdf'

    @staticmethod
    def format_name() -> str:
        """Get the human-readable format name.
        
        Returns:
        --------
        str
            The format name 'netCDF'.
        """
        return 'netCDF'
