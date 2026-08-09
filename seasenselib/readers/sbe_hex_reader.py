"""Reader wrapper and helper functions for Sea-Bird SBE HEX files.

Supports two instrument families, detected automatically from the file header:

* **SBE37** family (SBE37SM, SBE37SMP, …) — existing support, unchanged.
* **SBE911plus** family (SBE 911+/917+ CTD) — added in this module.

The public entry point for both families is :class:`SbeHexReader`.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
import logging
from pathlib import Path
import re
import warnings
from types import SimpleNamespace
from typing import Any, Dict, Literal, Union

import numpy as np
import pandas as pd
import xarray as xr

import seasenselib.parameters as params
from seasenselib.readers.base import AbstractReader


logger = logging.getLogger(__name__)

_SENSOR_ID_RE = re.compile(r"<Sensor\b[^>]*\bid=(['\"])(?P<sensor_id>[^'\"]+)\1")
_DEVICE_TYPE_RE = re.compile(r"\bDeviceType=(['\"])(?P<device_type>[^'\"]+)\1")
_HEADER_VALUE_RE = re.compile(r"<(?P<tag>[A-Za-z0-9_]+)>(?P<value>.*?)</(?P=tag)>")


_SBE37_FORMAT0_HEX_LENGTHS = {
    "temperature": 6,
    "conductivity": 6,
    "pressure": 6,
    "temperature compensation": 4,
    "SBE63 oxygen phase": 6,
    "SBE63 oxygen temperature": 6,
    "date time": 8,
}

_SBE_HEX_VARIABLE_SENSOR_TYPES = {
    "temp": "temperature",
    "cond": "conductivity",
    "press": "pressure",
    "oxygen": "oxygen",
    "oxygen_ml_l": "oxygen",
    "oxygen_phase": "oxygen",
    "oxygen_temp": "oxygen",
}


@dataclass(frozen=True)
class SensorSpec:
    """How to turn one XMLCON sensor element into calibration coefficients.

    ``coeff_class`` is the seabirdscientific coefficient dataclass; ``None``
    when no upstream class exists. ``tag_map`` maps XMLCON leaf tag names to
    dataclass field names. ``variable`` is the output variable stem, or
    ``None`` for sensors that are metadata-only.
    """

    coeff_class: type | None
    tag_map: dict
    variable: str | None


@dataclass
class SensorInfo:
    """Calibration and role metadata for one XMLCON sensor channel."""

    sensor_type: str
    variable: str | None
    serial_number: str | None
    calibration_date: str | None
    coefficients: Any
    role: str | None = None
    offset: float | None = None
    slope: float | None = None
    name: str | None = None


@dataclass
class XmlconMap:
    """Parsed SBE911+ xmlcon: per-channel sensor info and instrument-level settings."""

    sensors: dict  # dict[tuple[str, int], SensorInfo]
    meta: dict


_XMLCON_SKIP = frozenset({"NotInUse"})

_N_FREQ = 5
_N_VOLT = 8
_SPAR_IDX = 14


def channel_of(index: int) -> tuple:
    """Map an xmlcon ``Sensor index`` attribute to a ``(kind, channel_number)`` tuple.

    Raises :exc:`ValueError` if the index falls outside the SBE911+ layout.
    """
    if index < _N_FREQ:
        return ("frequency", index)
    if index < _N_FREQ + _N_VOLT:
        return ("volt", index - _N_FREQ)
    if index == _SPAR_IDX:
        return ("spar", 0)
    raise ValueError(
        f"XMLCON sensor index {index} is outside the SBE911+ layout "
        f"(frequency 0–{_N_FREQ - 1}, volt {_N_FREQ}–{_N_FREQ + _N_VOLT - 1}, "
        f"spar {_SPAR_IDX})."
    )


def detect_sbe_hex_family(hex_path: Union[str, Path]) -> Literal["sbe37", "sbe911plus"]:
    """Return the instrument family by inspecting line 1 of the hex file.

    The SBE 911plus/917plus always starts with ``* Sea-Bird SBE 9 Data File:``.
    Every other recognised SBE HEX variant is treated as SBE37 family.
    """
    with open(hex_path, "r", encoding="latin-1") as f:
        first = f.readline().strip()
    if first == "* Sea-Bird SBE 9 Data File:":
        return "sbe911plus"
    return "sbe37"


def _parse_nmea_degrees(value: str) -> float | None:
    """Convert an NMEA lat/lon string such as '65 13.78 N' to decimal degrees."""
    try:
        parts = value.strip().split()
        if len(parts) == 3:
            degrees = float(parts[0])
            minutes = float(parts[1])
            hemisphere = parts[2].upper()
            decimal = degrees + minutes / 60.0
            if hemisphere in ("S", "W"):
                decimal = -decimal
            return decimal
    except (ValueError, IndexError):
        pass
    return None


def parse_hex_header_sbe911(hex_path: Union[str, Path]) -> dict:
    """Parse the ``* key = value`` header of an SBE 911plus HEX file.

    Reads with ``latin-1`` encoding to handle ship names with non-ASCII
    characters.  Double-asterisk ``** key: value`` lines are collected into
    ``user_header``.

    Returns
    -------
    dict
        Keys: ``bytes_per_scan``, ``voltage_words``, ``scans_averaged``,
        ``upload_time`` (:class:`datetime.datetime`), ``nmea_latitude``,
        ``nmea_longitude``, ``store_lat_lon`` (bool), ``sample_interval``
        (seconds, float), ``user_header`` (dict).
    """
    header: dict = {
        "bytes_per_scan": None,
        "voltage_words": None,
        "scans_averaged": None,
        "upload_time": None,
        "nmea_latitude": None,
        "nmea_longitude": None,
        "store_lat_lon": False,
        "nmea_time_added": False,
        "store_system_time": False,
        "sample_interval": None,
        "user_header": {},
    }

    with open(hex_path, "r", encoding="latin-1") as f:
        for line in f:
            if not line.startswith("*"):
                break
            stripped = line[1:].strip()

            # Double-asterisk user-header lines
            if stripped.startswith("*"):
                user_line = stripped[1:].strip()
                if ":" in user_line:
                    key, _, val = user_line.partition(":")
                    key = key.strip()
                    val = val.strip()
                    if key:
                        try:
                            header["user_header"][key] = int(val)
                        except ValueError:
                            header["user_header"][key] = val
                continue

            # Bare flag lines (no "=")
            if "=" not in stripped:
                if stripped == "Append System Time to Every Scan":
                    header["store_system_time"] = True
                continue

            key, _, val = stripped.partition("=")
            key = key.strip()
            val = val.strip()

            if key == "Number of Bytes Per Scan":
                header["bytes_per_scan"] = int(val)
            elif key == "Number of Voltage Words":
                header["voltage_words"] = int(val)
            elif key in (
                "Number of Scans Averaged by the Deck Unit",
                "number of scans to average",
            ):
                parsed = int(val)
                if header["scans_averaged"] is None:
                    header["scans_averaged"] = parsed
            elif key == "System UpLoad Time":
                for fmt in ("%b %d %Y %H:%M:%S", "%b %d %Y  %H:%M:%S"):
                    try:
                        header["upload_time"] = datetime.datetime.strptime(val, fmt)
                        break
                    except ValueError:
                        continue
            elif key == "NMEA Latitude":
                header["nmea_latitude"] = _parse_nmea_degrees(val)
            elif key == "NMEA Longitude":
                header["nmea_longitude"] = _parse_nmea_degrees(val)
            elif key == "Store Lat/Lon Data":
                header["store_lat_lon"] = "Append" in val

    if header["scans_averaged"] is not None:
        header["sample_interval"] = header["scans_averaged"] / 24.0

    return header


def _sbe_hex_field(name: str, hex_chars: int) -> SimpleNamespace:
    """Create one field description inside a raw SBE hex data row."""
    return SimpleNamespace(name=name, hex_chars=hex_chars)


def _sbe_hex_layout(
    *,
    name: str,
    instrument_family: str,
    decoder_backend: str,
    fields: tuple[SimpleNamespace, ...],
) -> SimpleNamespace:
    """Create a supported raw SBE hex data-row layout description.

    This is intentionally small for now. Future layouts should be added by
    creating another layout detector and, only if needed, another decoder
    backend. The calibration/xarray building code should not need to know the
    byte positions of each raw hex row.
    """
    return SimpleNamespace(
        name=name,
        instrument_family=instrument_family,
        decoder_backend=decoder_backend,
        fields=fields,
        expected_hex_chars=sum(field.hex_chars for field in fields),
    )


def _is_sbe37_instrument_type(instrument_type) -> bool:
    name = getattr(instrument_type, "name", "")
    value = getattr(instrument_type, "value", "")
    return name.startswith("SBE37") or str(value).startswith("37-")


def detect_sbe_hex_layout(
    header_info: dict,
    enabled_sensors_list: list[str],
    instrument_type,
    *,
    family: str = "sbe37",
) -> SimpleNamespace:
    """Detect the raw data-row layout before decoding.

    For SBE37 format-0, the layout is derived from ``enabled_sensors_list``
    and cross-checked against ``header_info['sample_length']``.

    For SBE911plus, the layout is derived from ``header_info['bytes_per_scan']``,
    ``header_info['voltage_words']``, and ``header_info['store_lat_lon']``.
    The cross-check against ``bytes_per_scan`` raises on mismatch.

    ``TxRealTime`` is treated as acquisition metadata for SBE37; the actual
    safety checks are the enabled sensors, ``SampleLength``, and per-line hex
    length validation in :func:`_read_hex_file_fast`.
    """
    if family == "sbe911plus":
        return _detect_sbe911plus_layout(header_info)

    if not _is_sbe37_instrument_type(instrument_type):
        raise ValueError(
            f"No SBE HEX layout detector is implemented for {instrument_type}. "
            "Add a new SbeHexLayout detector/decoder for this instrument family."
        )

    fields = [
        _sbe_hex_field(
            "temperature",
            _SBE37_FORMAT0_HEX_LENGTHS["temperature"],
        ),
        _sbe_hex_field(
            "conductivity",
            _SBE37_FORMAT0_HEX_LENGTHS["conductivity"],
        ),
    ]
    layout_tokens = ["temp", "cond"]

    if "oxygen" in enabled_sensors_list:
        fields.extend(
            [
                _sbe_hex_field(
                    "SBE63 oxygen phase",
                    _SBE37_FORMAT0_HEX_LENGTHS["SBE63 oxygen phase"],
                ),
                _sbe_hex_field(
                    "SBE63 oxygen temperature",
                    _SBE37_FORMAT0_HEX_LENGTHS["SBE63 oxygen temperature"],
                ),
            ]
        )
        layout_tokens.append("oxygen")

    if "pressure" in enabled_sensors_list:
        fields.extend(
            [
                _sbe_hex_field(
                    "pressure",
                    _SBE37_FORMAT0_HEX_LENGTHS["pressure"],
                ),
                _sbe_hex_field(
                    "temperature compensation",
                    _SBE37_FORMAT0_HEX_LENGTHS["temperature compensation"],
                ),
            ]
        )
        layout_tokens.append("press")

    fields.append(_sbe_hex_field("date time", _SBE37_FORMAT0_HEX_LENGTHS["date time"]))

    layout = _sbe_hex_layout(
        name=f"sbe37_format0_{'_'.join(layout_tokens)}_time",
        instrument_family="SBE37",
        decoder_backend="seabirdscientific.read_hex",
        fields=tuple(fields),
    )

    sample_length = header_info.get("sample_length")
    if sample_length is not None and sample_length * 2 != layout.expected_hex_chars:
        raise ValueError(
            f"Header SampleLength={sample_length} bytes does not match detected "
            f"layout {layout.name} ({layout.expected_hex_chars // 2} bytes). "
            "If this is a valid file, add a new SbeHexLayout detector/decoder."
        )

    return layout


def _detect_sbe911plus_layout(header_info: dict) -> SimpleNamespace:
    """Build the SBE 911plus hex data-row layout from header metadata.

    Layout formula (all values from the file header):
    - 5 frequency channels × 3 bytes each = 15 bytes (T1, C1, P, T2, C2)
    - ``voltage_words`` × 3 bytes each (each word encodes two ext-volt values)
    - 7 bytes NMEA lat/lon when ``store_lat_lon`` is True
    - 3 bytes status + data-integrity trailer

    The total must equal ``bytes_per_scan``.  A mismatch raises :exc:`ValueError`
    rather than silently skipping the check.
    """
    freq_channels = 5  # 911+ always has 5 frequency channels (T1, C1, P, T2, C2)
    volt_words = header_info.get("voltage_words")
    store_lat_lon = header_info.get("store_lat_lon", False)
    nmea_time_added = header_info.get("nmea_time_added", False)
    store_system_time = header_info.get("store_system_time", False)
    bytes_per_scan = header_info.get("bytes_per_scan")

    if volt_words is None:
        raise ValueError(
            "Cannot build SBE 911plus layout: 'Number of Voltage Words' not found in header."
        )

    _FREQ_NAMES = [
        "temperature",
        "conductivity",
        "digiquartz pressure",
        "secondary temperature",
        "secondary conductivity",
    ]
    fields = [_sbe_hex_field(name, 6) for name in _FREQ_NAMES[:freq_channels]]
    for i in range(volt_words):
        fields.append(_sbe_hex_field(f"volt_word_{i}", 6))
    if store_lat_lon:
        fields.append(_sbe_hex_field("nmea_location", 14))
    if nmea_time_added:
        fields.append(_sbe_hex_field("nmea_time", 8))
    fields.append(_sbe_hex_field("status_integrity", 6))
    if store_system_time:
        fields.append(_sbe_hex_field("system_time", 8))

    name_parts = [f"f{freq_channels}", f"v{volt_words}"]
    if store_lat_lon:
        name_parts.append("nmea")
    if nmea_time_added:
        name_parts.append("ntime")
    if store_system_time:
        name_parts.append("stime")
    layout = _sbe_hex_layout(
        name=f"sbe911plus_{'_'.join(name_parts)}",
        instrument_family="sbe911plus",
        decoder_backend="seabirdscientific.read_hex",
        fields=tuple(fields),
    )

    if bytes_per_scan is not None and bytes_per_scan * 2 != layout.expected_hex_chars:
        raise ValueError(
            f"Header 'Number of Bytes Per Scan'={bytes_per_scan} gives "
            f"{bytes_per_scan * 2} expected hex chars, but the derived layout "
            f"'{layout.name}' totals {layout.expected_hex_chars} chars. "
            "Check FrequencyChannelsSuppressed, VoltageWordsSuppressed, and "
            "'Store Lat/Lon Data' in the header."
        )

    return layout


def _normalise_sensor_id(sensor_id: str) -> str | None:
    """Map SBE header sensor ids to the internal sensor names used here."""
    sensor_key = re.sub(r"[\s_-]+", "", sensor_id).lower()
    sensor_aliases = {
        "temperature": "temperature",
        "conductivity": "conductivity",
        "pressure": "pressure",
        "oxygen": "oxygen",
        "sbe63": "oxygen",
    }
    return sensor_aliases.get(sensor_key)


def _parse_bool_text(value: str) -> bool | None:
    value = value.strip().lower()
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    return None


def _parse_float_text(value: str) -> float | None:
    """Parse a numeric SBE header value, returning None if unavailable."""
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None


def _read_sbe_hex_raw_header(hex_file: Union[str, Path]) -> str | None:
    """Read the SBE HEX header verbatim up to the data section."""
    lines = []
    with Path(hex_file).open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("*") and lines:
                break
            if line.strip().startswith("*END*"):
                lines.append(line.rstrip("\n"))
                break
            if line.startswith("*"):
                lines.append(line.rstrip("\n"))

    if not lines:
        return None
    return "\n".join(lines)


def _find_sbe_hex_xmlcon_path(hex_file: Union[str, Path]) -> Path | None:
    """Find a companion XMLCON file for an SBE HEX file, if one exists."""
    hex_path = Path(hex_file)
    candidates = [
        hex_path.with_suffix(".xmlcon"),
        hex_path.with_suffix(".XMLCON"),
        hex_path.with_suffix(".con"),
        hex_path.with_suffix(".CON"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _normalise_sbe_hex_calibration_info(sensor_info: dict) -> dict:
    """Return a JSON-friendly calibration record."""
    coefficients = dict(sensor_info.get("coefficients", {}) or {})
    record = {
        "type": sensor_info.get("type"),
        "format": sensor_info.get("format"),
        "coefficients": coefficients,
    }

    serial_number = (
        sensor_info.get("serial_number")
        or sensor_info.get("serialnum")
        or coefficients.get("serialnum")
    )
    calibration_date = (
        sensor_info.get("calibration_date")
        or sensor_info.get("caldate")
        or coefficients.get("caldate")
    )
    if serial_number is not None:
        record["serial_number"] = serial_number
    if calibration_date is not None:
        record["calibration_date"] = calibration_date
    if sensor_info.get("metadata"):
        record["metadata"] = sensor_info["metadata"]
    if sensor_info.get("index") is not None:
        record["index"] = sensor_info["index"]
    return {key: value for key, value in record.items() if value is not None}


def _sbe_hex_calibration_block(header_info: dict, xmlcon_info: dict | None) -> dict:
    """Build structured calibration metadata from HEX and XMLCON sources."""
    calibration = {}

    header_coefficients = header_info.get("calibration_coefficients") or {}
    if header_coefficients:
        calibration["hex_header"] = {
            sensor_type: _normalise_sbe_hex_calibration_info(sensor_info)
            for sensor_type, sensor_info in header_coefficients.items()
        }

    if xmlcon_info:
        calibration["xmlcon"] = {
            sensor_info["type"]: _normalise_sbe_hex_calibration_info(sensor_info)
            for sensor_info in xmlcon_info.get("sensors", {}).values()
        }

    return calibration


def _sbe_hex_raw_metadata_blocks(
    header_info: dict,
    xmlcon_info: dict | None,
) -> dict:
    """Build SeaSenseLib raw metadata blocks for SBE HEX files."""
    attributes = {
        "enabled_sensors": header_info.get("enabled_sensors", []),
        "device_type": header_info.get("device_type"),
        "sample_length": header_info.get("sample_length"),
        "tx_real_time": header_info.get("tx_real_time"),
        "reference_pressure": header_info.get("reference_pressure"),
    }
    attributes = {
        key: value
        for key, value in attributes.items()
        if value is not None and value != []
    }

    if xmlcon_info and xmlcon_info.get("xmlcon_path"):
        attributes["xmlcon_file"] = str(xmlcon_info["xmlcon_path"])

    configuration = {}
    output_flags = header_info.get("output_flags") or {}
    if output_flags:
        configuration["output_flags"] = output_flags

    calibration = _sbe_hex_calibration_block(header_info, xmlcon_info)

    blocks = {}
    if attributes:
        blocks["attributes"] = attributes
    if configuration:
        blocks["configuration"] = configuration
    if calibration:
        blocks["calibration"] = calibration
    return blocks


def _sbe_hex_raw_variable_metadata(
    header_info: dict,
    xmlcon_info: dict | None,
) -> dict:
    """Build variable-level raw metadata for SBE HEX output variables."""
    variables = {}
    header_coefficients = header_info.get("calibration_coefficients") or {}
    xmlcon_sensors = {}
    if xmlcon_info:
        xmlcon_sensors = {
            sensor_info["type"]: sensor_info
            for sensor_info in xmlcon_info.get("sensors", {}).values()
        }

    for variable_name, sensor_type in _SBE_HEX_VARIABLE_SENSOR_TYPES.items():
        sensor_info = header_coefficients.get(sensor_type) or xmlcon_sensors.get(
            sensor_type
        )
        if not sensor_info and sensor_type not in header_info.get(
            "enabled_sensors", []
        ):
            continue

        metadata = {"sensor_type": sensor_type}
        normalised = _normalise_sbe_hex_calibration_info(sensor_info or {})
        for key in ("serial_number", "calibration_date", "format", "index"):
            if key in normalised:
                metadata[key] = normalised[key]
        variables[variable_name] = metadata

    return variables


def _select_sbe37_instrument_type(
    instrument_data_module,
    device_type: str | None = None,
    instrument_type=None,
):
    """Select the closest seabirdscientific SBE37 instrument enum."""
    instrument_type_enum = instrument_data_module.InstrumentType

    if instrument_type is not None:
        if isinstance(instrument_type, instrument_type_enum):
            return instrument_type

        selected = _instrument_type_from_text(
            instrument_data_module, str(instrument_type)
        )
        if selected is None:
            valid_names = ", ".join(
                item.name
                for item in instrument_type_enum
                if item.name.startswith("SBE37")
            )
            raise ValueError(
                f"Unsupported SBE37 instrument_type '{instrument_type}'. "
                f"Use one of: {valid_names}"
            )
        return selected

    selected = _instrument_type_from_text(instrument_data_module, device_type)
    if selected is None:
        valid_names = ", ".join(
            item.name for item in instrument_type_enum if item.name.startswith("SBE37")
        )
        raise ValueError(
            f"Unrecognised SBE37 device_type '{device_type}' in hex header. "
            f"Supported types: {valid_names}. "
            "Pass instrument_type= explicitly if this is a valid SBE37 file."
        )
    return selected


def _instrument_type_from_text(instrument_data_module, text: str | None):
    if not text:
        return None

    normalised = re.sub(r"[^A-Z0-9]", "", text.upper())
    instrument_type_enum = instrument_data_module.InstrumentType
    markers = [
        ("SBE37SMPODO", "SBE37SMPODO"),
        ("37SMPODO", "SBE37SMPODO"),
        ("SBE37IMPODO", "SBE37IMPODO"),
        ("37IMPODO", "SBE37IMPODO"),
        ("SBE37SMP", "SBE37SMP"),
        ("37SMP", "SBE37SMP"),
        ("SBE37IMP", "SBE37IMP"),
        ("37IMP", "SBE37IMP"),
        ("SBE37SIP", "SBE37SIP"),
        ("37SIP", "SBE37SIP"),
        ("SBE37IM", "SBE37IM"),
        ("37IM", "SBE37IM"),
        ("SBE37SI", "SBE37SI"),
        ("37SI", "SBE37SI"),
        ("SBE37SM", "SBE37SM"),
        ("37SM", "SBE37SM"),
    ]

    for marker, enum_name in markers:
        if marker in normalised:
            return getattr(instrument_type_enum, enum_name)
    return None


def _read_hex_file_fast(
    filepath: Union[str, Path],
    instrument_type,
    enabled_sensors: list,
    layout: SimpleNamespace | None = None,
    *,
    moored_mode: bool = False,
    is_shallow: bool = True,
    frequency_channels_suppressed: int = 0,
    voltage_words_suppressed: int = 0,
) -> pd.DataFrame:
    """Read SBE hex rows with seabirdscientific's decoder and bulk DataFrame build."""
    import seabirdscientific.instrument_data as id

    if layout and layout.decoder_backend != "seabirdscientific.read_hex":
        raise NotImplementedError(
            f"Layout {layout.name} uses unsupported decoder backend "
            f"{layout.decoder_backend!r}"
        )

    records = []
    filepath = Path(filepath)
    is_data = False

    with filepath.open("r") as file:
        for line_number, line in enumerate(file, start=1):
            if is_data:
                hex_line = line.strip()
                if not hex_line:
                    continue

                if layout and len(hex_line) != layout.expected_hex_chars:
                    raise ValueError(
                        f"Hex data line {line_number} in {filepath} has "
                        f"{len(hex_line)} characters, but layout {layout.name} "
                        f"expects {layout.expected_hex_chars}. If this is a "
                        "valid file, add a new SbeHexLayout detector/decoder."
                    )

                try:
                    records.append(
                        id.read_hex(
                            instrument_type=instrument_type,
                            hex_segment=hex_line,
                            enabled_sensors=enabled_sensors,
                            moored_mode=moored_mode,
                            is_shallow=is_shallow,
                            frequency_channels_suppressed=frequency_channels_suppressed,
                            voltage_words_suppressed=voltage_words_suppressed,
                        )
                    )
                except Exception as exc:
                    raise ValueError(
                        f"Could not parse SBE HEX data line {line_number} "
                        f"in {filepath}: {exc}"
                    ) from exc
            elif line.strip().startswith("*END*"):
                is_data = True

    if not is_data:
        raise ValueError(f"Could not find '*END*' header marker in {filepath}")

    return pd.DataFrame.from_records(records)


