"""
Module for writing sensor data to netCDF files.
"""
from __future__ import annotations
import numpy as np
import xarray as xr

from ctd_tools.writers.base import AbstractWriter

def _is_string_dtype(dt) -> bool:
    # 'U' unicode, 'S' bytes, 'O' object (vlen strings end up object)
    return np.dtype(dt).kind in ("U", "S", "O")

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
    def _sanitize_netcdf_attrs(self, ds: xr.Dataset) -> xr.Dataset:
        """Convert attrs to NetCDF-safe types (no bools/datetimes)."""
        import pandas as pd
        from datetime import datetime

        def fix(v):
            if isinstance(v, (np.bool_, bool)):
                return "true" if v else "false"     # or int(v)
            if isinstance(v, (np.datetime64, pd.Timestamp, datetime)):
                return np.datetime_as_string(np.datetime64(v), unit="ms")
            return v

        ds.attrs = {k: fix(v) for k, v in ds.attrs.items()}
        for var in ds.variables:
            ds[var].attrs = {k: fix(v) for k, v in ds[var].attrs.items()}
        return ds

    def _detect_time_dim(self, ds: xr.Dataset) -> str | None:
        """Heuristic: prefer a coord of datetime64; fallback to 'time' if present."""
        # datetime64 coordinate?
        for name, coord in ds.coords.items():
            if np.issubdtype(coord.dtype, np.datetime64):
                return name
        # common name
        return "time" if "time" in ds.dims else None

    def _build_encoding(
        self,
        ds: xr.Dataset,
        *,
        float32: bool = True,
        quantize: int | None = 3,
        complevel: int = 5,
        shuffle: bool = True,
        chunk_time: int | None = 3600,
        chunk_overrides: dict[str, tuple[int, ...]] | None = None,
        uint8_vars: list[str] | None = None,
        float32_vars: list[str] | None = None,
    ) -> dict:
        """Create an encoding dict for xarray.to_netcdf()."""
        enc: dict[str, dict] = {}
        time_dim = self._detect_time_dim(ds)
        chunk_overrides = chunk_overrides or {}
        uint8_vars = set(uint8_vars or [])
        float32_vars = set(float32_vars or [])

        def chunks_for(var: str) -> tuple[int, ...] | None:
            # explicit override
            if var in chunk_overrides:
                return chunk_overrides[var]
            dims = ds[var].dims
            if not dims:
                return None
            chunks = []
            for d in dims:
                if d == time_dim and chunk_time is not None:
                    # clamp to [1, len]
                    chunks.append(max(1, min(ds.dims[d], int(chunk_time))))
                else:
                    # chunk fully along non-time dims (sane default for typical sizes)
                    chunks.append(ds.dims[d])
            return tuple(chunks)

        for var in ds.variables:
            v = ds[var]
            e = {"zlib": True, "complevel": int(complevel), "shuffle": bool(shuffle)}
            cs = chunks_for(var)
            if cs is not None:
                e["chunksizes"] = cs

            # dtype decisions
            if np.issubdtype(v.dtype, np.floating):
                if (float32 or var in float32_vars) and v.dtype != np.float32:
                    e["dtype"] = "float32"
                if quantize is not None:
                    e["least_significant_digit"] = int(quantize)
            elif var in uint8_vars and v.dtype != np.uint8:
                e["dtype"] = "uint8"

            enc[var] = e

        return enc

    def write(
        self,
        file_name: str,
        *,
        optimize: bool = True,
        engine: str = "netcdf4",
        # size/precision knobs:
        float32: bool = True,
        quantize: int | None = 3,
        complevel: int = 5,
        shuffle: bool = True,
        # variable management:
        drop_derived: bool = False,
        drop_vars: list[str] | None = None,
        uint8_vars: list[str] | None = None,
        float32_vars: list[str] | None = None,
        # chunking:
        chunk_time: int | None = 3600,
        chunk_overrides: dict[str, tuple[int, ...]] | None = None,
    ):
        """
        Write the Dataset to NetCDF with optional compression/encoding optimizations.

        Typical use:
            writer.write("out.nc", optimize=True, drop_derived=True,
                         uint8_vars=[...], float32_vars=[...])
        """
        ds = self.data

        # Optionally drop variables tagged as derived or listed explicitly
        to_drop = set(drop_vars or [])
        if drop_derived:
            for v in list(ds.data_vars):
                if ds[v].attrs.get("derived", False) in (True, "true", "True", 1):
                    to_drop.add(v)
        if to_drop:
            ds = ds.drop_vars(sorted(to_drop))

        # Sanitize attrs for NetCDF
        ds = self._sanitize_netcdf_attrs(ds)

        if not optimize:
            ds.to_netcdf(file_name, engine=engine)
            return

        # Build encoding and write
        encoding = self._build_encoding(
            ds,
            float32=float32,
            quantize=quantize,
            complevel=complevel,
            shuffle=shuffle,
            chunk_time=chunk_time,
            chunk_overrides=chunk_overrides,
            uint8_vars=uint8_vars,
            float32_vars=float32_vars,
        )
        ds.to_netcdf(file_name, engine=engine, encoding=encoding)


    @staticmethod
    def file_extension() -> str:
        """Get the default file extension for this writer.

        Returns:
        --------
        str
            The file extension for netCDF files, which is '.nc'.
        """
        return '.nc'
