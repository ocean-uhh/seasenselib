"""
Module for reading ADCP (RDI/Teledyne Workhorse) data from MATLAB .mat files converted from binary with rdadcp.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import xarray as xr
from datetime import datetime
from seasenselib.readers.base import AbstractReader
import seasenselib.parameters as params


class AdcpMatlabRdadcpReader(AbstractReader):
    """Reader which converts ADCP data stored in MATLAB .mat files converted from binary with rdadcp into an xarray Dataset."""

    def __init__(self, input_file: str,
                 time_dim: str = params.TIME,
                 bin_dim: str = "bin",
                 beam_dim: str = "beam",
                 mapping: dict | None = None,
                 **kwargs):
        """Initialize AdcpMatlabRdadcpReader.
        
        Parameters
        ----------
        input_file : str
            Path to the MAT file.
        time_dim : str, default=params.TIME
            Name of the time dimension in the output dataset.
        bin_dim : str, default="bin"
            Name of the bin dimension in the output dataset.
        beam_dim : str, default="beam"
            Name of the beam dimension in the output dataset.
        mapping : dict, optional
            Variable name mapping dictionary.
        **kwargs
            Additional base class parameters:
            
            - input_header_file : str | None
                Path to separate header file (if applicable).
            - perform_default_postprocessing : bool, default=True
                Whether to perform default post-processing.
            - rename_variables : bool, default=True
                Whether to rename variables to standard names.
            - assign_metadata : bool, default=True
                Whether to assign CF-compliant metadata.
            - sort_variables : bool, default=True
                Whether to sort variables alphabetically.
        """
        self._time_dim = time_dim
        self._bin_dim = bin_dim
        self._beam_dim = beam_dim
        super().__init__(input_file, mapping, **kwargs)
        self._validate_file()

    # ---------- helpers ----------
    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...] | None:
        """Return valid file extensions for MATLAB files."""
        return ('.mat',)

    @classmethod
    def reader_args(cls) -> list[dict]:
        return []

    @staticmethod
    def _matlab_datenum_to_datetime64(dnums: np.ndarray) -> np.ndarray:
        # MATLAB datenum -> Unix epoch days offset (719529 days)
        return (pd.to_datetime(dnums - 719529, unit="D")).values.astype("datetime64[ns]")

    @staticmethod
    def _iso_ms(x: np.datetime64 | pd.Timestamp | datetime) -> str:
        return np.datetime_as_string(np.datetime64(x), unit="ms")

    @staticmethod
    def _maybe_cm_per_s_to_m_per_s(arr: np.ndarray) -> tuple[np.ndarray, bool]:
        """Heuristic: if 95th percentile magnitude > 1, assume cm/s and convert to m/s."""
        a = np.asarray(arr, dtype=float)
        p95 = np.nanpercentile(np.abs(a), 95)
        if p95 > 1.0:
            return a / 100.0, True
        return a, False

    @staticmethod
    def _pad_time_last_dim(arr: np.ndarray, target_nt: int) -> np.ndarray:
        """Pad last dimension with NaNs if it's target_nt-1; truncate if target_nt+1."""
        if arr.shape[-1] == target_nt:
            return arr
        if arr.shape[-1] == target_nt - 1:
            pad_shape = list(arr.shape)
            pad_shape[-1] = 1
            pad = np.full(pad_shape, np.nan)
            return np.concatenate([arr, pad], axis=-1)
        if arr.shape[-1] == target_nt + 1:
            return arr[..., :target_nt]
        # otherwise, leave as is (caller may error later)
        return arr

    # ---------- core parsing ----------
    def _parse(self, mat_file_path):
        import scipy.io

        mat = scipy.io.loadmat(mat_file_path, squeeze_me=True, struct_as_record=False)
        if "adcp" not in mat:
            raise KeyError("Expected a top-level struct named 'adcp' in the MAT file.")
        adcp = mat["adcp"]
        cfg = getattr(adcp, "config", None)
        if cfg is None:
            raise KeyError("Missing 'adcp.config' struct.")

        # --- time & keep mask ---
        mtime = np.asarray(getattr(adcp, "mtime"), dtype=float).ravel()
        keep_idx = np.where((mtime != 0) & np.isfinite(mtime))[0]   # drop corrupted rows
        dropped = int(mtime.size - keep_idx.size)

        # helper to index last axis with keep_idx (robust to arrays that are one-sample short)
        def _take_last(a, idx):
            a = np.asarray(a)
            if a.ndim == 0:
                return a
            tlen = a.shape[-1]
            if tlen == 0:
                return a
            # clip indices to array length in case some arrays are already shorter
            idx2 = idx[idx < tlen]
            return a[..., idx2]

        # convert kept matlab datenums to datetime64
        time = self._matlab_datenum_to_datetime64(mtime[keep_idx])
        nt = time.size

        # --- read shapes / config as before ---
        ev = np.asarray(getattr(adcp, "east_vel"))
        n_cells = int(getattr(cfg, "n_cells", getattr(cfg, "n_beams", 0))) or ev.shape[0]
        bin_idx = np.arange(1, n_cells + 1)
        ranges = np.asarray(getattr(cfg, "ranges", np.arange(n_cells) * np.nan)).reshape(-1)
        if ranges.size != n_cells:
            ranges = np.full(n_cells, np.nan)

        orientation = str(getattr(cfg, "orientation", "up")).lower().strip()
        sgn = +1 if orientation.startswith("up") else -1

        # --- 1D series (time) with mask applied ---
        depth_pd = _take_last(getattr(adcp, "depth"), keep_idx).astype(float).reshape(-1)
        pressure  = _take_last(getattr(adcp, "pressure"), keep_idx).astype(float).reshape(-1)
        number    = _take_last(getattr(adcp, "number"), keep_idx).astype(float).reshape(-1)
        heading   = _take_last(getattr(adcp, "heading"), keep_idx).astype(float).reshape(-1)
        pitch     = _take_last(getattr(adcp, "pitch"), keep_idx).astype(float).reshape(-1)
        roll      = _take_last(getattr(adcp, "roll"), keep_idx).astype(float).reshape(-1)
        heading_std = _take_last(getattr(adcp, "heading_std"), keep_idx).astype(float).reshape(-1)
        pitch_std   = _take_last(getattr(adcp, "pitch_std"), keep_idx).astype(float).reshape(-1)
        roll_std    = _take_last(getattr(adcp, "roll_std"), keep_idx).astype(float).reshape(-1)
        temperature = _take_last(getattr(adcp, "temperature"), keep_idx).astype(float).reshape(-1)
        salinity    = _take_last(getattr(adcp, "salinity"), keep_idx).astype(float).reshape(-1)
        pressure_std= _take_last(getattr(adcp, "pressure_std"), keep_idx).astype(float).reshape(-1)

        # --- 2D velocities (bin, time) with mask applied on time axis ---
        east  = _take_last(getattr(adcp, "east_vel"),  keep_idx).astype(float)
        north = _take_last(getattr(adcp, "north_vel"), keep_idx).astype(float)
        vert  = _take_last(getattr(adcp, "vert_vel"),  keep_idx).astype(float)
        # transpose if they came in as (time, bin)
        if east.shape[0] != n_cells and east.shape[1] == n_cells:
            east, north, vert = east.T, north.T, vert.T

        # --- 3D QA (bin, beam, time) mask on time axis ---
        def _bbt(a):
            a = np.asarray(a)
            if a.ndim != 3:
                return a
            b0, b1, t = a.shape
            if b0 == n_cells and b1 == 4:
                return a
            if b1 == n_cells and b0 == 4:
                return np.transpose(a, (1, 0, 2))
            if b0 == 4 and b1 != 4:
                return np.transpose(a, (1, 0, 2))
            return a

        corr   = _take_last(_bbt(getattr(adcp, "corr")),   keep_idx).astype(float)
        status = _take_last(_bbt(getattr(adcp, "status")), keep_idx).astype(float)
        intens = _take_last(_bbt(getattr(adcp, "intens")), keep_idx).astype(float)
        perc_good = _take_last(_bbt(getattr(adcp, "perc_good")), keep_idx).astype(float)

        # --- bottom track (beam, time) ---
        bt_range     = _take_last(getattr(adcp, "bt_range"),     keep_idx).astype(float)
        bt_vel       = _take_last(getattr(adcp, "bt_vel"),       keep_idx).astype(float)
        bt_corr      = _take_last(getattr(adcp, "bt_corr"),      keep_idx).astype(float)
        bt_ampl      = _take_last(getattr(adcp, "bt_ampl"),      keep_idx).astype(float)
        bt_perc_good = _take_last(getattr(adcp, "bt_perc_good"), keep_idx).astype(float)

        # --- z(bin,time) using kept times only ---
        # depth positive-down; z positive-up: z = -depth + sgn * ranges
        z_2d = (-depth_pd[np.newaxis, :]) + sgn * ranges[:, np.newaxis]

        # --- pressure units heuristic (after masking) ---
        pres_med = float(np.nanmedian(pressure))
        pres_units = "dbar"
        self._orig_pres_units = "unknown"
        if pres_med > 1e4:
            pressure = pressure / 1e3
            pressure_std = pressure_std / 1e3
            self._orig_pres_units = "Pa"

        # --- vertical velocity cm/s -> m/s heuristic (after masking) ---
        vert, self._vert_converted_from_cm = self._maybe_cm_per_s_to_m_per_s(vert)

        # keep config/attrs
        self._cfg = cfg
        self._orientation = orientation
        self._dropped_zero_mtime = dropped  # for attrs

        return {
            params.TIME: time,
            "nt": nt,
            "n_cells": n_cells,
            "bin_idx": np.arange(1, n_cells+1),
            "ranges": ranges,
            "z_2d": z_2d,
            "east": east,
            "north": north,
            "vert": vert,
            "depth_pd": depth_pd,
            "pressure": pressure,
            "number": number,
            "heading": heading,
            "pitch": pitch,
            "roll": roll,
            "heading_std": heading_std,
            "pitch_std": pitch_std,
            "roll_std": roll_std,
            "temperature": temperature,
            "salinity": salinity,
            "pressure_std": pressure_std,
            "corr": corr,
            "status": status,
            "intens": intens,
            "perc_good": perc_good,
            "bt_range": bt_range,
            "bt_vel": bt_vel,
            "bt_corr": bt_corr,
            "bt_ampl": bt_ampl,
            "bt_perc_good": bt_perc_good,
            "pres_units": pres_units,
        }


    # ---------- dataset creation ----------
    def _create_xarray_dataset(self, P) -> xr.Dataset:
        n_cells, nt = P["n_cells"], P["nt"]

        coords = {
            self._time_dim: (self._time_dim, P[params.TIME]),
            self._bin_dim: (self._bin_dim, P["bin_idx"]),
            "range": (self._bin_dim, P["ranges"]),  # cell-center distance from transducer [m]
        }

        # 2-D z coordinate (positive upward)
        coords["z"] = ((self._bin_dim, self._time_dim), P["z_2d"])

        ds = xr.Dataset(
            data_vars={
                # velocities
                "east_velocity": ((self._bin_dim, self._time_dim), P["east"]),
                "north_velocity": ((self._bin_dim, self._time_dim), P["north"]),
                "up_velocity": ((self._bin_dim, self._time_dim), P["vert"]),

                # 1-D sensor data
                "depth": (self._time_dim, P["depth_pd"]),           # positive down
                "pressure": (self._time_dim, P["pressure"]),
                "ensemble_number": (self._time_dim, P["number"]),
                "heading": (self._time_dim, P["heading"]),
                "pitch": (self._time_dim, P["pitch"]),
                "roll": (self._time_dim, P["roll"]),
                "heading_std": (self._time_dim, P["heading_std"]),
                "pitch_std": (self._time_dim, P["pitch_std"]),
                "roll_std": (self._time_dim, P["roll_std"]),
                "temperature": (self._time_dim, P["temperature"]),
                "salinity": (self._time_dim, P["salinity"]),
                "pressure_std": (self._time_dim, P["pressure_std"]),

                # 3-D QA fields
                "correlation_magnitude": ((self._bin_dim, self._beam_dim, self._time_dim), P["corr"]),
                "echo_intensity": ((self._bin_dim, self._beam_dim, self._time_dim), P["intens"]),
                "status": ((self._bin_dim, self._beam_dim, self._time_dim), P["status"]),
                "percent_good": ((self._bin_dim, self._beam_dim, self._time_dim), P["perc_good"]),

                # bottom track
                "bt_range": ((self._beam_dim, self._time_dim), P["bt_range"]),
                "bt_velocity": ((self._beam_dim, self._time_dim), P["bt_vel"]),
                "bt_correlation": ((self._beam_dim, self._time_dim), P["bt_corr"]),
                "bt_amplitude": ((self._beam_dim, self._time_dim), P["bt_ampl"]),
                "bt_percent_good": ((self._beam_dim, self._time_dim), P["bt_perc_good"]),
            },
            coords=coords,
            attrs={
                "Conventions": "CF-1.13",
                "title": "ADCP (RDI/Teledyne Workhorse) time series",
                "source": "ADCP MATLAB export (adcp struct)",
                "instrument_type": str(getattr(self._cfg, "name", "wh-adcp")),
                "beam_angle": float(getattr(self._cfg, "beam_angle", np.nan)),
                "beam_frequency_kHz": float(getattr(self._cfg, "beam_freq", np.nan)),
                "cell_size_m": float(getattr(self._cfg, "cell_size", np.nan)),
                "bin1_distance_m": float(getattr(self._cfg, "bin1_dist", np.nan)),
                "blank_distance_m": float(getattr(self._cfg, "blank", np.nan)),
                "n_cells": int(getattr(self._cfg, "n_cells", n_cells)),
                "pings_per_ensemble": int(getattr(self._cfg, "pings_per_ensemble", np.nan)),
                "coord_system": str(getattr(self._cfg, "coord_sys", "")),
                "orientation": self._orientation,
                "xducer_misalign_deg": float(getattr(self._cfg, "xducer_misalign", 0.0)),
                "magnetic_variation_deg": float(getattr(self._cfg, "magnetic_var", 0.0)),
                "ranges_definition": "cell center range from transducer [m]",
                "time_coverage_start": self._iso_ms(P[params.TIME][0]),
                "time_coverage_end": self._iso_ms(P[params.TIME][-1]),
                "vertical_velocity_converted_from_cm_s": bool(self._vert_converted_from_cm),
                "pressure_original_units": self._orig_pres_units,
            },
        )
        # Record that we dropped some samples.
        ds.attrs["dropped_zero_mtime_samples"] = int(getattr(self, "_dropped_zero_mtime", 0))

        # Deal with boolean
        ds.attrs.update({
            # ...
            "vertical_velocity_converted_from_cm_s": (
                "true" if self._vert_converted_from_cm else "false"
                # or: int(self._vert_converted_from_cm)
            ),
        })

        # Minimal variable attributes with units (stages will add CF compliance)
        ds["east_velocity"].attrs = {"units": "m s-1"}
        ds["north_velocity"].attrs = {"units": "m s-1"}
        ds["up_velocity"].attrs = {
            "units": "m s-1",
            "note": "Positive upward (heuristic conversion from cm/s applied if needed)."
        }
        ds["depth"].attrs = {"units": "m", "positive": "down"}
        ds["z"].attrs = {
            "units": "m", "positive": "up",
            "comment": "z(bin,time) = -depth(time) ± range(bin) depending on orientation"
        }
        ds["range"].attrs = {"units": "m"}
        ds["pressure"].attrs = {"units": P["pres_units"]}
        ds["pressure_std"].attrs = {"units": P["pres_units"]}
        
        for nm in ("heading", "pitch", "roll", "heading_std", "pitch_std", "roll_std"):
            ds[nm].attrs["units"] = "degree"
        
        ds["temperature"].attrs = {"units": "degree_Celsius"}
        ds["salinity"].attrs = {"units": "1e-3"}
        ds["ensemble_number"].attrs = {"units": "1"}
        ds["correlation_magnitude"].attrs = {"units": "1"}
        ds["echo_intensity"].attrs = {"units": "counts"}
        ds["status"].attrs = {"units": "1"}
        ds["percent_good"].attrs = {"units": "percent"}
        ds["bt_range"].attrs = {"units": "m"}
        ds["bt_velocity"].attrs = {"units": "m s-1"}
        ds["bt_correlation"].attrs = {"units": "1"}
        ds["bt_amplitude"].attrs = {"units": "counts"}
        ds["bt_percent_good"].attrs = {"units": "percent"}

        # allow your metadata mapping hook to add/override
        for key in list(ds.data_vars.keys()) + list(ds.coords.keys()):
            super()._assign_metadata_for_key_to_xarray_dataset(ds, key)

        return ds

    def _load_data(self) -> xr.Dataset:
        """Load data from the MATLAB file and return an xarray Dataset."""
        parsed = self._parse(self.input_file)
        return self._create_xarray_dataset(parsed)

    @classmethod
    def format_mappings(cls) -> dict[str, list]:
        """Return ADCP rdadcp format-specific variable name mappings.
        
        Returns
        -------
        dict[str, list]
            Dictionary mapping standard names to ADCP format-specific aliases.
        """
        return {
            params.EAST_VELOCITY: ['east_velocity'],
            params.NORTH_VELOCITY: ['north_velocity'],
            params.UP_VELOCITY: ['up_velocity'],
            params.DEPTH: ['depth'],
            params.PRESSURE: ['pressure'],
            params.TEMPERATURE: ['temperature'],
            params.SALINITY: ['salinity'],
        }

    @classmethod
    def format_key(cls) -> str:
        return 'adcp-matlab-rdadcp'

    @classmethod
    def format_name(cls) -> str:
        return "ADCP Matlab rdadcp"

    @classmethod
    def file_extension(cls) -> str | None:
        return None