def _sensor_configs_by_type(sensor_configs: dict) -> dict:
    configs_by_type = {}
    for sensor_info in sensor_configs.values():
        sensor_type = sensor_info.get("type")
        if sensor_type:
            configs_by_type.setdefault(sensor_type, sensor_info)
    return configs_by_type


def _require_coefficients(
    sensor_type: str, coefficients: dict, expected_keys: list[str]
):
    missing = [key for key in expected_keys if key not in coefficients]
    if missing:
        raise ValueError(
            f"Missing required {sensor_type} calibration coefficients: "
            f"{', '.join(missing)}"
        )


def sbe37_xmlcon_reader(xmlcon_file: Union[str, Path]) -> Dict:
    """
    DEPRECATED
    Parse SBE37 xmlcon file to extract sensor configuration and calibration
    coefficients.

    Parameters
    ----------
    xmlcon_file : Union[str, Path]
        Path to .xmlcon file

    Returns
    -------
    Dict
        Dictionary containing sensor configurations and coefficient objects
    """
    import xml.etree.ElementTree as ET

    xmlcon_path = Path(xmlcon_file)
    if not xmlcon_path.exists():
        raise FileNotFoundError(f"XMLCON file not found: {xmlcon_path}")

    # Parse XML
    tree = ET.parse(xmlcon_path)
    root = tree.getroot()

    sensors = {}
    enabled_sensors = []

    # Find all sensors by index
    for sensor_elem in root.findall(".//Sensor"):
        index = sensor_elem.get("index")
        if index is None:
            continue

        index = int(index)

        # Check what type of sensor this is
        temp_sensor = sensor_elem.find("TemperatureSensor")
        cond_sensor = sensor_elem.find("ConductivitySensor")
        press_sensor = sensor_elem.find("PressureSensor")

        if temp_sensor is not None:
            sensors[index] = _parse_coefficients(temp_sensor, "temperature", index)
            enabled_sensors.append("temperature")

        elif cond_sensor is not None:
            sensors[index] = _parse_coefficients(cond_sensor, "conductivity", index)
            enabled_sensors.append("conductivity")

        elif press_sensor is not None:
            sensors[index] = _parse_coefficients(press_sensor, "pressure", index)
            enabled_sensors.append("pressure")

    return {
        "sensors": sensors,
        "enabled_sensors": enabled_sensors,
        "xmlcon_path": xmlcon_path,
    }


