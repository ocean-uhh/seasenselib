"""Reader wrapper and helper functions for Sea-Bird SBE37 HEX files."""

from __future__ import annotations

import logging
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Dict, Union

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
) -> SimpleNamespace:
    """Detect the raw data-row layout before decoding.

    Only the SBE37 format-0 family is implemented so far because that is what
    seabirdscientific currently decodes for SBE37 variants. This small detector
    gives future developers a clear extension point for new row structures.
    """
    if not _is_sbe37_instrument_type(instrument_type):
        raise ValueError(
            f"No SBE HEX layout detector is implemented for {instrument_type}. "
            "Add a new SbeHexLayout detector/decoder for this instrument family."
        )

    if header_info.get("tx_real_time") is False:
        raise ValueError(
            "Unsupported SBE37 HEX layout: TxRealTime=no. "
            "Add a non-realtime SbeHexLayout decoder before reading this file."
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

    fields.append(
        _sbe_hex_field("date time", _SBE37_FORMAT0_HEX_LENGTHS["date time"])
    )

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
    candidates = [hex_path.with_suffix(".xmlcon")]
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
        if not sensor_info and sensor_type not in header_info.get("enabled_sensors", []):
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
    return selected or instrument_type_enum.SBE37SM


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
        logger.warning(
            "Could not parse calibration coefficients in %s: %s", hex_path, e
        )

    return {
        "enabled_sensors": enabled_sensors,
        "calibration_coefficients": calibration_coeffs,
        "device_type": device_type,
        "sample_length": sample_length,
        "tx_real_time": tx_real_time,
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

    # Extract time coordinate from raw data
    if raw_data.empty:
        times = pd.DatetimeIndex([])
    elif "date time" not in raw_data.columns:
        raise ValueError(
            f"Decoded SBE HEX data from {hex_path} does not contain time"
        )
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

            temp_comp_values = raw_data.get(
                "temperature compensation", np.zeros(n_samples)
            )
            if hasattr(temp_comp_values, "values"):
                temp_comp_values = temp_comp_values.values

            pressure = conv.convert_pressure(
                pressure_count=raw_data["pressure"].values,
                compensation_voltage=temp_comp_values,
                coefs=press_coefs,
                units="dbar",
            )
            data_vars["press"] = (params.TIME, pressure)

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

            temp_values = data_vars.get("temp", (None, np.zeros(n_samples)))[1]
            pressure_values = data_vars.get("press", (None, np.zeros(n_samples)))[1]
            conductivity = conv.convert_conductivity(
                conductivity_count=raw_data["conductivity"].values,
                temperature=temp_values,
                pressure=pressure_values,
                coefs=cond_coefs,
            )
            # Convert from S/m to mS/cm.
            data_vars["cond"] = (params.TIME, conductivity * 10.0)

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
                    # For now, use a typical seawater salinity of 35 PSU.
                    pressure_vals = data_vars["press"][1]
                    salinity_vals = np.full_like(pressure_vals, 35.0)

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
        # Handle SBE63 oxygen data (phase and temperature)
        if "SBE63 oxygen phase" in raw_data.columns:
            data_vars["oxygen_phase"] = (params.TIME, raw_data["SBE63 oxygen phase"].values)
        if "SBE63 oxygen temperature" in raw_data.columns:
            data_vars["oxygen_temp"] = (
                params.TIME,
                raw_data["SBE63 oxygen temperature"].values,
            )

    # Create dataset
    ds = xr.Dataset(data_vars, coords={params.TIME: times})

    # Add units as variable attributes
    if "temp" in data_vars:
        ds["temp"].attrs["units"] = "degrees_C"
        ds["temp"].attrs["long_name"] = "Temperature"
    if "cond" in data_vars:
        ds["cond"].attrs["units"] = "mS/cm"
        ds["cond"].attrs["long_name"] = "Conductivity"
    if "press" in data_vars:
        ds["press"].attrs["units"] = "dbar"
        ds["press"].attrs["long_name"] = "Pressure"
    if "oxygen" in data_vars:
        ds["oxygen"].attrs["units"] = "umol/L"
        ds["oxygen"].attrs["long_name"] = "Dissolved Oxygen"
    if "oxygen_ml_l" in data_vars:
        ds["oxygen_ml_l"].attrs["units"] = "ml/L"
        ds["oxygen_ml_l"].attrs["long_name"] = "Dissolved Oxygen (ml/L)"
    if "oxygen_phase" in data_vars:
        ds["oxygen_phase"].attrs["units"] = "degrees"
        ds["oxygen_phase"].attrs["long_name"] = "Oxygen Phase"
    if "oxygen_temp" in data_vars:
        ds["oxygen_temp"].attrs["units"] = "degrees_C"
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
    ds.attrs["data_type"] = "calibrated" if (calibration_coeffs or xmlcon_info) else "raw"

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

    def _load_data(self) -> xr.Dataset:
        """Load the SBE HEX file using the original standalone function."""
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

        self._raw_header = _read_sbe_hex_raw_header(self.input_file)
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

        return ds

    @classmethod
    def format_key(cls) -> str:
        return "sbe-hex"

    @classmethod
    def format_name(cls) -> str:
        return "SeaBird SBE37 HEX"

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
