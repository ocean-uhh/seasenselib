"""Reader wrapper for RDI raw binary ADCP files."""

from __future__ import annotations

from contextlib import redirect_stdout
import inspect
import io
import json
import logging
from typing import Any, Callable

import numpy as np
import xarray as xr

import seasenselib.parameters as params
from .base import AbstractReader


logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = (".000", ".pd0", ".enr", ".ens", ".enx")
_RDI_SALINITY_SETTING = "rdi_salinity_setting"
_RDI_TEMPERATURE_SETTING = "rdi_temperature_setting"
_RDI_TRANSDUCER_DEPTH = "rdi_transducer_depth"
_RDI_PRESSURE_PLACEHOLDER = "rdi_pressure_placeholder"
_RDI_SENSOR_BITS = {
    "c_sound": 6,
    "depth": 5,
    "heading": 4,
    "pitch": 3,
    "roll": 2,
    "salinity": 1,
    "temp": 0,
}
_SENSOR_SOURCE_DESCRIPTIONS = {
    "sensor": "Value is interpreted as coming from an instrument sensor.",
    "configured": "Value is interpreted as an instrument or user setting.",
    "configured_fallback": (
        "A sensor value was requested, but RDI flags indicate that the "
        "instrument fell back to a configured setting."
    ),
    "derived": "Value is interpreted as calculated by the instrument.",
    "placeholder": "Field is present but is not interpreted as a valid value.",
    "unknown": "Source cannot be determined from available metadata.",
}
_RDI_SENSOR_BASIS_DESCRIPTIONS = {
    "rdi_fixed_leader_source_flag": (
        "RDI fixed-leader sensor-source flag."
    ),
    "rdi_fixed_leader_source_and_available_flags": (
        "RDI fixed-leader sensor-source and sensor-available flags."
    ),
    "rdi_fixed_leader_source_requested_but_unavailable": (
        "RDI fixed-leader source flag requested a sensor, but the "
        "sensor-available flag was false."
    ),
    "rdi_fixed_leader_flags_unavailable": (
        "RDI fixed-leader sensor flags were unavailable or undecodable."
    ),
    "rdi_pressure_nonzero": "Decoded RDI pressure field contains non-zero values.",
    "rdi_pressure_all_zero": "Decoded RDI pressure field contains only zero values.",
    "rdi_pressure_all_zero_and_fixed_leader_flags": (
        "Decoded RDI pressure field contains only zero values and RDI "
        "fixed-leader flags do not confirm a pressure/depth sensor."
    ),
    "rdi_fixed_leader_depth_available_flag": (
        "RDI fixed-leader depth/pressure sensor-available flag."
    ),
}