def _parse_coefficients(sensor_elem, sensor_type: str, sensor_index: int) -> Dict:
    """
    Generic function to parse sensor coefficients from XML element.

    Parameters
    ----------
    sensor_elem : xml.etree.ElementTree.Element
        XML element containing sensor data
    sensor_type : str
        Type of sensor ('temperature', 'conductivity', 'pressure')
    sensor_index : int
        Sensor index from xmlcon

    Returns
    -------
    Dict
        Sensor information with coefficients
    """
    # Extract common fields
    serial_num = sensor_elem.find("SerialNumber").text
    cal_date = sensor_elem.find("CalibrationDate").text

    # Parse all coefficient elements to lowercase keys
    coef_dict = {}

    if sensor_type == "conductivity":
        # Special handling for conductivity - check UseG_J flag
        use_g_j_elem = sensor_elem.find("UseG_J")
        use_g_j = use_g_j_elem is not None and use_g_j_elem.text == "1"

        if use_g_j:
            # Look for equation="1" coefficients which contain G,H,I,J
            for coeffs_elem in sensor_elem.findall("Coefficients"):
                equation_attr = coeffs_elem.get("equation")
                if equation_attr == "1":
                    for child in coeffs_elem:
                        if child.text:
                            coef_dict[child.tag.lower()] = float(child.text)
                    break
        else:
            # Use equation="0" with A,B,C,D coefficients
            for coeffs_elem in sensor_elem.findall("Coefficients"):
                equation_attr = coeffs_elem.get("equation")
                if equation_attr == "0":
                    for child in coeffs_elem:
                        if child.text:
                            coef_dict[child.tag.lower()] = float(child.text)
                    break

        # Also parse direct children (slope, offset, etc.)
        for child in sensor_elem:
            if child.tag.lower() in ["slope", "offset"]:
                if child.text:
                    coef_dict[child.tag.lower()] = float(child.text)

    else:
        # For temperature and pressure, parse all numeric child elements
        for child in sensor_elem:
            if child.text and child.tag not in ["SerialNumber", "CalibrationDate"]:
                try:
                    coef_dict[child.tag.lower()] = float(child.text)
                except ValueError:
                    # Skip non-numeric elements
                    continue

    # Separate seabirdscientific calibration coefficients from slope/offset
    cal_coeffs = {}
    metadata = {}

    # Define expected coefficient names for each sensor type
    if sensor_type == "temperature":
        expected_coeffs = ["a0", "a1", "a2", "a3"]
    elif sensor_type == "conductivity":
        expected_coeffs = ["g", "h", "i", "j", "cpcor", "ctcor", "wbotc"]
    elif sensor_type == "pressure":
        expected_coeffs = [
            "pa0",
            "pa1",
            "pa2",
            "ptca0",
            "ptca1",
            "ptca2",
            "ptcb0",
            "ptcb1",
            "ptcb2",
            "ptempa0",
            "ptempa1",
            "ptempa2",
        ]
    else:
        expected_coeffs = []

    # Split coefficients
    for key, value in coef_dict.items():
        if key in expected_coeffs:
            cal_coeffs[key] = value
        else:
            metadata[key] = value

    return {
        "type": sensor_type,
        "serial_number": serial_num,
        "calibration_date": cal_date,
        "coefficients": cal_coeffs,
        "metadata": metadata,
        "index": sensor_index,
    }


# ---------------------------------------------------------------------------
# SBE 911plus xmlcon and dataset builder
# ---------------------------------------------------------------------------


def _par_im(par_elem, xmlcon_idx: int) -> float:
    """Compute the PARCoefficients.im value from a PAR_BiosphericalLicorChelseaSensor element.

    Formula: im = 1e9 * Multiplier / CalibrationConstant
    Raises ValueError on missing or zero CalibrationConstant.
    """
    cc_str = par_elem.findtext("CalibrationConstant")
    if not cc_str or not cc_str.strip():
        raise ValueError(
            f"PAR sensor at xmlcon index {xmlcon_idx} has no CalibrationConstant — "
            "cannot compute PAR coefficients."
        )
    cc = float(cc_str)
    if cc == 0.0:
        raise ValueError(
            f"PAR sensor at xmlcon index {xmlcon_idx} has CalibrationConstant=0 — "
            "cannot divide by zero when computing PAR coefficients."
        )
    multiplier = float(par_elem.findtext("Multiplier") or 1.0)
    return 1e9 * multiplier / cc



def _sci(elem) -> dict:
    """Return serial and calibration_date from a sensor XML element."""
    return {
        "serial": (elem.findtext("SerialNumber") or "").strip(),
        "calibration_date": (elem.findtext("CalibrationDate") or "").strip(),
    }


def read_xmlcon(path: Union[str, Path]) -> XmlconMap:
    """Parse an SBE 911plus xmlcon file into an :class:`XmlconMap`.

    Each ``<Sensor index="N">`` element in the xmlcon maps to a channel via
    :func:`channel_of`. The returned :class:`XmlconMap` has:

    * ``sensors`` — ``{(kind, channel): SensorInfo}`` for all declared, non-skipped
      sensors that fall within the active channel range.
    * ``meta`` — instrument-level settings (suppressed counts, timing flags, SPAR).

    Parameters
    ----------
    path : Union[str, Path]
        Path to a Sea-Bird ``.xmlcon`` / ``.XMLCON`` file.

    Raises
    ------
    ValueError
        If a sensor element tag is neither in the internal ``_XMLCON_SENSORS``
        registry nor in :data:`_XMLCON_SKIP`. Unknown sensors are an error, not
        a silent omission.
    """
    import xml.etree.ElementTree as ET
    from seabirdscientific.cal_coefficients import (
        TemperatureFrequencyCoefficients,
        PressureDigiquartzCoefficients,
        ConductivityCoefficients,
        Oxygen43Coefficients,
        ECOCoefficients,
        AltimeterCoefficients,
        PH18Coefficients,
    )

    # Registry of all known sensor tags. Sensors with coeff_class=None have
    # no upstream seabirdscientific dataclass; their coefficients are built in
    # the explicit branches below.
    _XMLCON_SENSORS: dict = {
        "TemperatureSensor": SensorSpec(
            TemperatureFrequencyCoefficients,
            {"G": "g", "H": "h", "I": "i", "J": "j", "F0": "f0"},
            "temperature",
        ),
        "ConductivitySensor": SensorSpec(
            ConductivityCoefficients,
            {"G": "g", "H": "h", "I": "i", "J": "j",
             "CPcor": "cpcor", "CTcor": "ctcor", "WBOTC": "wbotc"},
            "conductivity",
        ),
        "PressureSensor": SensorSpec(
            PressureDigiquartzCoefficients,
            {"C1": "c1", "C2": "c2", "C3": "c3", "D1": "d1", "D2": "d2",
             "T1": "t1", "T2": "t2", "T3": "t3", "T4": "t4", "T5": "t5"},
            "pressure",
        ),
        "OxygenSensor": SensorSpec(
            Oxygen43Coefficients,
            {"Soc": "soc", "offset": "v_offset", "Tau20": "tau_20",
             "A": "a", "B": "b", "C": "c", "E": "e",
             "D0": "d0", "D1": "d1", "D2": "d2",
             "H1": "h1", "H2": "h2", "H3": "h3"},
            "oxygen",
        ),
        "AltimeterSensor": SensorSpec(
            AltimeterCoefficients,
            {"ScaleFactor": "slope", "Offset": "offset"},
            "altimeter",
        ),
        "FluoroWetlabECO_AFL_FL_Sensor": SensorSpec(
            ECOCoefficients,
            {"ScaleFactor": "slope", "Vblank": "offset"},
            "fluorescence",
        ),
        "TurbidityMeter": SensorSpec(
            ECOCoefficients,
            {"ScaleFactor": "slope", "DarkVoltage": "offset"},
            "turbidity",
        ),
        "FluoroSeapointSensor": SensorSpec(
            ECOCoefficients,
            {"GainSetting": "slope", "Offset": "offset"},
            "fluorescence",
        ),
        "FluoroSeatechWetlabsFLF_Sensor": SensorSpec(
            ECOCoefficients,
            {"ScaleFactor": "slope", "Offset": "offset"},
            "fluorescence",
        ),
        "pH_Sensor": SensorSpec(
            PH18Coefficients,
            {"Slope": "slope", "Offset": "offset"},
            "ph",
        ),
        # No upstream dataclass — coefficients built in explicit branches below.
        "WET_LabsCStar": SensorSpec(None, {}, "transmissometer"),
        "UserPolynomialSensor": SensorSpec(None, {}, "user_polynomial"),
        "PAR_BiosphericalLicorChelseaSensor": SensorSpec(None, {}, "par"),
        # Calibration extracted into meta; any in-range index is skipped.
        "SPAR_Sensor": SensorSpec(None, {}, None),
    }

    path = Path(path)
    root = ET.parse(path).getroot()

    freq_suppressed = int(root.findtext(".//FrequencyChannelsSuppressed") or 0)
    volt_suppressed = int(root.findtext(".//VoltageWordsSuppressed") or 0)
    scans_to_average = int(root.findtext(".//ScansToAverage") or 1)
    store_lat_lon = int(root.findtext(".//NmeaPositionDataAdded") or 0) == 1
    nmea_time_added = int(root.findtext(".//NmeaTimeAdded") or 0) == 1
    scan_time_added = int(root.findtext(".//ScanTimeAdded") or 0) == 1
    surface_par_added = int(root.findtext(".//SurfaceParVoltageAdded") or 0) == 1

    spar_coefs = None
    if surface_par_added:
        spar_elem = root.find(".//SPAR_Sensor")
        if spar_elem is not None:
            cf = spar_elem.findtext("ConversionFactor")
            if cf is not None:
                from seabirdscientific.cal_coefficients import SPARCoefficients
                spar_coefs = SPARCoefficients(
                    im=1.0, a0=0.0, a1=1.0,
                    conversion_factor=float(cf),
                )

    meta = {
        "frequency_channels_suppressed": freq_suppressed,
        "voltage_words_suppressed": volt_suppressed,
        "scans_to_average": scans_to_average,
        "store_lat_lon": store_lat_lon,
        "nmea_time_added": nmea_time_added,
        "scan_time_added": scan_time_added,
        "surface_par_added": surface_par_added,
        "spar_coefficients": spar_coefs,
        "sample_interval": scans_to_average / 24.0,
    }

    n_freq = 5 - freq_suppressed
    n_volt = 8 - volt_suppressed

    sensors: dict = {}
    temp_count = 0
    cond_count = 0
    oxy_count = 0

    for sensor_elem in root.findall(".//Sensor"):
        xmlcon_idx = int(sensor_elem.get("index", -1))
        if xmlcon_idx < 0:
            continue

        if xmlcon_idx < n_freq:
            channel_key = ("frequency", xmlcon_idx)
        elif xmlcon_idx < n_freq + n_volt:
            channel_key = ("volt", xmlcon_idx - n_freq)
        else:
            continue  # suppressed channel or out-of-range (e.g. SPAR at index 14)

        child = next(iter(sensor_elem), None)
        if child is None:
            continue

        tag = child.tag
        if tag in _XMLCON_SKIP:
            continue

        if tag == "SPAR_Sensor":
            continue  # calibration already extracted into meta above

        spec = _XMLCON_SENSORS.get(tag)
        if spec is None:
            raise ValueError(
                f"{path.name}: unhandled sensor {tag!r} at index {xmlcon_idx}. "
                "Add it to _XMLCON_SENSORS or _XMLCON_SKIP."
            )

        serial = (child.findtext("SerialNumber") or "").strip()
        cal_date = (child.findtext("CalibrationDate") or "").strip()

        # --- explicit branches for sensors needing conditional or extra logic ---

        if tag == "TemperatureSensor":
            use_gj = int(child.findtext("UseG_J") or 1)
            if use_gj == 0:
                raise ValueError(
                    f"{path.name}: TemperatureSensor at index {xmlcon_idx} has "
                    "UseG_J=0 (A/B/C/D coefficients), which has no upstream "
                    "seabirdscientific representation. Use a Seasave version that "
                    "outputs UseG_J=1 coefficients."
                )
            role = "primary" if temp_count == 0 else "secondary"
            temp_count += 1
            coefs = TemperatureFrequencyCoefficients(
                g=float(child.findtext("G")),
                h=float(child.findtext("H")),
                i=float(child.findtext("I")),
                j=float(child.findtext("J")),
                f0=float(child.findtext("F0")),
            )
            sensors[channel_key] = SensorInfo(
                sensor_type="temperature",
                variable="temperature",
                serial_number=serial,
                calibration_date=cal_date,
                coefficients=coefs,
                role=role,
            )

        elif tag == "ConductivitySensor":
            role = "primary" if cond_count == 0 else "secondary"
            cond_count += 1
            eq1 = child.find('./Coefficients[@equation="1"]')
            # Older Seasave XMLCONs (pre-7.22) store G/H/I/J directly under the
            # sensor element rather than inside a Coefficients[@equation="1"] block,
            # and omit WBOTC entirely. Fall back to bare children in that case.
            coef_src = eq1 if eq1 is not None else child
            g = coef_src.findtext("G")
            if g is None:
                raise ValueError(
                    f"{path.name}: ConductivitySensor at index {xmlcon_idx} has no "
                    "G/H/I/J coefficients in equation=1 or bare form."
                )
            coefs = ConductivityCoefficients(
                g=float(g),
                h=float(coef_src.findtext("H")),
                i=float(coef_src.findtext("I")),
                j=float(coef_src.findtext("J")),
                cpcor=float(coef_src.findtext("CPcor") or -9.57e-8),
                ctcor=float(coef_src.findtext("CTcor") or 3.25e-6),
                wbotc=float(coef_src.findtext("WBOTC") or 0.0),
            )
            sensors[channel_key] = SensorInfo(
                sensor_type="conductivity",
                variable="conductivity",
                serial_number=serial,
                calibration_date=cal_date,
                coefficients=coefs,
                role=role,
            )

        elif tag == "PressureSensor":
            ad590m = child.findtext("AD590M")
            ad590b = child.findtext("AD590B")
            coefs = PressureDigiquartzCoefficients(
                c1=float(child.findtext("C1")),
                c2=float(child.findtext("C2")),
                c3=float(child.findtext("C3")),
                d1=float(child.findtext("D1")),
                d2=float(child.findtext("D2")),
                t1=float(child.findtext("T1")),
                t2=float(child.findtext("T2")),
                t3=float(child.findtext("T3")),
                t4=float(child.findtext("T4")),
                t5=float(child.findtext("T5")),
                AD590M=float(ad590m) if ad590m is not None else None,
                AD590B=float(ad590b) if ad590b is not None else None,
            )
            sensors[channel_key] = SensorInfo(
                sensor_type="pressure",
                variable="pressure",
                serial_number=serial,
                calibration_date=cal_date,
                coefficients=coefs,
                role="primary",
                offset=float(child.findtext("Offset") or 0),
                slope=float(child.findtext("Slope") or 1),
            )

        elif tag == "OxygenSensor":
            oxy_role = "primary" if oxy_count == 0 else "secondary"
            oxy_count += 1
            eq1 = child.find('./CalibrationCoefficients[@equation="1"]')
            if eq1 is None:
                logger.warning(
                    "OxygenSensor at xmlcon index %d has no equation=1 "
                    "calibration coefficients — sensor will be skipped.",
                    xmlcon_idx,
                )
                sensors[channel_key] = SensorInfo(
                    sensor_type="oxygen",
                    variable="oxygen",
                    serial_number=serial,
                    calibration_date=cal_date,
                    coefficients=None,
                    role=oxy_role,
                )
            else:
                sensors[channel_key] = SensorInfo(
                    sensor_type="oxygen",
                    variable="oxygen",
                    serial_number=serial,
                    calibration_date=cal_date,
                    coefficients=Oxygen43Coefficients(
                        soc=float(eq1.findtext("Soc")),
                        v_offset=float(eq1.findtext("offset")),
                        tau_20=float(eq1.findtext("Tau20")),
                        a=float(eq1.findtext("A")),
                        b=float(eq1.findtext("B")),
                        c=float(eq1.findtext("C")),
                        e=float(eq1.findtext("E")),
                        d0=float(eq1.findtext("D0")),
                        d1=float(eq1.findtext("D1")),
                        d2=float(eq1.findtext("D2")),
                        h1=float(eq1.findtext("H1")),
                        h2=float(eq1.findtext("H2")),
                        h3=float(eq1.findtext("H3")),
                    ),
                    role=oxy_role,
                )

        elif tag == "WET_LabsCStar":
            sensors[channel_key] = SensorInfo(
                sensor_type="transmissometer",
                variable="transmissometer",
                serial_number=serial,
                calibration_date=cal_date,
                coefficients={
                    "M": float(child.findtext("M")),
                    "B": float(child.findtext("B")),
                    "path_length": float(child.findtext("PathLength")),
                },
            )

        elif tag == "UserPolynomialSensor":
            sensors[channel_key] = SensorInfo(
                sensor_type="user_polynomial",
                variable="user_polynomial",
                serial_number=serial,
                calibration_date=cal_date,
                coefficients={
                    "A0": float(child.findtext("A0") or 0),
                    "A1": float(child.findtext("A1") or 0),
                    "A2": float(child.findtext("A2") or 0),
                    "A3": float(child.findtext("A3") or 0),
                },
                name=(child.findtext("SensorName") or "").strip(),
            )

        elif tag == "PAR_BiosphericalLicorChelseaSensor":
            from seabirdscientific.cal_coefficients import PARCoefficients
            sensors[channel_key] = SensorInfo(
                sensor_type="par",
                variable="par",
                serial_number=serial,
                calibration_date=cal_date,
                coefficients=PARCoefficients(
                    im=_par_im(child, xmlcon_idx),
                    a0=0.0,
                    a1=float(child.findtext("M") or 1.0),
                    multiplier=1.0,
                ),
                offset=float(child.findtext("Offset") or 0.0),
            )

        else:
            # Simple table-driven: coeff_class and tag_map are sufficient.
            coefs = None
            if spec.coeff_class is not None:
                kwargs = {}
                for xml_tag, field_name in spec.tag_map.items():
                    val_str = child.findtext(xml_tag)
                    if val_str is None:
                        raise ValueError(
                            f"{path.name}: sensor {tag!r} at index {xmlcon_idx} "
                            f"is missing required calibration tag <{xml_tag}>."
                        )
                    kwargs[field_name] = float(val_str)
                coefs = spec.coeff_class(**kwargs)
            sensors[channel_key] = SensorInfo(
                sensor_type=spec.variable or tag.lower(),
                variable=spec.variable,
                serial_number=serial,
                calibration_date=cal_date,
                coefficients=coefs,
            )

    return XmlconMap(sensors=sensors, meta=meta)


def _build_sbe911_enabled_sensors(xmlcon_map: XmlconMap) -> tuple[list, int, int]:
    """Derive the seabirdscientific enabled-sensors list from the xmlcon map.

    Returns ``(enabled_sensors, frequency_channels_suppressed,
    voltage_words_suppressed)``.
    """
    import seabirdscientific.instrument_data as _id

    meta = xmlcon_map.meta
    freq_suppressed = meta.get("frequency_channels_suppressed", 0)
    volt_suppressed = meta.get("voltage_words_suppressed", 0)
    store_lat_lon = meta.get("store_lat_lon", False)
    nmea_time_added = meta.get("nmea_time_added", False)
    scan_time_added = meta.get("scan_time_added", False)
    surface_par_added = meta.get("surface_par_added", False)

    _VOLT_SENSOR = {
        0: _id.Sensors.ExtVolt0,
        1: _id.Sensors.ExtVolt1,
        2: _id.Sensors.ExtVolt2,
        3: _id.Sensors.ExtVolt3,
        4: _id.Sensors.ExtVolt4,
        5: _id.Sensors.ExtVolt5,
        6: _id.Sensors.ExtVolt6,
        7: _id.Sensors.ExtVolt7,
    }

    temp_count = 0
    cond_count = 0
    enabled: list = []

    for freq_idx in range(5 - freq_suppressed):
        entry = xmlcon_map.sensors.get(("frequency", freq_idx))
        st = entry.sensor_type if entry else None
        if st == "temperature":
            enabled.append(
                _id.Sensors.Temperature
                if temp_count == 0
                else _id.Sensors.SecondaryTemperature
            )
            temp_count += 1
        elif st == "conductivity":
            enabled.append(
                _id.Sensors.Conductivity
                if cond_count == 0
                else _id.Sensors.SecondaryConductivity
            )
            cond_count += 1
        elif st == "pressure":
            enabled.append(_id.Sensors.Pressure)

    # Each "voltage word" in the hex is a 3-byte block encoding TWO channels.
    # VoltageWordsSuppressed counts suppressed word-pairs (not individual channels).
    # Active channels = (4 - volt_suppressed) * 2.
    active_volt_channels = (4 - volt_suppressed) * 2
    for volt_idx in range(active_volt_channels):
        enabled.append(_VOLT_SENSOR[volt_idx])

    if surface_par_added:
        enabled.append(_id.Sensors.SPAR)
    if store_lat_lon:
        enabled.append(_id.Sensors.nmeaLocation)
    if nmea_time_added:
        enabled.append(_id.Sensors.nmeaTime)
    if scan_time_added:
        enabled.append(_id.Sensors.SystemTime)

    return enabled, freq_suppressed, volt_suppressed