_RDI_ATTR_DEFAULTS: dict[str, dict[str, str]] = {
    "c_sound": {
        "units": "m s-1",
        "long_name": "Speed of Sound",
        "standard_name": "speed_of_sound_in_sea_water",
        "measurement_type": "Derived",
        "comment": "Speed of sound used by the ADCP, decoded from the RDI variable leader.",
    },
    _RDI_TRANSDUCER_DEPTH: {
        "units": "m",
        "long_name": "RDI Transducer Depth",
        "positive": "down",
        "comment": (
            "RDI variable-leader depth field for the transducer head. The "
            "fixed-leader sensor flags indicate whether this came from the "
            "pressure/depth sensor or from the manual ED setting."
        ),
    },
    "pressure": {
        "units": "dbar",
        "long_name": "Pressure",
        "standard_name": "sea_water_pressure",
        "measurement_type": "Measured",
    },
    _RDI_PRESSURE_PLACEHOLDER: {
        "units": "dbar",
        "long_name": "RDI Pressure Placeholder",
        "measurement_type": "Placeholder",
        "comment": (
            "RDI pressure field is present in the ensemble but contains only "
            "zeros, which usually indicates that no pressure sensor was "
            "available or enabled."
        ),
    },
    _RDI_SALINITY_SETTING: {
        "units": "1e-3",
        "long_name": "RDI Salinity Setting",
        "measurement_type": "Configured",
        "comment": (
            "RDI variable-leader salinity field. This is normally a configured "
            "value used by the ADCP for sound-speed calculations, not a salinity "
            "measurement."
        ),
    },
    _RDI_TEMPERATURE_SETTING: {
        "units": "degree_C",
        "long_name": "RDI Temperature Setting",
        "measurement_type": "Configured",
        "comment": (
            "RDI variable-leader temperature field came from the manual ET "
            "setting because the fixed-leader sensor flags do not show an "
            "active temperature sensor source."
        ),
    },
    "salinity": {
        "units": "1e-3",
        "long_name": "ADCP Salinity",
        "standard_name": "sea_water_salinity",
        "measurement_type": "Measured",
        "comment": (
            "Salinity decoded from the RDI variable leader. The fixed-leader "
            "sensor flags indicate a conductivity/salinity sensor source; "
            "verify instrument configuration before treating this as CTD-quality data."
        ),
    },
    "temp": {
        "units": "degree_C",
        "long_name": "ADCP Temperature",
        "standard_name": "sea_water_temperature",
        "measurement_type": "Measured",
        "comment": (
            "Temperature reported by the ADCP variable leader, usually from "
            "the instrument's internal thermistor rather than an external CTD."
        ),
    },
    "vel": {
        "units": "m s-1",
        "long_name": "Water Velocity",
    },
}


def _set_measurement_type(attrs: dict[str, Any], value: str) -> None:
    """Set the compact SeaSenseLib measurement-type annotation."""
    attrs["measurement_type"] = value