def _build_sbe911_time(header_info: dict, n_samples: int) -> pd.DatetimeIndex:
    """Build a time coordinate from upload time and sample interval.

    ``System UpLoad Time`` is taken as the time of the **last** scan.
    The time array is constructed backward to the first scan.
    """
    upload_time = header_info.get("upload_time")
    sample_interval = header_info.get("sample_interval")

    if upload_time is None:
        raise ValueError(
            "Cannot build time coordinate: 'System UpLoad Time' not found in "
            "the 911+ header. The file may be malformed."
        )
    if not sample_interval or sample_interval <= 0:
        raise ValueError(
            f"Cannot build time coordinate: invalid sample_interval={sample_interval!r}. "
            "Check 'Number of Scans Averaged by the Deck Unit' in the header."
        )

    start = upload_time - datetime.timedelta(seconds=(n_samples - 1) * sample_interval)
    return pd.date_range(
        start=start, periods=n_samples, freq=pd.Timedelta(seconds=sample_interval)
    )


def sbe911_hex_reader(
    hex_file: Union[str, Path],
    *,
    header_info: dict | None = None,
    xmlcon_map: XmlconMap | None = None,
    xmlcon_path: Union[str, Path] | None = None,
) -> xr.Dataset:
    """Read an SBE 911plus HEX file and return a calibrated xarray Dataset.

    Calibration coefficients are derived from the companion xmlcon file via
    :func:`read_xmlcon`.  The time coordinate is reconstructed
    from ``System UpLoad Time`` (last scan) and ``sample_interval``.

    Parameters
    ----------
    hex_file : Union[str, Path]
        Path to the ``.hex`` file.
    header_info : dict, optional
        Pre-parsed header from :func:`parse_hex_header_sbe911`.
    xmlcon_map : XmlconMap, optional
        Pre-parsed xmlcon map from :func:`read_xmlcon`.
    xmlcon_path : Union[str, Path], optional
        Path to companion xmlcon; used when ``xmlcon_map`` is not supplied.

    Returns
    -------
    xr.Dataset
        Calibrated dataset with T, C, P, secondary T/C where present, and all
        aux channels declared in the xmlcon.
    """
    import seabirdscientific.instrument_data as _id
    import seabirdscientific.conversion as conv
    import gsw

    hex_path = Path(hex_file)
    if not hex_path.exists():
        raise FileNotFoundError(f"Hex file not found: {hex_path}")

    if header_info is None:
        header_info = parse_hex_header_sbe911(hex_path)

    if xmlcon_map is None:
        if xmlcon_path is None:
            xmlcon_path = _find_sbe_hex_xmlcon_path(hex_path)
        if xmlcon_path is None:
            raise FileNotFoundError(
                f"No companion xmlcon file found for {hex_path}. "
                "SBE 911+ files require an xmlcon for calibration."
            )
        xmlcon_map = read_xmlcon(xmlcon_path)
    elif xmlcon_path is None:
        xmlcon_path = _find_sbe_hex_xmlcon_path(hex_path)

    # Merge xmlcon flags into header_info so the layout detector sees them.
    # Older Seasave versions (pre-7.22) omit "Store Lat/Lon Data" and
    # "NmeaTimeAdded" from the hex header; the XMLCON is authoritative.
    # ScanTimeAdded may already be True from the hex "Append System Time" bare flag.
    _xmlcon_meta = xmlcon_map.meta
    # XMLCON is authoritative for all timing/layout flags; older Seasave versions
    # omit several flags from the hex header entirely.
    header_info["store_lat_lon"] = _xmlcon_meta.get(
        "store_lat_lon", header_info.get("store_lat_lon", False)
    )
    header_info["nmea_time_added"] = _xmlcon_meta.get("nmea_time_added", False)
    if _xmlcon_meta.get("scan_time_added", False):
        header_info["store_system_time"] = True
    # Fall back to XMLCON ScansToAverage when hex header omits "Number of Scans Averaged"
    if header_info.get("sample_interval") is None and _xmlcon_meta.get("sample_interval"):
        header_info["sample_interval"] = _xmlcon_meta["sample_interval"]

    enabled_sensors, freq_suppressed, volt_suppressed = _build_sbe911_enabled_sensors(
        xmlcon_map
    )
    layout = detect_sbe_hex_layout(
        header_info=header_info,
        enabled_sensors_list=[],
        instrument_type=_id.InstrumentType.SBE911Plus,
        family="sbe911plus",
    )
    raw = _read_hex_file_fast(
        filepath=hex_path,
        instrument_type=_id.InstrumentType.SBE911Plus,
        enabled_sensors=enabled_sensors,
        layout=layout,
        frequency_channels_suppressed=freq_suppressed,
        voltage_words_suppressed=volt_suppressed,
    )

    n_samples = len(raw)
    times = _build_sbe911_time(header_info, n_samples)
    sample_interval = header_info["sample_interval"]
    data_vars: dict = {}

    # ----- Primary temperature (freq 0) -----
    t1_info = xmlcon_map.sensors.get(("frequency", 0))
    if t1_info is None or t1_info.sensor_type != "temperature":
        raise ValueError(
            "No primary temperature sensor at frequency channel 0 in channel map."
        )
    temp_primary = conv.convert_temperature_frequency(
        frequency=raw["temperature"].values,
        coefs=t1_info.coefficients,
        standard="ITS90",
        units="C",
    )
    data_vars["temp"] = (params.TIME, temp_primary)

    # ----- Digiquartz pressure (freq 2) -----
    p_info = xmlcon_map.sensors.get(("frequency", 2))
    if p_info is None or p_info.sensor_type != "pressure":
        raise ValueError("No pressure sensor at frequency channel 2 in channel map.")
    if "temperature compensation" not in raw.columns:
        raise ValueError(
            "Column 'temperature compensation' absent from decoded 911+ data. "
            "Required for Digiquartz pressure conversion."
        )
    pressure = conv.convert_pressure_digiquartz(
        pressure_count=raw["digiquartz pressure"].values,
        compensation_voltage=raw["temperature compensation"].values,
        coefs=p_info.coefficients,
        units="dbar",
        sample_interval=sample_interval,
    )
    slope = p_info.slope if p_info.slope is not None else 1.0
    offset = p_info.offset if p_info.offset is not None else 0.0
    pressure = pressure * slope + offset
    data_vars["press"] = (params.TIME, pressure)

    # ----- Primary conductivity (freq 1) -----
    c1_info = xmlcon_map.sensors.get(("frequency", 1))
    if c1_info is None or c1_info.sensor_type != "conductivity":
        raise ValueError(
            "No primary conductivity sensor at frequency channel 1 in channel map."
        )
    # convert_conductivity with scalar=1.0 returns mS/cm for 911+ frequency input.
    cond_primary = conv.convert_conductivity(
        conductivity_count=raw["conductivity"].values,
        temperature=temp_primary,
        pressure=pressure,
        coefs=c1_info.coefficients,
    )
    _median_cond = float(np.median(cond_primary[np.isfinite(cond_primary)]))
    if not (10.0 < _median_cond < 1000.0):
        warnings.warn(
            f"SBE 911+ primary conductivity has median {_median_cond:.4g} mS/cm, "
            "outside the expected range (10–1000). "
            "Check instrument calibration coefficients.",
            UserWarning,
            stacklevel=2,
        )
    data_vars["cond"] = (params.TIME, cond_primary)
    # salinity_primary is computed lazily inside the oxygen volt branch.
    _salinity_primary = None

    # ----- Secondary temperature (freq 3, optional) -----
    t2_info = xmlcon_map.sensors.get(("frequency", 3))
    if t2_info and t2_info.sensor_type == "temperature":
        temp_secondary = conv.convert_temperature_frequency(
            frequency=raw["secondary temperature"].values,
            coefs=t2_info.coefficients,
            standard="ITS90",
            units="C",
        )
        data_vars["temp2"] = (params.TIME, temp_secondary)

    # ----- Secondary conductivity (freq 4, optional) -----
    c2_info = xmlcon_map.sensors.get(("frequency", 4))
    if (
        c2_info
        and c2_info.sensor_type == "conductivity"
        and "temp2" in data_vars
    ):
        cond_secondary = conv.convert_conductivity(
            conductivity_count=raw["secondary conductivity"].values,
            temperature=data_vars["temp2"][1],
            pressure=pressure,
            coefs=c2_info.coefficients,
        )
        _median_cond2 = float(np.median(cond_secondary[np.isfinite(cond_secondary)]))
        if not (10.0 < _median_cond2 < 1000.0):
            warnings.warn(
                f"SBE 911+ secondary conductivity has median {_median_cond2:.4g} mS/cm, "
                "outside the expected range (10–1000). "
                "Check instrument calibration coefficients.",
                UserWarning,
                stacklevel=2,
            )
        data_vars["cond2"] = (params.TIME, cond_secondary)

    # ----- Voltage channels -----
    # VoltageWordsSuppressed counts suppressed word-pairs; active channels = (4 - suppressed) * 2
    n_volt = (4 - xmlcon_map.meta.get("voltage_words_suppressed", 0)) * 2

    for volt_idx in range(n_volt):
        raw_col = f"volt {volt_idx}"
        if raw_col not in raw.columns:
            continue
        volt_info = xmlcon_map.sensors.get(("volt", volt_idx))
        if volt_info is None:
            continue

        sensor_type = volt_info.sensor_type
        coefs = volt_info.coefficients
        volt_raw = raw[raw_col].values

        if sensor_type == "not_in_use":
            logger.info("Volt %d: NotInUse — skipped.", volt_idx)

        elif sensor_type == "oxygen":
            if coefs is None:
                logger.warning(
                    "Volt %d: oxygen sensor has no calibration coefficients — skipped.",
                    volt_idx,
                )
                continue
            if _salinity_primary is None:
                _salinity_primary = gsw.SP_from_C(
                    C=cond_primary,
                    t=temp_primary,
                    p=pressure,
                )
            oxy_ml_l = conv.convert_sbe43_oxygen(
                voltage=volt_raw,
                temperature=temp_primary,
                pressure=pressure,
                salinity=_salinity_primary,
                coefs=coefs,
                apply_tau_correction=True,
                apply_hysteresis_correction=True,
                window_size=1,
                sample_interval=sample_interval,
            )
            sigma_theta = conv.potential_density_from_t_s_p(
                temperature=temp_primary,
                salinity=_salinity_primary,
                pressure=pressure,
                lon=header_info.get("nmea_longitude") or 0.0,
                lat=header_info.get("nmea_latitude") or 0.0,
            )
            oxy_role = volt_info.role or "primary"
            oxy_var = "oxygen" if oxy_role == "primary" else "oxygen2"
            data_vars[f"{oxy_var}_ml_l"] = (params.TIME, oxy_ml_l)
            data_vars[oxy_var] = (
                params.TIME,
                conv.convert_oxygen_to_umol_per_kg(oxy_ml_l, sigma_theta),
            )

        elif sensor_type in ("fluorescence", "turbidity"):
            if coefs is None:
                logger.warning(
                    "Volt %d: %s has no calibration coefficients — skipped.",
                    volt_idx,
                    sensor_type,
                )
                continue
            data_vars[sensor_type] = (
                params.TIME,
                conv.convert_eco(raw=volt_raw, coefs=coefs),
            )

        elif sensor_type == "altimeter":
            if coefs is None:
                logger.warning(
                    "Volt %d: altimeter has no coefficients — skipped.", volt_idx
                )
                continue
            data_vars["altimeter"] = (
                params.TIME,
                conv.convert_altimeter(volts=volt_raw, coefs=coefs),
            )

        elif sensor_type == "transmissometer":
            if coefs is None:
                logger.warning(
                    "Volt %d: transmissometer has no coefficients — storing raw voltage.",
                    volt_idx,
                )
                data_vars[f"volt{volt_idx}_raw"] = (params.TIME, volt_raw)
            else:
                data_vars["transmissometer"] = (
                    params.TIME,
                    coefs["M"] * volt_raw + coefs["B"],
                )

        elif sensor_type == "user_polynomial":
            if coefs is None:
                data_vars[f"volt{volt_idx}_raw"] = (params.TIME, volt_raw)
            else:
                result = (
                    coefs["A0"]
                    + coefs["A1"] * volt_raw
                    + coefs["A2"] * volt_raw**2
                    + coefs["A3"] * volt_raw**3
                )
                raw_name = volt_info.name or f"volt{volt_idx}_poly"
                var_name = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name).lower()
                data_vars[var_name] = (params.TIME, result)
                logger.info(
                    "Volt %d: user polynomial stored as '%s'.", volt_idx, var_name
                )

        elif sensor_type == "ph":
            logger.info(
                "Volt %d: pH conversion not implemented — storing raw voltage as "
                "'volt%d_raw'.",
                volt_idx,
                volt_idx,
            )
            data_vars[f"volt{volt_idx}_raw"] = (params.TIME, volt_raw)

        elif sensor_type == "par":
            if coefs is None:
                logger.warning(
                    "Volt %d: PAR sensor has no calibration coefficients — storing raw voltage.",
                    volt_idx,
                )
                data_vars[f"volt{volt_idx}_raw"] = (params.TIME, volt_raw)
            else:
                par_offset = volt_info.offset if volt_info.offset is not None else 0.0
                data_vars["par"] = (
                    params.TIME,
                    conv.convert_par_logarithmic(volts=volt_raw, coefs=coefs) + par_offset,
                )

        else:
            raise NotImplementedError(
                f"Volt {volt_idx}: unhandled sensor_type '{sensor_type}'. "
                "Add a conversion to sbe911_hex_reader."
            )

    # ----- NMEA position (per-scan) -----
    if "NMEA Latitude" in raw.columns:
        data_vars["nmea_latitude"] = (params.TIME, raw["NMEA Latitude"].values)
    if "NMEA Longitude" in raw.columns:
        data_vars["nmea_longitude"] = (params.TIME, raw["NMEA Longitude"].values)

    # ----- Surface PAR (separate scan field, decoded by seabirdscientific) -----
    if xmlcon_map.meta.get("surface_par_added", False) and "surface par" in raw.columns:
        spar_coefs = xmlcon_map.meta.get("spar_coefficients")
        if spar_coefs is None:
            logger.warning(
                "SurfaceParVoltageAdded is set but no SPAR calibration found "
                "in XMLCON — storing raw surface PAR voltage."
            )
            data_vars["spar_raw"] = (params.TIME, raw["surface par"].values)
        else:
            data_vars["spar"] = (
                params.TIME,
                conv.convert_spar_biospherical(
                    volts=raw["surface par"].values, coefs=spar_coefs
                ),
            )

    ds = xr.Dataset(data_vars, coords={params.TIME: times})

    _VAR_ATTRS = {
        "temp": {"units": "degree_C", "long_name": "Temperature (Primary)"},
        "cond": {"units": "mS cm-1", "long_name": "Conductivity (Primary)"},
        "press": {"units": "dbar", "long_name": "Pressure"},
        "temp2": {"units": "degree_C", "long_name": "Temperature (Secondary)"},
        "cond2": {"units": "mS cm-1", "long_name": "Conductivity (Secondary)"},
        "oxygen": {"units": "umol kg-1", "long_name": "Dissolved Oxygen"},
        "oxygen_ml_l": {"units": "ml l-1", "long_name": "Dissolved Oxygen"},
        "oxygen2": {"units": "umol kg-1", "long_name": "Dissolved Oxygen (Secondary)"},
        "oxygen2_ml_l": {"units": "ml l-1", "long_name": "Dissolved Oxygen (Secondary)"},
        "fluorescence": {"units": "mg m-3", "long_name": "Fluorescence"},
        "turbidity": {"units": "NTU", "long_name": "Turbidity"},
        "altimeter": {"units": "m", "long_name": "Altimeter Distance"},
        "transmissometer": {"units": "%", "long_name": "Beam Transmission"},
        "par": {"units": "umol_photons m-2 s-1", "long_name": "Photosynthetically Active Radiation"},
        "spar": {"units": "umol_photons m-2 s-1", "long_name": "Surface Photosynthetically Active Radiation"},
        "spar_raw": {"units": "V", "long_name": "Surface PAR (raw voltage)"},
        "nmea_latitude": {"units": "degrees_north", "long_name": "NMEA Latitude"},
        "nmea_longitude": {"units": "degrees_east", "long_name": "NMEA Longitude"},
    }
    for var, attrs in _VAR_ATTRS.items():
        if var in ds:
            ds[var].attrs.update(attrs)

    ds.attrs["source_file"] = str(hex_path)
    ds.attrs["instrument_family"] = "sbe911plus"
    ds.attrs["instrument_type"] = _id.InstrumentType.SBE911Plus.value
    ds.attrs["sample_interval"] = sample_interval
    ds.attrs["hex_layout"] = layout.name
    ds.attrs["hex_layout_expected_chars"] = layout.expected_hex_chars
    if xmlcon_path is not None:
        ds.attrs["xmlcon_file"] = str(xmlcon_path)
        try:
            ds.attrs["xmlcon_content"] = Path(xmlcon_path).read_text(encoding="utf-8")
        except Exception:
            ds.attrs["xmlcon_content"] = Path(xmlcon_path).read_text(encoding="latin-1")
    if header_info.get("upload_time") is not None:
        ds.attrs["upload_time"] = header_info["upload_time"].isoformat()
    for k, v in header_info.get("user_header", {}).items():
        ds.attrs[f"user_{k.lower()}"] = v

    return ds


def parse_hex_header_sensors(hex_file: Union[str, Path]) -> Dict:
    """
    Parse SBE37 hex file header to extract enabled sensors and calibration coefficients.

    Parameters
    ----------
    hex_file : Union[str, Path]
        Path to .hex file

    Returns
    -------
    Dict
        Dictionary with enabled_sensors list and calibration_coefficients
    """
    import xml.etree.ElementTree as ET

    hex_path = Path(hex_file)
    enabled_sensors = []
    calibration_coeffs = {}
    device_type = None
    sample_length = None
    tx_real_time = None
    reference_pressure = None
    output_flags = {}

    # Read the header and extract XML content
    header_lines = []
    with open(hex_path, "r") as f:
        for line in f:
            if line.startswith("*"):
                header_lines.append(line[1:].strip())  # Remove * prefix
            else:
                # End of header, start of data
                break

    # Join header lines and try to parse as XML
    header_xml = "\n".join(header_lines)

    # Extract enabled sensors
    for line in header_lines:
        if device_type is None:
            device_match = _DEVICE_TYPE_RE.search(line)
            if device_match:
                device_type = device_match.group("device_type")

        value_match = _HEADER_VALUE_RE.search(line)
        if value_match:
            tag = value_match.group("tag")
            value = value_match.group("value").strip()

            if tag == "SampleLength":
                try:
                    sample_length = int(value)
                except ValueError:
                    sample_length = None
            elif tag == "TxRealTime":
                tx_real_time = _parse_bool_text(value)
            elif tag == "ReferencePressure":
                reference_pressure = _parse_float_text(value)
            elif tag in {
                "OutputTemperature",
                "OutputConductivity",
                "OutputPressure",
                "OutputOxygen",
                "PressureInstalled",
            }:
                output_flags[tag] = _parse_bool_text(value)

        sensor_match = _SENSOR_ID_RE.search(line)
        if sensor_match:
            sensor_type = _normalise_sensor_id(sensor_match.group("sensor_id"))
            if sensor_type and sensor_type not in enabled_sensors:
                enabled_sensors.append(sensor_type)

    output_sensor_tags = {
        "OutputTemperature": "temperature",
        "OutputConductivity": "conductivity",
        "OutputPressure": "pressure",
        "OutputOxygen": "oxygen",
    }
    for tag, sensor_type in output_sensor_tags.items():
        if output_flags.get(tag) is True and sensor_type not in enabled_sensors:
            enabled_sensors.append(sensor_type)

    # Extract calibration coefficients
    try:
        # Find CalibrationCoefficients section
        cal_start = header_xml.find("<CalibrationCoefficients")
        cal_end_marker = "</CalibrationCoefficients>"
        cal_end_index = header_xml.find(cal_end_marker)

        if cal_start != -1 and cal_end_index != -1:
            cal_end = cal_end_index + len(cal_end_marker)
            cal_xml = header_xml[cal_start:cal_end]

            # Parse calibration XML
            root = ET.fromstring(cal_xml)

            for calibration in root.findall("Calibration"):
                sensor_id = _normalise_sensor_id(calibration.get("id", ""))
                cal_format = calibration.get("format", "")

                if sensor_id in ["temperature", "conductivity", "pressure", "oxygen"]:
                    sensor_coeffs = {}

                    for child in calibration:
                        text = (child.text or "").strip()
                        if not text:
                            continue

                        if child.tag in ["A0", "A1", "A2", "A3"]:  # Temperature coeffs
                            sensor_coeffs[child.tag.lower()] = float(text)
                        elif child.tag in [
                            "G",
                            "H",
                            "I",
                            "J",
                            "PCOR",
                            "TCOR",
                            "WBOTC",
                        ]:  # Conductivity coeffs
                            # Map to seabirdscientific expected names
                            key_map = {
                                "PCOR": "cpcor",
                                "TCOR": "ctcor",
                                "WBOTC": "wbotc",
                            }
                            key = key_map.get(child.tag, child.tag.lower())
                            sensor_coeffs[key] = float(text)
                        elif child.tag.startswith("PA"):  # Pressure coeffs
                            sensor_coeffs[child.tag.lower()] = float(text)
                        elif child.tag.startswith("PTC"):  # Pressure temp compensation
                            sensor_coeffs[child.tag.lower()] = float(text)
                        elif child.tag.startswith("PTEMP"):  # Pressure temp coeffs
                            sensor_coeffs[child.tag.lower()] = float(text)
                        elif child.tag.startswith("OX") or child.tag in [
                            "TAU20",
                            "NTAU",
                        ]:  # Oxygen coeffs
                            sensor_coeffs[child.tag.lower()] = float(text)
                        elif child.tag in ["SerialNum", "CalDate"]:
                            sensor_coeffs[child.tag.lower()] = text

                    calibration_coeffs[sensor_id] = {
                        "coefficients": sensor_coeffs,
                        "format": cal_format,
                        "type": sensor_id,
                    }

    except Exception as e:
        raise ValueError(
            f"Could not parse calibration coefficients in {hex_path}: {e}. "
            "The header XML may be malformed. Supply calibration via an xmlcon file."
        ) from e

    return {
        "enabled_sensors": enabled_sensors,
        "calibration_coefficients": calibration_coeffs,
        "device_type": device_type,
        "sample_length": sample_length,
        "tx_real_time": tx_real_time,
        "reference_pressure": reference_pressure,
        "output_flags": output_flags,
    }