def _rdi_flag(value: Any, bit: int) -> bool | None:
    """Return one RDI fixed-leader sensor flag bit, if it can be decoded."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        if set(text) <= {"0", "1"}:
            number = int(text, 2)
        else:
            number = int(text)
    except (TypeError, ValueError):
        return None

    return bool(number & (1 << bit))


def _sensor_state(ds: xr.Dataset, variable_name: str) -> dict[str, Any]:
    """Decode RDI EZ source/available flags for one environmental field."""
    bit = _RDI_SENSOR_BITS.get(variable_name)
    if bit is None:
        return {
            "source_flag": None,
            "available_flag": None,
            "source": "unknown",
            "basis": "rdi_fixed_leader_flags_unavailable",
        }

    source_flag = _rdi_flag(ds.attrs.get("sensors_src"), bit)
    available_flag = _rdi_flag(ds.attrs.get("sensors_avail"), bit)
    if source_flag is None:
        source = "unknown"
        basis = "rdi_fixed_leader_flags_unavailable"
    elif variable_name == "c_sound":
        if source_flag:
            source = "derived"
        else:
            source = "configured"
        basis = "rdi_fixed_leader_source_flag"
    elif source_flag and available_flag:
        source = "sensor"
        basis = "rdi_fixed_leader_source_and_available_flags"
    elif source_flag and available_flag is False:
        source = "configured_fallback"
        basis = "rdi_fixed_leader_source_requested_but_unavailable"
    elif source_flag:
        source = "unknown"
        basis = "rdi_fixed_leader_source_flag"
    else:
        source = "configured"
        basis = "rdi_fixed_leader_source_flag"

    return {
        "source_flag": source_flag,
        "available_flag": available_flag,
        "source": source,
        "basis": basis,
    }


def _read_rdi_import() -> tuple[Callable[..., xr.Dataset], str]:
    """Import the MHKiT DOLfYN RDI reader lazily."""
    try:
        from mhkit import dolfyn
    except ModuleNotFoundError as exc:
        if exc.name != "mhkit":
            raise
        try:
            import dolfyn  # type: ignore[no-redef]
        except ModuleNotFoundError as fallback_exc:
            raise ImportError(
                "RdiRawReader requires MHKiT with DOLfYN support. "
                'Install it with: pip install "mhkit[dolfyn]"'
            ) from fallback_exc
        source = "dolfyn.io.rdi.read_rdi"
    else:
        source = "mhkit.dolfyn.io.rdi.read_rdi"

    try:
        read_rdi = dolfyn.io.rdi.read_rdi
    except AttributeError as exc:
        raise ImportError(
            "The installed DOLfYN package does not expose io.rdi.read_rdi(). "
            'Please install a recent MHKiT build with: pip install "mhkit[dolfyn]"'
        ) from exc

    return read_rdi, source


class RdiRawReader(AbstractReader):
    """Read Teledyne RD Instruments (RDI) raw binary ADCP files.

    The reader delegates binary decoding to a tested RDI parser and keeps the
    returned xarray structure intact. SeaSenseLib only adds reader provenance,
    raw-metadata hints, and conservative variable mappings such as ``temp``
    -> ``temperature`` and ``c_sound`` -> ``speed_of_sound``.

    Velocity is intentionally preserved as vector variable ``vel``. Its
    component meaning depends on ``ds.attrs["coord_sys"]`` (for example beam,
    inst, ship, earth, or principal), so automatic CF component variables would
    be a scientific decision rather than a safe metadata cleanup.
    """

    def __init__(
        self,
        input_file: str,
        userdata: bool | str | None = None,
        nens: int | tuple[int, int] | None = None,
        debug: int | None = None,
        vmdas_search: bool = False,
        winriver: bool = False,
        search_num: int | None = None,
        show_decoder_output: bool = False,
        mapping: dict | None = None,
        **kwargs,
    ):
        """Initialize the RDI raw ADCP reader.

        Parameters
        ----------
        input_file
            Path to an RDI raw binary ADCP file, commonly ``.000``.
        userdata
            Passed to DOLfYN. Use ``True`` to search for a sibling
            ``*.userdata.json`` file, ``False`` to skip it, or a string path
            to use a specific metadata file. ``None`` keeps DOLfYN's default.
        nens
            Number of ensembles to read, or a start/stop tuple for DOLfYN
            versions that support sliced reads.
        debug
            DOLfYN debug level. ``None`` keeps DOLfYN's default.
        vmdas_search
            Ask DOLfYN to search for VMDAS navigation blocks when offsets are
            unreliable.
        winriver
            Force DOLfYN's WinRiver parsing path. DOLfYN normally detects this.
        search_num
            Optional DOLfYN search window for versions that expose it.
        show_decoder_output
            If True, let the backend decoder write progress messages to
            stdout. The default keeps SeaSenseLib reads quiet.
        mapping
            Additional SeaSenseLib variable mappings.
        **kwargs
            Base reader options such as ``perform_default_postprocessing`` and
            ``use_steps``.
        """
        self._userdata = userdata
        self._nens = nens
        self._debug = debug
        self._vmdas_search = vmdas_search
        self._winriver = winriver
        self._search_num = search_num
        self._show_decoder_output = show_decoder_output
        self._decoder_source = ""
        self._raw_metadata_blocks: dict[str, Any] = {}
        self._raw_metadata_variables: dict[str, Any] = {}
        super().__init__(input_file, mapping, **kwargs)
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...]:
        """Return supported RDI raw binary extensions."""
        return _SUPPORTED_EXTENSIONS

    @classmethod
    def reader_args(cls) -> list[dict]:
        return [
            cls._reader_arg(
                "userdata",
                "bool | path",
                None,
                "Pass DOLfYN userdata handling: true to search, false to skip, or a file path.",
            ),
            cls._reader_arg(
                "nens",
                "int",
                None,
                "Number of ensembles to read from the raw file.",
            ),
            cls._reader_arg(
                "debug",
                "int",
                None,
                "DOLfYN debug level.",
            ),
            cls._reader_arg(
                "vmdas_search",
                "bool",
                False,
                "Ask DOLfYN to search for VMDAS navigation blocks.",
            ),
            cls._reader_arg(
                "winriver",
                "bool",
                False,
                "Force DOLfYN's WinRiver parsing path.",
            ),
            cls._reader_arg(
                "search_num",
                "int",
                None,
                "DOLfYN search window for backends that expose it.",
            ),
            cls._reader_arg(
                "show_decoder_output",
                "bool",
                False,
                "Allow backend decoder progress messages on stdout.",
            ),
        ]

    def _load_data(self) -> xr.Dataset:
        """Load the RDI raw data and return an xarray Dataset."""
        read_rdi, source = _read_rdi_import()
        self._decoder_source = source
        ds = self._call_read_rdi(read_rdi)
        if not isinstance(ds, xr.Dataset):
            raise TypeError(
                f"DOLfYN returned {type(ds)!r}; expected xarray.Dataset."
            )

        ds = self._annotate_decoded_dataset(ds)
        self._raw_metadata_blocks = self._build_raw_metadata_blocks(ds)
        self._raw_metadata_variables = self._build_raw_variable_metadata(ds)
        return ds

    def _call_read_rdi(self, read_rdi: Callable[..., xr.Dataset]) -> xr.Dataset:
        """Call DOLfYN's RDI reader while tolerating small API changes."""
        kwargs: dict[str, Any] = {
            "userdata": self._userdata,
            "nens": self._nens,
            "vmdas_search": self._vmdas_search,
            "winriver": self._winriver,
        }
        if self._search_num is not None:
            kwargs["search_num"] = self._search_num

        signature = inspect.signature(read_rdi)
        parameters = signature.parameters
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in parameters.values()
        )

        if self._debug is not None:
            if "debug" in parameters:
                kwargs["debug"] = self._debug
            elif "debug_level" in parameters:
                kwargs["debug_level"] = self._debug
            elif accepts_kwargs:
                kwargs["debug"] = self._debug

        if not accepts_kwargs:
            kwargs = {key: value for key, value in kwargs.items() if key in parameters}

        if self._show_decoder_output:
            return read_rdi(self.input_file, **kwargs)

        captured_stdout = io.StringIO()
        try:
            with redirect_stdout(captured_stdout):
                return read_rdi(self.input_file, **kwargs)
        finally:
            output = captured_stdout.getvalue().strip()
            if output:
                logger.debug("Suppressed RDI decoder stdout:\n%s", output)

    def _annotate_decoded_dataset(self, ds: xr.Dataset) -> xr.Dataset:
        """Add SeaSenseLib provenance and conservative metadata defaults."""
        ds = self._rename_configuration_fields(ds)

        for variable_name, attrs in _RDI_ATTR_DEFAULTS.items():
            if variable_name not in ds:
                continue
            for attr_name, attr_value in attrs.items():
                ds[variable_name].attrs.setdefault(attr_name, attr_value)

        for variable_name in ds.data_vars:
            variable_attrs = ds[variable_name].attrs
            variable_attrs.setdefault("original_name", variable_name)
            if "units" in variable_attrs:
                variable_attrs.setdefault("original_units", variable_attrs["units"])

        if "range" in ds.coords:
            ds["range"].attrs.setdefault("units", "m")
            ds["range"].attrs.setdefault("long_name", "Profile Range")
            ds["range"].attrs.setdefault(
                "comment",
                "Distance from transducer to cell center, as decoded from raw data.",
            )
        return ds

    def _rename_configuration_fields(self, ds: xr.Dataset) -> xr.Dataset:
        """Avoid presenting RDI settings/fallback fields as measured variables."""
        rename_map = {}
        if "salinity" in ds and _sensor_state(ds, "salinity")["source"] != "sensor":
            rename_map["salinity"] = _RDI_SALINITY_SETTING
        if "temp" in ds and _sensor_state(ds, "temp")["source"] in {
            "configured",
            "configured_fallback",
        }:
            rename_map["temp"] = _RDI_TEMPERATURE_SETTING
        if "depth" in ds:
            rename_map["depth"] = _RDI_TRANSDUCER_DEPTH
        if "pressure" in ds and self._is_zero_placeholder(ds["pressure"]):
            rename_map["pressure"] = _RDI_PRESSURE_PLACEHOLDER

        renamed = ds.rename(rename_map) if rename_map else ds
        for original_name, renamed_name in rename_map.items():
            attrs = renamed[renamed_name].attrs
            attrs.setdefault("original_name", original_name)
            if "units" in attrs:
                attrs.setdefault("original_units", attrs["units"])
            if renamed_name == _RDI_SALINITY_SETTING:
                attrs.pop("standard_name", None)
                attrs.update(_RDI_ATTR_DEFAULTS[_RDI_SALINITY_SETTING])
            if renamed_name == _RDI_TEMPERATURE_SETTING:
                attrs.pop("standard_name", None)
                attrs.update(_RDI_ATTR_DEFAULTS[_RDI_TEMPERATURE_SETTING])
            if renamed_name == _RDI_TRANSDUCER_DEPTH:
                attrs.pop("standard_name", None)
                attrs.update(_RDI_ATTR_DEFAULTS[_RDI_TRANSDUCER_DEPTH])
            if renamed_name == _RDI_PRESSURE_PLACEHOLDER:
                attrs.pop("standard_name", None)
                attrs.update(_RDI_ATTR_DEFAULTS[_RDI_PRESSURE_PLACEHOLDER])

        self._apply_environmental_source_attrs(renamed)
        return renamed

    def _apply_environmental_source_attrs(self, ds: xr.Dataset) -> None:
        """Attach decoded RDI sensor-source flags to environmental fields."""
        for original_name, variable_name in (
            ("c_sound", "c_sound"),
            (
                "temp",
                _RDI_TEMPERATURE_SETTING
                if _RDI_TEMPERATURE_SETTING in ds
                else "temp",
            ),
            (
                "salinity",
                _RDI_SALINITY_SETTING
                if _RDI_SALINITY_SETTING in ds
                else "salinity",
            ),
            ("depth", _RDI_TRANSDUCER_DEPTH),
            ("heading", "heading"),
            ("pitch", "pitch"),
            ("roll", "roll"),
        ):
            if variable_name not in ds:
                continue
            state = _sensor_state(ds, original_name)
            attrs = ds[variable_name].attrs
            attrs["sensor_source"] = state["source"]
            attrs["sensor_source_basis"] = state["basis"]
            attrs["rdi_sensor_source_flag"] = self._flag_attr(state["source_flag"])
            attrs["rdi_sensor_available_flag"] = self._flag_attr(
                state["available_flag"]
            )

            if original_name == "c_sound":
                if state["source"] == "configured":
                    _set_measurement_type(attrs, "Configured")
                    attrs["comment"] = (
                        "Speed of sound decoded from the RDI variable leader. "
                        "The fixed-leader sensor-source flag indicates the "
                        "manual EC setting was used."
                    )
                elif state["source"] == "derived":
                    _set_measurement_type(attrs, "Derived")
                    attrs["comment"] = (
                        "Speed of sound decoded from the RDI variable leader. "
                        "The fixed-leader sensor-source flag indicates the ADCP "
                        "calculated it from environmental fields."
                    )

            if original_name == "temp" and variable_name == "temp":
                if state["source"] == "sensor":
                    _set_measurement_type(attrs, "Measured")
                    attrs["comment"] = (
                        "Temperature reported by the RDI variable leader. The "
                        "fixed-leader sensor flags indicate the transducer "
                        "temperature sensor was used."
                    )
                elif state["source"] == "unknown":
                    _set_measurement_type(attrs, "Unknown")
                    attrs["comment"] = (
                        "Temperature reported by the RDI variable leader. The "
                        "fixed-leader sensor-source flags were not available, "
                        "so SeaSenseLib cannot determine whether this came "
                        "from ET or from the temperature sensor."
                    )

            if original_name == "salinity" and variable_name == "salinity":
                if "units" in attrs:
                    attrs.setdefault("original_units", attrs["units"])
                attrs["units"] = _RDI_ATTR_DEFAULTS["salinity"]["units"]
                _set_measurement_type(attrs, "Measured")
                attrs["comment"] = (
                    "Salinity decoded from the RDI variable leader. The "
                    "fixed-leader sensor flags indicate a conductivity/salinity "
                    "sensor source; verify instrument configuration before "
                    "treating this as CTD-quality data."
                )

            if original_name == "depth" and variable_name == _RDI_TRANSDUCER_DEPTH:
                if state["source"] == "sensor":
                    _set_measurement_type(attrs, "Measured")
                    attrs["comment"] = (
                        "RDI variable-leader transducer depth. The fixed-leader "
                        "sensor flags indicate this came from the internal "
                        "pressure/depth sensor."
                    )
                elif state["source"] == "configured_fallback":
                    _set_measurement_type(attrs, "Configured")
                    attrs["comment"] = (
                        "RDI variable-leader transducer depth. The fixed-leader "
                        "sensor-source flag requested the pressure/depth sensor, "
                        "but the sensor-available flag is false, so the ADCP "
                        "falls back to the manual ED setting."
                    )
                elif state["source"] == "configured":
                    _set_measurement_type(attrs, "Configured")
                    attrs["comment"] = (
                        "RDI variable-leader transducer depth. The fixed-leader "
                        "sensor-source flag indicates the manual ED setting was used."
                    )

            if original_name in {"heading", "pitch", "roll"}:
                label = original_name.capitalize()
                if state["source"] == "sensor":
                    _set_measurement_type(attrs, "Measured")
                    attrs["comment"] = (
                        f"{label} decoded from the RDI variable leader. The "
                        "fixed-leader sensor flags indicate an instrument "
                        "sensor was used."
                    )
                elif state["source"] == "configured_fallback":
                    _set_measurement_type(attrs, "Configured")
                    attrs["comment"] = (
                        f"{label} decoded from the RDI variable leader. The "
                        "fixed-leader sensor-source flag requested a sensor, "
                        "but the sensor-available flag is false, so the ADCP "
                        "falls back to a configured value."
                    )
                elif state["source"] == "configured":
                    _set_measurement_type(attrs, "Configured")
                    attrs["comment"] = (
                        f"{label} decoded from the RDI variable leader. The "
                        "fixed-leader sensor-source flag indicates a configured "
                        "value was used."
                    )
                elif state["source"] == "unknown":
                    _set_measurement_type(attrs, "Unknown")
                    attrs["comment"] = (
                        f"{label} decoded from the RDI variable leader. The "
                        "fixed-leader sensor flags were not available, so "
                        "SeaSenseLib cannot determine the source."
                    )

        if "pressure" in ds:
            attrs = ds["pressure"].attrs
            depth_state = _sensor_state(ds, "depth")
            attrs["sensor_source"] = "sensor"
            attrs["rdi_sensor_source_flag"] = "unknown"
            basis = (
                "rdi_fixed_leader_depth_available_flag"
                if depth_state["available_flag"]
                else "rdi_pressure_nonzero"
            )
            attrs["sensor_source_basis"] = basis
            attrs["rdi_sensor_available_flag"] = self._flag_attr(
                depth_state["available_flag"]
            )

        if _RDI_PRESSURE_PLACEHOLDER in ds:
            attrs = ds[_RDI_PRESSURE_PLACEHOLDER].attrs
            depth_state = _sensor_state(ds, "depth")
            attrs["sensor_source"] = "placeholder"
            attrs["rdi_sensor_source_flag"] = "unknown"
            basis = (
                "rdi_pressure_all_zero"
                if depth_state["available_flag"] is None
                else "rdi_pressure_all_zero_and_fixed_leader_flags"
            )
            attrs["sensor_source_basis"] = basis
            attrs["rdi_sensor_available_flag"] = self._flag_attr(
                depth_state["available_flag"]
            )

    @staticmethod
    def _flag_attr(value: bool | None) -> str:
        """Serialize optional booleans safely for netCDF attrs."""
        if value is None:
            return "unknown"
        return "true" if value else "false"

    @staticmethod
    def _is_zero_placeholder(array: xr.DataArray) -> bool:
        """Return True when a decoded field only contains zero-like values."""
        values = np.asarray(array.values)
        if values.size == 0:
            return False
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return False
        return bool(np.all(finite == 0))

    def _build_raw_metadata_blocks(self, ds: xr.Dataset) -> dict[str, Any]:
        """Build opaque raw metadata blocks for the finalization stage."""
        return {
            "configuration": {
                "decoder": self._decoder_source,
                "reader_options": self._read_options(),
            },
            "sensor_sources": self._sensor_source_summary(ds),
            "mapping_notes": self._mapping_notes(ds),
        }

    def _sensor_source_summary(self, ds: xr.Dataset) -> dict[str, Any]:
        """Return decoded RDI sensor-source flags for raw metadata."""
        return {
            "note": (
                "sensor_source values are compact SeaSenseLib annotations. "
                "sensor_source_basis values and rdi_* flag attributes are "
                "RDI-specific evidence from decoded fixed-leader fields. "
                "These annotations are not external standard terms."
            ),
            "bit_mapping": dict(_RDI_SENSOR_BITS),
            "definitions": {
                "sensor_source": _SENSOR_SOURCE_DESCRIPTIONS,
                "sensor_source_basis": _RDI_SENSOR_BASIS_DESCRIPTIONS,
                "bit_mapping": (
                    "RDI fixed-leader sensor-source fields follow the "
                    "EZcdhprst order; SeaSenseLib maps c,d,h,p,r,s,t to bits "
                    "6,5,4,3,2,1,0."
                ),
            },
            "raw_flags": {
                "sensors_src": ds.attrs.get("sensors_src"),
                "sensors_avail": ds.attrs.get("sensors_avail"),
            },
            "fields": {
                name: _sensor_state(ds, name)
                for name in _RDI_SENSOR_BITS
            },
        }

    def _build_raw_variable_metadata(self, ds: xr.Dataset) -> dict[str, Any]:
        """Summarize variables without copying data values."""
        variables: dict[str, Any] = {}
        for name in list(ds.coords) + list(ds.data_vars):
            array = ds[name]
            attrs = dict(array.attrs)
            variable_metadata = {"dims": list(array.dims)}
            for attr_name in (
                "original_name",
                "units",
                "original_units",
                "measurement_type",
                "sensor_source",
                "sensor_source_basis",
                "rdi_sensor_source_flag",
                "rdi_sensor_available_flag",
            ):
                if attr_name in attrs:
                    variable_metadata[attr_name] = attrs[attr_name]
            variables[name] = variable_metadata
        return variables

    def _postprocess_after_pipeline(self, ds: xr.Dataset) -> xr.Dataset:
        """Expose raw-variable metadata under mapped variable names as well."""
        if "raw_metadata" not in ds.attrs or not self._processing_metadata:
            return ds

        variable_mappings = self._processing_metadata.get("variable_mappings")
        if not isinstance(variable_mappings, dict) or not variable_mappings:
            return ds

        try:
            raw_metadata = json.loads(ds.attrs["raw_metadata"])
        except (TypeError, json.JSONDecodeError):
            return ds

        variables = raw_metadata.get("variables")
        if not isinstance(variables, dict):
            return ds

        for original_name, mapped_name in variable_mappings.items():
            if original_name not in variables or mapped_name in variables:
                continue
            source_metadata = variables[original_name]
            if not isinstance(source_metadata, dict):
                continue
            mapped_metadata = dict(source_metadata)
            mapped_metadata.setdefault("original_name", original_name)
            if mapped_name in ds:
                attrs = ds[mapped_name].attrs
                if "units" in attrs:
                    mapped_metadata["units"] = attrs["units"]
                if "original_units" in attrs:
                    mapped_metadata.setdefault("original_units", attrs["original_units"])
            variables[mapped_name] = mapped_metadata

        ds.attrs["raw_metadata"] = json.dumps(
            raw_metadata,
            ensure_ascii=False,
            default=str,
        )
        return ds

    def _read_options(self) -> dict[str, Any]:
        """Return raw read options for provenance."""
        return {
            "userdata": self._userdata,
            "nens": self._nens,
            "debug": self._debug,
            "vmdas_search": self._vmdas_search,
            "winriver": self._winriver,
            "search_num": self._search_num,
            "show_decoder_output": self._show_decoder_output,
        }

    def _mapping_notes(self, ds: xr.Dataset) -> dict[str, Any]:
        """Describe conservative mapping choices without duplicating flags."""
        coord_sys = str(ds.attrs.get("coord_sys", "")).lower() or None
        safe_mappings = {}
        for source, canonical in (
            ("temp", params.TEMPERATURE),
            ("c_sound", params.SPEED_OF_SOUND),
            ("salinity", params.SALINITY),
            ("pressure", params.PRESSURE),
        ):
            if source in ds:
                safe_mappings[source] = canonical

        setting_fields = {}
        for original, renamed in (
            ("temp", _RDI_TEMPERATURE_SETTING),
            ("salinity", _RDI_SALINITY_SETTING),
            ("depth", _RDI_TRANSDUCER_DEPTH),
        ):
            if renamed in ds:
                setting_fields[original] = renamed

        placeholder_fields = {}
        if _RDI_PRESSURE_PLACEHOLDER in ds:
            placeholder_fields["pressure"] = _RDI_PRESSURE_PLACEHOLDER

        not_mapped: dict[str, str] = {}
        if setting_fields:
            not_mapped.update(
                {
                    original: (
                        f"Kept as {renamed}; RDI flags indicate a configured, "
                        "fallback, or instrument-head value rather than an "
                        "unambiguous canonical measurement."
                    )
                    for original, renamed in setting_fields.items()
                }
            )
        if placeholder_fields:
            not_mapped.update(
                {
                    original: (
                        f"Kept as {renamed}; decoded values are all zero and "
                        "are treated as a placeholder."
                    )
                    for original, renamed in placeholder_fields.items()
                }
            )
        if "vel" in ds:
            not_mapped["vel"] = (
                "Kept as vector variable vel; component splitting depends on "
                "coord_sys and can require reviewed rotation or deployment "
                "metadata."
            )

        return {
            "safe_reader_mappings": safe_mappings,
            "not_mapped": not_mapped,
            "velocity": {
                "source_variable": "vel",
                "coordinate_system": coord_sys,
                "cf_component_mapping": (
                    "not_applied"
                    if coord_sys != "earth"
                    else "possible_after_review"
                ),
            },
        }

    @classmethod
    def format_mappings(cls) -> dict[str, list[str]]:
        """Return conservative RDI-to-SeaSenseLib variable mappings."""
        return {
            params.TEMPERATURE: ["temp"],
            params.SPEED_OF_SOUND: ["c_sound"],
            params.PRESSURE: ["pressure"],
        }

    @classmethod
    def format_key(cls) -> str:
        return "rdi-raw"

    @classmethod
    def format_name(cls) -> str:
        return "RDI ADCP raw"

    @classmethod
    def file_extension(cls) -> str | None:
        return ".000"

    @classmethod
    def file_extensions(cls) -> tuple[str, ...]:
        return _SUPPORTED_EXTENSIONS


__all__ = ["RdiRawReader"]