def sbe37_hex_reader(
    hex_file: Union[str, Path],
    *,
    instrument_type=None,
    moored_mode: bool = False,
    is_shallow: bool = True,
    frequency_channels_suppressed: int = 0,
    voltage_words_suppressed: int = 0,
    header_info: dict | None = None,
    xmlcon_info: dict | None = None,
    xmlcon_path: Union[str, Path] | None = None,
    create_pressure_from_reference_pressure: bool = False,
) -> xr.Dataset:
    """
    Read SBE37 hex file using seabirdscientific library.

    Parameters
    ----------
    hex_file : Union[str, Path]
        Path to .hex file
    instrument_type : optional
        Optional seabirdscientific InstrumentType enum or SBE37 instrument type string
        (for example ``"SBE37SMP"``). If omitted, DeviceType is read from the header.
    moored_mode, is_shallow, frequency_channels_suppressed, voltage_words_suppressed
        Advanced seabirdscientific decoder options passed through unchanged.
    header_info : dict, optional
        Pre-parsed HEX header metadata from :func:`parse_hex_header_sensors`.
    xmlcon_info : dict, optional
        Pre-parsed XMLCON metadata from :func:`sbe37_xmlcon_reader`.
    xmlcon_path : Union[str, Path], optional
        Path to the companion XMLCON file that produced ``xmlcon_info``.
    create_pressure_from_reference_pressure : bool, default False
        If True and no pressure sensor data are decoded, create a constant
        pressure variable from the header ``ReferencePressure`` value. This is
        explicit because reference pressure is deployment/configuration
        metadata, not a measured pressure time series.

    Returns
    -------
    xr.Dataset
        Dataset containing temperature, conductivity, pressure, and/or oxygen data
    """
    hex_path = Path(hex_file)
    if not hex_path.exists():
        raise FileNotFoundError(f"Hex file not found: {hex_path}")
    if xmlcon_path is not None:
        xmlcon_path = Path(xmlcon_path)

    # Parse sensors and calibration coefficients from hex header
    if header_info is None:
        header_info = parse_hex_header_sensors(hex_path)
    enabled_sensors_list = header_info["enabled_sensors"]
    calibration_coeffs = header_info.get("calibration_coefficients", {})
    device_type = header_info.get("device_type")
    reference_pressure = header_info.get("reference_pressure")

    # Fallback: Look for corresponding xmlcon file if header parsing fails
    if not enabled_sensors_list:
        if xmlcon_info is None:
            if xmlcon_path is None:
                xmlcon_path = _find_sbe_hex_xmlcon_path(hex_path)
            if xmlcon_path is not None:
                xmlcon_info = sbe37_xmlcon_reader(xmlcon_path)
        if xmlcon_info is not None:
            enabled_sensors_list = xmlcon_info["enabled_sensors"]
        if not enabled_sensors_list:
            raise ValueError(
                f"Could not determine sensor configuration for {hex_path}. "
                "No xmlcon file found and header parsing failed."
            )

    logger.info("Detected enabled sensors: %s", enabled_sensors_list)
    if calibration_coeffs:
        logger.info(
            "Found calibration coefficients for: %s",
            list(calibration_coeffs.keys()),
        )

    try:
        import seabirdscientific.instrument_data as id
    except ImportError:
        raise ImportError(
            "seabirdscientific package required for SBE37 hex file reading"
        )

    # Build enabled sensors list following the example format
    enabled_sensors = []

    # Always include basic sensors first
    if "temperature" in enabled_sensors_list:
        enabled_sensors.append(id.Sensors.Temperature)
    if "conductivity" in enabled_sensors_list:
        enabled_sensors.append(id.Sensors.Conductivity)
    if "pressure" in enabled_sensors_list:
        enabled_sensors.append(id.Sensors.Pressure)

    # Add oxygen sensor if detected - use SBE63 format for ODO instruments
    if "oxygen" in enabled_sensors_list:
        enabled_sensors.append(id.Sensors.SBE63)

    instrument_type = _select_sbe37_instrument_type(
        id,
        device_type=device_type,
        instrument_type=instrument_type,
    )

    logger.info("Using instrument type: %s", instrument_type.value)
    logger.debug(
        "Enabled seabirdscientific sensors: %s",
        [s.value for s in enabled_sensors],
    )

    layout = detect_sbe_hex_layout(
        header_info=header_info,
        enabled_sensors_list=enabled_sensors_list,
        instrument_type=instrument_type,
    )
    logger.info("Detected hex layout: %s", layout.name)

    # Read the hex file. This deliberately keeps seabirdscientific's line decoder,
    # but avoids its slow pandas scalar assignment loop.
    raw_data = _read_hex_file_fast(
        filepath=hex_path,
        instrument_type=instrument_type,
        enabled_sensors=enabled_sensors,
        layout=layout,
        moored_mode=moored_mode,
        is_shallow=is_shallow,
        frequency_channels_suppressed=frequency_channels_suppressed,
        voltage_words_suppressed=voltage_words_suppressed,
    )

    # Import conversion functions and coefficient classes
    try:
        import seabirdscientific.conversion as conv
        from seabirdscientific.cal_coefficients import (
            TemperatureCoefficients,
            ConductivityCoefficients,
            PressureCoefficients,
        )
    except ImportError:
        raise ImportError(
            "seabirdscientific conversion module required for calibration"
        )

    # Convert to xarray Dataset
    data_vars = {}
    pressure_from_reference_pressure = False

    # Extract time coordinate from raw data
    if raw_data.empty:
        times = pd.DatetimeIndex([])
    elif "date time" not in raw_data.columns:
        raise ValueError(f"Decoded SBE HEX data from {hex_path} does not contain time")
    else:
        times = pd.to_datetime(raw_data["date time"])
    n_samples = len(times)

    # Apply calibration coefficients if available (from header or xmlcon)
    if calibration_coeffs or xmlcon_info:
        logger.info("Applying calibration coefficients to convert raw data")

        # Use header calibration coefficients if available.
        if calibration_coeffs:
            sensor_configs = calibration_coeffs
        else:
            sensor_configs = xmlcon_info["sensors"]
        sensor_configs = _sensor_configs_by_type(sensor_configs)

        temperature_info = sensor_configs.get("temperature")
        if temperature_info and "temperature" in raw_data.columns:
            coeffs = temperature_info["coefficients"]
            temp_keys = ["a0", "a1", "a2", "a3"]
            temp_coeffs_filtered = {
                k: v
                for k, v in coeffs.items()
                if k in temp_keys and isinstance(v, (int, float))
            }
            _require_coefficients("temperature", temp_coeffs_filtered, temp_keys)
            temp_coefs = TemperatureCoefficients(**temp_coeffs_filtered)

            temperature = conv.convert_temperature(
                temperature_counts_in=raw_data["temperature"].values,
                coefs=temp_coefs,
                standard="ITS90",
                units="C",
                use_mv_r=False,
            )
            data_vars["temp"] = (params.TIME, temperature)

        pressure_info = sensor_configs.get("pressure")
        if pressure_info and "pressure" in raw_data.columns:
            coeffs = pressure_info["coefficients"]
            press_keys = [
                "pa0",
                "pa1",
                "pa2",
                "ptca0",
                "ptca1",
                "ptca2",
                "ptcb0",
                "ptcb1",
                "ptcb2",
                "ptempa0",
                "ptempa1",
                "ptempa2",
            ]
            press_coeffs_filtered = {
                k: v
                for k, v in coeffs.items()
                if k in press_keys and isinstance(v, (int, float))
            }
            _require_coefficients("pressure", press_coeffs_filtered, press_keys)
            press_coefs = PressureCoefficients(**press_coeffs_filtered)

            if "temperature compensation" not in raw_data.columns:
                raise ValueError(
                    f"Column 'temperature compensation' is absent from decoded SBE37 "
                    f"data in {hex_path}. Cannot convert pressure without it."
                )
            temp_comp_values = raw_data["temperature compensation"].values

            pressure = conv.convert_pressure(
                pressure_count=raw_data["pressure"].values,
                compensation_voltage=temp_comp_values,
                coefs=press_coefs,
                units="dbar",
            )
            data_vars["press"] = (params.TIME, pressure)

        if (
            create_pressure_from_reference_pressure
            and "press" not in data_vars
            and reference_pressure is not None
        ):
            data_vars["press"] = (
                params.TIME,
                np.full(n_samples, float(reference_pressure), dtype=float),
            )
            pressure_from_reference_pressure = True

        conductivity_info = sensor_configs.get("conductivity")
        if conductivity_info and "conductivity" in raw_data.columns:
            coeffs = conductivity_info["coefficients"]
            cond_keys = ["g", "h", "i", "j", "cpcor", "ctcor", "wbotc"]
            cond_coeffs_filtered = {
                k: v
                for k, v in coeffs.items()
                if k in cond_keys and isinstance(v, (int, float))
            }
            _require_coefficients("conductivity", cond_coeffs_filtered, cond_keys)
            cond_coefs = ConductivityCoefficients(**cond_coeffs_filtered)

            if "temp" not in data_vars:
                logger.warning(
                    "SBE37 conductivity conversion: temperature calibration is "
                    "missing; using zeros for temperature. Result will be inaccurate."
                )
            if "press" not in data_vars:
                logger.warning(
                    "SBE37 conductivity conversion: no pressure data available; "
                    "using zeros for pressure. Use create_pressure_from_reference_pressure=True "
                    "to supply a reference depth for a more accurate result."
                )
            temp_values = data_vars.get("temp", (None, np.zeros(n_samples)))[1]
            pressure_values = data_vars.get("press", (None, np.zeros(n_samples)))[1]
            conductivity = conv.convert_conductivity(
                conductivity_count=raw_data["conductivity"].values,
                temperature=temp_values,
                pressure=pressure_values,
                coefs=cond_coefs,
            )
            # convert_conductivity returns S/m for SBE37; pipeline normalises to mS cm-1.
            _median_cond37 = float(np.median(conductivity[np.isfinite(conductivity)]))
            if not (0.5 < _median_cond37 < 10.0):
                warnings.warn(
                    f"SBE37 conductivity has median {_median_cond37:.4g} S/m, "
                    "outside the expected range (0.5–10). "
                    "Check instrument calibration coefficients.",
                    UserWarning,
                    stacklevel=2,
                )
            data_vars["cond"] = (params.TIME, conductivity)

        oxygen_info = sensor_configs.get("oxygen")
        if oxygen_info and "SBE63 oxygen phase" in raw_data.columns:
            coeffs = oxygen_info["coefficients"]
            try:
                # Import SBE63 oxygen conversion
                from seabirdscientific.cal_coefficients import (
                    Oxygen63Coefficients,
                    Thermistor63Coefficients,
                )

                # Create oxygen coefficients object
                oxygen_coeffs_filtered = {
                    "a0": coeffs.get("oxa0", 0),
                    "a1": coeffs.get("oxa1", 0),
                    "a2": coeffs.get("oxa2", 0),
                    "b0": coeffs.get("oxb0", 0),
                    "b1": coeffs.get("oxb1", 0),
                    "c0": coeffs.get("oxc0", 0),
                    "c1": coeffs.get("oxc1", 0),
                    "c2": coeffs.get("oxc2", 0),
                    "e": coeffs.get("oxe", 0),
                }
                oxy_coefs = Oxygen63Coefficients(**oxygen_coeffs_filtered)

                # Create thermistor coefficients object
                therm_coeffs_filtered = {
                    "ta0": coeffs.get("oxta0", 0),
                    "ta1": coeffs.get("oxta1", 0),
                    "ta2": coeffs.get("oxta2", 0),
                    "ta3": coeffs.get("oxta3", 0),
                }
                therm_coefs = Thermistor63Coefficients(**therm_coeffs_filtered)

                oxygen_phase = raw_data["SBE63 oxygen phase"].values
                oxygen_temp = raw_data["SBE63 oxygen temperature"].values

                # We need pressure and salinity for full conversion.
                if "temp" in data_vars and "cond" in data_vars and "press" in data_vars:
                    import gsw as _gsw

                    pressure_vals = data_vars["press"][1]
                    salinity_vals = _gsw.SP_from_C(
                        C=data_vars["cond"][1],
                        t=data_vars["temp"][1],
                        p=pressure_vals,
                    )

                    oxygen_ml_per_l = conv.convert_sbe63_oxygen(
                        raw_oxygen_phase=oxygen_phase,
                        thermistor=oxygen_temp,
                        pressure=pressure_vals,
                        salinity=salinity_vals,
                        coefs=oxy_coefs,
                        thermistor_coefs=therm_coefs,
                        thermistor_units="C",
                    )

                    # 1 ml/L O2 = 44.66 umol/L at STP.
                    data_vars["oxygen"] = (params.TIME, oxygen_ml_per_l * 44.66)
                    data_vars["oxygen_ml_l"] = (params.TIME, oxygen_ml_per_l)
                else:
                    data_vars["oxygen_phase"] = (params.TIME, oxygen_phase)
                    data_vars["oxygen_temp"] = (params.TIME, oxygen_temp)

            except Exception as e:
                logger.warning("Could not apply oxygen calibration: %s", e)
                data_vars["oxygen_phase"] = (
                    params.TIME,
                    raw_data["SBE63 oxygen phase"].values,
                )
                data_vars["oxygen_temp"] = (
                    params.TIME,
                    raw_data["SBE63 oxygen temperature"].values,
                )
    else:
        # No xmlcon file - use raw data directly from seabirdscientific
        logger.info("No calibration coefficients available; using raw converted data")

        # Add available sensors from raw_data
        if "temperature" in raw_data.columns:
            data_vars["temp"] = (params.TIME, raw_data["temperature"].values)
        if "conductivity" in raw_data.columns:
            data_vars["cond"] = (params.TIME, raw_data["conductivity"].values)
        if "pressure" in raw_data.columns:
            data_vars["press"] = (params.TIME, raw_data["pressure"].values)
        if (
            create_pressure_from_reference_pressure
            and "press" not in data_vars
            and reference_pressure is not None
        ):
            data_vars["press"] = (
                params.TIME,
                np.full(n_samples, float(reference_pressure), dtype=float),
            )
            pressure_from_reference_pressure = True
        # Handle SBE63 oxygen data (phase and temperature)
        if "SBE63 oxygen phase" in raw_data.columns:
            data_vars["oxygen_phase"] = (
                params.TIME,
                raw_data["SBE63 oxygen phase"].values,
            )
        if "SBE63 oxygen temperature" in raw_data.columns:
            data_vars["oxygen_temp"] = (
                params.TIME,
                raw_data["SBE63 oxygen temperature"].values,
            )

    # Create dataset
    ds = xr.Dataset(data_vars, coords={params.TIME: times})

    # Add units as variable attributes
    if "temp" in data_vars:
        ds["temp"].attrs["units"] = "degree_C"
        ds["temp"].attrs["long_name"] = "Temperature"
    if "cond" in data_vars:
        ds["cond"].attrs["units"] = "S/m"
        ds["cond"].attrs["long_name"] = "Conductivity"
        ds["cond"].attrs["conductivity_unit_source"] = "SBE37 hex convert_conductivity returns S/m"
    if "press" in data_vars:
        ds["press"].attrs["units"] = "dbar"
        if pressure_from_reference_pressure:
            ds["press"].attrs["long_name"] = "Reference Pressure"
            ds["press"].attrs["measurement_type"] = "Configured"
            ds["press"].attrs["sensor_source"] = "configured"
            ds["press"].attrs["sensor_source_basis"] = "sbe_header_reference_pressure"
            ds["press"].attrs["comment"] = (
                "Constant pressure created from the SBE header ReferencePressure "
                "value because create_pressure_from_reference_pressure=True."
            )
        else:
            ds["press"].attrs["long_name"] = "Pressure"
    if "oxygen" in data_vars:
        ds["oxygen"].attrs["units"] = "umol l-1"
        ds["oxygen"].attrs["long_name"] = "Dissolved Oxygen"
    if "oxygen_ml_l" in data_vars:
        ds["oxygen_ml_l"].attrs["units"] = "ml l-1"
        ds["oxygen_ml_l"].attrs["long_name"] = "Dissolved Oxygen (ml/L)"
    if "oxygen_phase" in data_vars:
        ds["oxygen_phase"].attrs["units"] = "degrees"
        ds["oxygen_phase"].attrs["long_name"] = "Oxygen Phase"
    if "oxygen_temp" in data_vars:
        ds["oxygen_temp"].attrs["units"] = "degree_C"
        ds["oxygen_temp"].attrs["long_name"] = "Oxygen Sensor Temperature"

    # Add metadata
    ds.attrs["source_file"] = str(hex_path)
    if xmlcon_info:
        if xmlcon_path is not None:
            ds.attrs["xmlcon_file"] = str(xmlcon_path)
        else:
            ds.attrs["sensor_detection"] = "xmlcon_metadata"
    else:
        ds.attrs["sensor_detection"] = "hex_header"
    if device_type:
        ds.attrs["device_type"] = device_type
    ds.attrs["instrument_type"] = instrument_type.value
    ds.attrs["hex_layout"] = layout.name
    ds.attrs["hex_layout_backend"] = layout.decoder_backend
    ds.attrs["hex_layout_expected_chars"] = layout.expected_hex_chars
    ds.attrs["hex_layout_fields"] = ", ".join(field.name for field in layout.fields)
    ds.attrs["data_type"] = (
        "calibrated" if (calibration_coeffs or xmlcon_info) else "raw"
    )
    if reference_pressure is not None:
        ds.attrs["reference_pressure"] = reference_pressure
    ds.attrs["create_pressure_from_reference_pressure"] = (
        create_pressure_from_reference_pressure
    )
    if pressure_from_reference_pressure:
        ds.attrs["pressure_source"] = "header_reference_pressure"

    # Add sensor information as attributes
    if xmlcon_info:
        for sensor_info in xmlcon_info["sensors"].values():
            sensor_type = sensor_info["type"]
            serial = sensor_info["serial_number"]
            cal_date = sensor_info["calibration_date"]

            ds.attrs[f"{sensor_type}_serial"] = serial
            ds.attrs[f"{sensor_type}_calibration_date"] = cal_date

    return ds


class SbeHexReader(AbstractReader):
    """SeaSenseLib reader wrapper for Sea-Bird SBE37 ``.hex`` files."""

    def __init__(
        self,
        input_file: str,
        mapping: dict | None = None,
        **kwargs,
    ):
        """Initialize the SBE HEX reader.

        Parameters
        ----------
        input_file : str
            Path to the SBE ``.hex`` file.
        mapping : dict, optional
            Variable name mapping dictionary.
        **kwargs
            Additional base class parameters.
        """
        self._hex_reader_options = {
            "instrument_type": kwargs.pop("instrument_type", None),
            "moored_mode": kwargs.pop("moored_mode", False),
            "is_shallow": kwargs.pop("is_shallow", True),
            "frequency_channels_suppressed": kwargs.pop(
                "frequency_channels_suppressed", 0
            ),
            "voltage_words_suppressed": kwargs.pop("voltage_words_suppressed", 0),
            "create_pressure_from_reference_pressure": kwargs.pop(
                "create_pressure_from_reference_pressure", False
            ),
        }
        super().__init__(input_file, mapping, **kwargs)
        self._raw_header = None
        self._raw_metadata_blocks = {}
        self._raw_metadata_variables = {}
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...]:
        """Return valid file extensions for SBE HEX files."""
        return (".hex",)

    @classmethod
    def reader_args(cls) -> list[dict]:
        return [
            cls._reader_arg(
                "instrument_type",
                "str",
                None,
                "Override the SBE37 instrument type used by seabirdscientific.",
            ),
            cls._reader_arg(
                "moored_mode",
                "bool",
                False,
                "Pass seabirdscientific's moored-mode option to the hex decoder.",
            ),
            cls._reader_arg(
                "is_shallow",
                "bool",
                True,
                "Pass seabirdscientific's shallow-water option to the hex decoder.",
            ),
            cls._reader_arg(
                "frequency_channels_suppressed",
                "int",
                0,
                "Number of suppressed frequency channels for the hex decoder.",
            ),
            cls._reader_arg(
                "voltage_words_suppressed",
                "int",
                0,
                "Number of suppressed voltage words for the hex decoder.",
            ),
            cls._reader_arg(
                "create_pressure_from_reference_pressure",
                "bool",
                False,
                "Create a constant pressure variable from the SBE header ReferencePressure value.",
            ),
        ]

    def _load_data(self) -> xr.Dataset:
        """Load the SBE HEX file, dispatching on instrument family."""
        self._raw_header = _read_sbe_hex_raw_header(self.input_file)
        family = detect_sbe_hex_family(self.input_file)

        if family == "sbe911plus":
            return self._load_data_sbe911plus()

        return self._load_data_sbe37()

    def _load_data_sbe37(self) -> xr.Dataset:
        """Load data for the SBE37 family."""
        header_info = parse_hex_header_sensors(self.input_file)
        xmlcon_info = None
        xmlcon_path = _find_sbe_hex_xmlcon_path(self.input_file)
        if xmlcon_path is not None:
            try:
                xmlcon_info = sbe37_xmlcon_reader(xmlcon_path)
            except Exception as exc:
                logger.warning(
                    "Could not parse companion SBE XMLCON metadata %s: %s",
                    xmlcon_path,
                    exc,
                )

        self._raw_metadata_blocks = _sbe_hex_raw_metadata_blocks(
            header_info,
            xmlcon_info,
        )
        ds = sbe37_hex_reader(
            self.input_file,
            header_info=header_info,
            xmlcon_info=xmlcon_info,
            xmlcon_path=xmlcon_path,
            **self._hex_reader_options,
        )

        self._raw_metadata_variables = {
            name: meta
            for name, meta in _sbe_hex_raw_variable_metadata(
                header_info,
                xmlcon_info,
            ).items()
            if name in ds.data_vars
        }
        if (
            "press" in ds.data_vars
            and "press" not in self._raw_metadata_variables
            and ds.attrs.get("pressure_source") == "header_reference_pressure"
        ):
            self._raw_metadata_variables["press"] = {
                "sensor_type": "pressure",
                "source": "header_reference_pressure",
                "reference_pressure": header_info.get("reference_pressure"),
            }

        return ds

    def _load_data_sbe911plus(self) -> xr.Dataset:
        """Load data for the SBE 911plus family."""
        header_info = parse_hex_header_sbe911(self.input_file)
        xmlcon_path = _find_sbe_hex_xmlcon_path(self.input_file)
        xmlcon_map = None
        if xmlcon_path is not None:
            try:
                xmlcon_map = read_xmlcon(xmlcon_path)
            except Exception as exc:
                raise ValueError(
                    f"Could not parse companion 911+ XMLCON {xmlcon_path}: {exc}. "
                    "SBE 911+ calibration requires a valid XMLCON file."
                ) from exc

        ds = sbe911_hex_reader(
            self.input_file,
            header_info=header_info,
            xmlcon_map=xmlcon_map,
            xmlcon_path=xmlcon_path,
        )
        self._raw_metadata_blocks = {
            "attributes": {
                "instrument_family": "sbe911plus",
                "upload_time": header_info.get("upload_time"),
                "sample_interval": header_info.get("sample_interval"),
            }
        }
        self._raw_metadata_variables = {}
        return ds

    @classmethod
    def format_key(cls) -> str:
        return "sbe-hex"

    @classmethod
    def format_name(cls) -> str:
        return "SeaBird SBE HEX"

    @classmethod
    def file_extension(cls) -> str | None:
        return ".hex"

    @classmethod
    def format_mappings(cls) -> dict[str, list]:
        """Return aliases produced by the wrapped SBE HEX decoding function."""
        return {
            params.TEMPERATURE: ["temp"],
            params.CONDUCTIVITY: ["cond"],
            params.PRESSURE: ["press"],
            params.OXYGEN: ["oxygen"],
        }
