"""Reader wrapper for Nortek raw binary files."""

from __future__ import annotations

import csv
from contextlib import contextmanager, redirect_stdout
from datetime import datetime
import importlib
import inspect
import io
import json
import logging
import struct
from typing import Any, Callable, Iterator

import numpy as np
import xarray as xr

import seasenselib.parameters as params
from .base import AbstractReader


logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = (".aqd", ".vec", ".wpr")
_NORTEK2_SIGNATURE = b"\xa5\x0a"
_NORTEK2_AVERAGE_RECORD_ID = 22
_NORTEK2_AVGD_RECORD_ID = 38
_NORTEK2_STRING_RECORD_ID = 160
_NORTEK2_HEADER = struct.Struct("<BBBBhhh")
_NORTEK2_AVGD_PAYLOAD_SIZE = 191
_NORTEK2_AVGD_VECTOR_OFFSET = 160
_NORTEK2_AVGD_DECODER = "seasenselib.nortek2.avgd"
_NORTEK_SOUND_SPEED_SETTING = "nortek_sound_speed_setting"
_NORTEK_PRESSURE_PLACEHOLDER = "nortek_pressure_placeholder"
_NORTEK_CORRELATION_PLACEHOLDER = "nortek_correlation_placeholder"
_EXPERIMENTAL_NOTE = (
    "Experimental reader: Nortek raw support is available for early validation "
    "and may be refined as additional Nortek binary variants are tested."
)
_SENSOR_SOURCE_DESCRIPTIONS = {
    "sensor": "Value is interpreted as coming from an instrument sensor.",
    "configured": "Value is interpreted as an instrument or user setting.",
    "placeholder": "Field is present but is not interpreted as a valid value.",
    "unknown": "Source cannot be determined from available metadata.",
}
_NORTEK_SENSOR_BASIS_DESCRIPTIONS = {
    "nortek_user_specified_sound_speed": (
        "Nortek user configuration flag for sound speed."
    ),
    "nortek_pressure_sensor_header": (
        "Nortek header pressure-sensor availability field."
    ),
    "nortek_pressure_nonzero": (
        "Decoded Nortek pressure field contains non-zero values."
    ),
    "nortek_pressure_all_zero": (
        "Decoded Nortek pressure field contains only zero values."
    ),
    "nortek_compass_header": "Nortek header compass availability field.",
    "nortek_tilt_sensor_header": (
        "Nortek header tilt-sensor availability field."
    ),
    "nortek_correlation_all_zero": (
        "Decoded Nortek correlation field contains only zero values."
    ),
}

_AQUADOPP_TEMPLATE_FIELDS = (
    "time",
    "error",
    "batt",
    "c_sound",
    "heading",
    "pitch",
    "roll",
    "status",
    "temp",
)

_NORTEK_ATTR_DEFAULTS: dict[str, dict[str, str]] = {
    "amp": {
        "units": "1",
        "long_name": "Acoustic Signal Amplitude",
        "comment": "Beam acoustic amplitude decoded from the Nortek raw data.",
    },
    "batt": {
        "units": "V",
        "long_name": "Battery Voltage",
        "measurement_type": "Measured",
    },
    "c_sound": {
        "units": "m s-1",
        "long_name": "Speed of Sound",
        "standard_name": "speed_of_sound_in_sea_water",
    },
    _NORTEK_SOUND_SPEED_SETTING: {
        "units": "m s-1",
        "long_name": "Nortek Sound Speed Setting",
        "measurement_type": "Configured",
        "comment": (
            "Sound speed decoded from the Nortek data block. The user "
            "configuration indicates a user-specified sound-speed setting, "
            "so SeaSenseLib does not treat this as a measured water property."
        ),
    },
    "corr": {
        "units": "%",
        "long_name": "Acoustic Signal Correlation",
    },
    _NORTEK_CORRELATION_PLACEHOLDER: {
        "units": "%",
        "long_name": "Nortek Correlation Placeholder",
        "measurement_type": "Placeholder",
        "comment": (
            "The decoded correlation field contains only zeros. For classic "
            "Aquadopp single-point blocks this field can be created by the "
            "backend template even though the raw block does not contain "
            "correlation samples."
        ),
    },
    "error": {
        "units": "1",
        "long_name": "Nortek Error Code",
        "comment": "Instrument error code decoded from the Nortek raw data.",
    },
    "heading": {
        "units": "degree",
        "long_name": "Heading",
        "standard_name": "platform_heading_angle",
        "measurement_type": "Measured",
    },
    "pitch": {
        "units": "degree",
        "long_name": "Pitch",
        "standard_name": "platform_pitch_angle",
        "measurement_type": "Measured",
    },
    "pressure": {
        "units": "dbar",
        "long_name": "Pressure",
        "standard_name": "sea_water_pressure",
        "measurement_type": "Measured",
    },
    _NORTEK_PRESSURE_PLACEHOLDER: {
        "units": "dbar",
        "long_name": "Nortek Pressure Placeholder",
        "measurement_type": "Placeholder",
        "comment": (
            "A pressure field was decoded, but the raw values or instrument "
            "configuration do not support treating it as measured pressure."
        ),
    },
    "roll": {
        "units": "degree",
        "long_name": "Roll",
        "standard_name": "platform_roll_angle",
        "measurement_type": "Measured",
    },
    "status": {
        "units": "1",
        "long_name": "Nortek Status Code",
        "comment": "Instrument status code decoded from the Nortek raw data.",
    },
    "temp": {
        "units": "degree_C",
        "long_name": "Temperature",
        "standard_name": "sea_water_temperature",
        "measurement_type": "Measured",
        "comment": "Temperature decoded from the Nortek raw data block.",
    },
    "vel": {
        "units": "m s-1",
        "long_name": "Water Velocity",
    },
}


def _read_nortek_import() -> tuple[Callable[..., xr.Dataset], str]:
    """Import the MHKiT DOLfYN Nortek reader lazily."""
    try:
        from mhkit import dolfyn
    except ModuleNotFoundError as exc:
        if exc.name != "mhkit":
            raise
        try:
            import dolfyn  # type: ignore[no-redef]
        except ModuleNotFoundError as fallback_exc:
            raise ImportError(
                "NortekRawReader requires MHKiT with DOLfYN support. "
                'Install it with: pip install "mhkit[dolfyn]"'
            ) from fallback_exc
        source_prefix = "dolfyn"
    else:
        source_prefix = "mhkit.dolfyn"

    read_nortek = getattr(dolfyn.io, "read_nortek", None)
    source = f"{source_prefix}.io.read_nortek"
    if not callable(read_nortek):
        try:
            read_nortek = dolfyn.io.nortek.read_nortek
        except AttributeError as exc:
            raise ImportError(
                "The installed DOLfYN package does not expose "
                "io.nortek.read_nortek(). Please install a recent MHKiT build "
                'with: pip install "mhkit[dolfyn]"'
            ) from exc
        source = f"{source_prefix}.io.nortek.read_nortek"

    return read_nortek, source


def _read_nortek2_import() -> tuple[Callable[..., xr.Dataset], str]:
    """Import the MHKiT DOLfYN Nortek Gen2/AD2CP reader lazily."""
    try:
        from mhkit import dolfyn
    except ModuleNotFoundError as exc:
        if exc.name != "mhkit":
            raise
        try:
            import dolfyn  # type: ignore[no-redef]
        except ModuleNotFoundError as fallback_exc:
            raise ImportError(
                "NortekRawReader requires MHKiT with DOLfYN support. "
                'Install it with: pip install "mhkit[dolfyn]"'
            ) from fallback_exc
        source_prefix = "dolfyn"
    else:
        source_prefix = "mhkit.dolfyn"

    read_signature = getattr(dolfyn.io, "read_signature", None)
    source = f"{source_prefix}.io.read_signature"
    if not callable(read_signature):
        try:
            nortek2_module = getattr(dolfyn.io, "nortek2")
        except AttributeError:
            try:
                nortek2_module = importlib.import_module(
                    f"{source_prefix}.io.nortek2"
                )
            except ImportError as exc:
                raise ImportError(
                    "The installed DOLfYN package does not expose "
                    "io.nortek2.read_signature(). Please install a recent "
                    'MHKiT build with: pip install "mhkit[dolfyn]"'
                ) from exc
        try:
            read_signature = nortek2_module.read_signature
        except AttributeError as exc:
            raise ImportError(
                "The installed DOLfYN package does not expose "
                "io.nortek2.read_signature(). Please install a recent MHKiT "
                'build with: pip install "mhkit[dolfyn]"'
            ) from exc
        source = f"{source_prefix}.io.nortek2.read_signature"

    return read_signature, source


class _Nortek2PacketInspector:
    """Inspect Nortek Gen2 packet headers without decoding scientific data.

    This class is only responsible for routing decisions in ``NortekRawReader``.
    It performs cheap binary checks that are safe to run before importing or
    invoking DOLfYN:

    * ``looks_like_file()`` checks the first bytes for the Nortek Gen2/AD2CP
      sync signature.
    * ``looks_like_avgd_product()`` scans the first few packet headers and
      identifies already averaged ID 38 products.
    * ``iter_headers()`` exposes the minimal header fields needed for those
      checks and skips over payloads without interpreting them.

    The class deliberately does not parse samples, metadata strings, checksums,
    or instrument configuration. Keeping it that narrow makes the file-type
    selection fast and keeps decoding responsibility in the reader/decoder that
    actually handles the chosen data layout.
    """

    @staticmethod
    def looks_like_file(filename: str) -> bool:
        """Return True when the file starts with the Nortek Gen2 AD2CP header."""
        with open(filename, "rb") as file:
            return file.read(len(_NORTEK2_SIGNATURE)) == _NORTEK2_SIGNATURE

    @classmethod
    def looks_like_avgd_product(cls, filename: str) -> bool:
        """Return True when the first data packet is the averaged ID 38 product."""
        try:
            for header in cls.iter_headers(filename, max_packets=16):
                if header["id"] == _NORTEK2_STRING_RECORD_ID:
                    continue
                return header["id"] == _NORTEK2_AVGD_RECORD_ID
        except ValueError:
            return False
        return False

    @staticmethod
    def iter_headers(
        filename: str,
        max_packets: int | None = None,
    ) -> Iterator[dict[str, int]]:
        """Yield sequential Nortek2 packet headers without decoding payloads."""
        packets_read = 0
        with open(filename, "rb") as file:
            while max_packets is None or packets_read < max_packets:
                position = file.tell()
                header_bytes = file.read(_NORTEK2_HEADER.size)
                if not header_bytes:
                    return
                if len(header_bytes) != _NORTEK2_HEADER.size:
                    raise ValueError("Truncated Nortek2 packet header.")

                sync, header_size, record_id, family, size, checksum, hchecksum = (
                    _NORTEK2_HEADER.unpack(header_bytes)
                )
                if sync != 165:
                    raise ValueError("Out-of-sync Nortek2 packet header.")
                if header_size != _NORTEK2_HEADER.size:
                    raise ValueError(
                        "Unsupported Nortek2 packet header size "
                        f"{header_size}; expected {_NORTEK2_HEADER.size}."
                    )
                if size < 0:
                    raise ValueError(
                        f"Invalid Nortek2 packet payload size: {size}."
                    )

                yield {
                    "position": position,
                    "header_size": header_size,
                    "id": record_id,
                    "family": family,
                    "size": size,
                    "checksum": checksum,
                    "header_checksum": hchecksum,
                }
                file.seek(size, 1)
                packets_read += 1


class _Nortek2AvgdProductDecoder:
    """Decode Nortek2 averaged ID 38 product files into an xarray dataset.

    Responsibility
        This class is a small SeaSenseLib fallback decoder for Nortek Gen2
        ``*_avgd.aqd`` files. Those files are not full raw burst streams; they
        are already averaged products containing string metadata packets and ID
        38 data packets. In the validated Aquadopp Gen2 examples, each ID 38
        packet represents one averaged sample.

    Why it exists
        The installed DOLfYN Nortek2 reader can handle normal Gen2 packet
        streams, but its indexer does not include the ID 38 product packet
        family. It therefore builds an empty index and fails before returning
        data. Rather than broadening DOLfYN with a runtime monkey patch, this
        decoder handles the unsupported product format directly.

    How it works
        The decoder reads packets sequentially, parses string records into
        structured raw metadata, parses ID 38 payload fields at fixed offsets,
        and builds a DOLfYN-like ``*_avg`` dataset with ``time_avg``,
        ``range_avg``, ``beam``, ``dir`` and ``dirIMU`` coordinates.

    Boundaries
        The implementation is intentionally conservative. It currently supports
        the observed 191-byte ID 38 payload with one cell and three beams. Other
        Nortek2 averaged product layouts should add a guarded branch here rather
        than weakening the existing validation. If DOLfYN gains native ID 38
        support later, this fallback can be disabled or changed to try DOLfYN
        first after regression tests confirm identical values.
    """

    @classmethod
    def read(cls, filename: str) -> xr.Dataset:
        """Read a Nortek2 averaged-product file into an xarray dataset."""
        config: dict[str, Any] = {}
        records: list[dict[str, Any]] = []
        string_records: list[dict[str, Any]] = []

        with open(filename, "rb") as file:
            while True:
                header_position = file.tell()
                header_bytes = file.read(_NORTEK2_HEADER.size)
                if not header_bytes:
                    break
                if len(header_bytes) != _NORTEK2_HEADER.size:
                    raise ValueError("Truncated Nortek2 averaged-product header.")

                sync, header_size, record_id, family, size, checksum, hchecksum = (
                    _NORTEK2_HEADER.unpack(header_bytes)
                )
                if sync != 165:
                    raise ValueError(
                        "Out-of-sync Nortek2 averaged-product packet at byte "
                        f"{header_position}."
                    )
                if header_size != _NORTEK2_HEADER.size:
                    raise ValueError(
                        "Unsupported Nortek2 averaged-product header size "
                        f"{header_size}; expected {_NORTEK2_HEADER.size}."
                    )
                payload = file.read(size)
                if len(payload) != size:
                    raise ValueError("Truncated Nortek2 averaged-product payload.")

                if record_id == _NORTEK2_STRING_RECORD_ID:
                    parsed = cls._parse_string_record(payload)
                    string_records.append(parsed)
                    if not config and parsed.get("blocks"):
                        config = parsed["blocks"]
                elif record_id == _NORTEK2_AVGD_RECORD_ID:
                    records.append(cls._parse_record(payload))
                else:
                    logger.debug(
                        "Skipping unsupported Nortek2 averaged-product packet "
                        "ID %s at byte %s",
                        record_id,
                        header_position,
                    )

        if not records:
            raise ValueError("No Nortek2 averaged ID 38 records found.")
        return cls._build_dataset(records, config, string_records)

    @classmethod
    def _parse_string_record(cls, payload: bytes) -> dict[str, Any]:
        """Parse a Nortek2 string record into structured raw metadata."""
        if not payload:
            return {"id": None, "text": "", "blocks": {}}

        string_id = int(payload[0])
        text = payload[1:].rstrip(b"\x00").decode("utf-8", errors="replace")
        return {
            "id": string_id,
            "text": text,
            "blocks": cls._parse_config_text(text),
        }

    @classmethod
    def _parse_config_text(cls, text: str) -> dict[str, Any]:
        """Parse Nortek2 comma-separated configuration text."""
        blocks: dict[str, Any] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or "," not in line:
                continue
            name, values = line.split(",", 1)
            block_name = name[3:] if name.startswith("GET") else name
            parsed_values = cls._parse_assignments(values)

            if block_name in blocks:
                existing = blocks[block_name]
                if not isinstance(existing, list):
                    blocks[block_name] = [existing]
                blocks[block_name].append(parsed_values)
            else:
                blocks[block_name] = parsed_values
        return blocks

    @classmethod
    def _parse_assignments(cls, text: str) -> dict[str, Any] | str:
        """Parse a comma-separated key=value list, preserving text if needed."""
        assignments: dict[str, Any] = {}
        for item in next(csv.reader([text])):
            if "=" not in item:
                return text
            key, value = item.split("=", 1)
            assignments[key.strip()] = cls._coerce_value(value.strip())
        return assignments

    @staticmethod
    def _coerce_value(value: str) -> Any:
        """Coerce Nortek2 configuration values to simple Python scalars."""
        if len(value) >= 2 and value[0] == value[-1] == '"':
            return value[1:-1]
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

    @classmethod
    def _parse_record(cls, payload: bytes) -> dict[str, Any]:
        """Parse one Nortek2 averaged ID 38 payload.

        The offsets used here are taken from the observed Aquadopp Gen2 averaged
        product layout and validated against Nortek's own CSV export. Values in
        this product are already averaged/stored as floats for scalar fields,
        while the vector block at byte 160 keeps velocity as signed millimetres
        per second, amplitude as half-counts, and correlation as integer
        percent-like values.
        """
        if len(payload) != _NORTEK2_AVGD_PAYLOAD_SIZE:
            raise ValueError(
                "Unsupported Nortek2 averaged-product payload size "
                f"{len(payload)}; expected {_NORTEK2_AVGD_PAYLOAD_SIZE}."
            )

        year, month, day, hour, minute, second, usec100 = struct.unpack_from(
            "<6BH",
            payload,
            24,
        )
        velocity = np.frombuffer(payload, dtype="<i2", count=3, offset=_NORTEK2_AVGD_VECTOR_OFFSET).astype(np.float32)
        amplitude = np.frombuffer(
            payload,
            dtype=np.uint8,
            count=3,
            offset=166,
        ).astype(np.float32)
        correlation = np.frombuffer(
            payload,
            dtype=np.uint8,
            count=3,
            offset=169,
        ).copy()

        return {
            "version": payload[16],
            "serial_number": struct.unpack_from("<I", payload, 20)[0],
            "time": cls._datetime(
                year,
                month,
                day,
                hour,
                minute,
                second,
                usec100,
            ),
            "c_sound": struct.unpack_from("<f", payload, 32)[0],
            "temp": struct.unpack_from("<f", payload, 36)[0],
            "pressure": struct.unpack_from("<f", payload, 40)[0],
            "pressure_with_offset": struct.unpack_from("<f", payload, 44)[0],
            "heading": struct.unpack_from("<f", payload, 48)[0],
            "pitch": struct.unpack_from("<f", payload, 52)[0],
            "roll": struct.unpack_from("<f", payload, 56)[0],
            "cell_size": struct.unpack_from("<f", payload, 80)[0],
            "blank_dist": struct.unpack_from("<f", payload, 84)[0],
            "batt": struct.unpack_from("<f", payload, 88)[0],
            "temp_press": struct.unpack_from("<f", payload, 92)[0],
            "temp_mag": struct.unpack_from("<f", payload, 96)[0] / 10.0,
            "temp_clock": struct.unpack_from("<f", payload, 100)[0],
            "mag": np.array(struct.unpack_from("<3f", payload, 104), dtype=np.float32),
            "accel": np.array(
                struct.unpack_from("<3f", payload, 116),
                dtype=np.float32,
            ),
            "ambig_vel": struct.unpack_from("<f", payload, 128)[0],
            "stm_data_scattering": struct.unpack_from("<f", payload, 148)[0],
            "stm_data_high_range": struct.unpack_from("<f", payload, 152)[0],
            "vel": velocity * 0.001,
            "amp": amplitude * 0.5,
            "corr": correlation,
            "percent_good": int(payload[172]),
        }

    @staticmethod
    def _datetime(
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
        second: int,
        usec100: int,
    ) -> np.datetime64:
        """Convert Nortek2 timestamp fields to numpy datetime64."""
        try:
            value = datetime(
                year + 1900,
                month + 1,
                day,
                hour,
                minute,
                second,
                usec100 * 100,
            )
        except ValueError:
            return np.datetime64("NaT", "ns")
        return np.datetime64(value, "ns")

    @classmethod
    def _build_dataset(
        cls,
        records: list[dict[str, Any]],
        config: dict[str, Any],
        string_records: list[dict[str, Any]],
    ) -> xr.Dataset:
        """Build an xarray dataset from parsed Nortek2 averaged-product records."""
        avg_config = (
            config.get("AVG", {}) if isinstance(config.get("AVG"), dict) else {}
        )
        coord_axes = str(avg_config.get("CY", "ENU")).strip().upper()
        n_cells = int(avg_config.get("NC", 1) or 1)
        n_beams = int(avg_config.get("NB", 3) or 3)
        if n_cells != 1 or n_beams != 3:
            raise ValueError(
                "Nortek2 averaged ID 38 products are currently supported for "
                f"3 beams and 1 cell; got {n_beams} beams and {n_cells} cells."
            )

        time = np.array([record["time"] for record in records], dtype="datetime64[ns]")
        range_value = float(records[0]["blank_dist"] + records[0]["cell_size"])
        attrs = cls._attrs(config, records, coord_axes, string_records)

        ds = xr.Dataset(
            data_vars={
                "c_sound_avg": ("time_avg", cls._record_array(records, "c_sound")),
                "temp_avg": ("time_avg", cls._record_array(records, "temp")),
                "pressure_avg": ("time_avg", cls._record_array(records, "pressure")),
                "pressure_with_offset_avg": (
                    "time_avg",
                    cls._record_array(records, "pressure_with_offset"),
                ),
                "heading_avg": ("time_avg", cls._record_array(records, "heading")),
                "pitch_avg": ("time_avg", cls._record_array(records, "pitch")),
                "roll_avg": ("time_avg", cls._record_array(records, "roll")),
                "batt_avg": ("time_avg", cls._record_array(records, "batt")),
                "temp_press_avg": (
                    "time_avg",
                    cls._record_array(records, "temp_press"),
                ),
                "temp_mag_avg": ("time_avg", cls._record_array(records, "temp_mag")),
                "temp_clock_avg": (
                    "time_avg",
                    cls._record_array(records, "temp_clock"),
                ),
                "ambig_vel_avg": (
                    "time_avg",
                    cls._record_array(records, "ambig_vel"),
                ),
                "stm_data_scattering_avg": (
                    "time_avg",
                    cls._record_array(records, "stm_data_scattering"),
                ),
                "stm_data_high_range_avg": (
                    "time_avg",
                    cls._record_array(records, "stm_data_high_range"),
                ),
                "percent_good_avg": (
                    "time_avg",
                    cls._record_array(records, "percent_good", dtype=np.uint8),
                ),
                "mag_avg": (("dirIMU", "time_avg"), cls._record_matrix(records, "mag")),
                "accel_avg": (
                    ("dirIMU", "time_avg"),
                    cls._record_matrix(records, "accel"),
                ),
                "vel_avg": (
                    ("dir", "range_avg", "time_avg"),
                    cls._record_matrix(records, "vel")[:, np.newaxis, :],
                ),
                "amp_avg": (
                    ("beam", "range_avg", "time_avg"),
                    cls._record_matrix(records, "amp")[:, np.newaxis, :],
                ),
                "corr_avg": (
                    ("beam", "range_avg", "time_avg"),
                    cls._record_matrix(records, "corr", dtype=np.uint8)[
                        :,
                        np.newaxis,
                        :,
                    ],
                ),
            },
            coords={
                "time_avg": ("time_avg", time),
                "range_avg": ("range_avg", np.array([range_value], dtype=np.float64)),
                "beam": ("beam", np.arange(1, n_beams + 1, dtype=np.int32)),
                "dir": ("dir", cls._direction_labels(coord_axes)),
                "dirIMU": ("dirIMU", ["E", "N", "U"]),
            },
            attrs=attrs,
        )
        return ds

    @staticmethod
    def _record_array(
        records: list[dict[str, Any]],
        key: str,
        dtype: Any = np.float32,
    ) -> np.ndarray:
        """Return a 1-D array from parsed record dictionaries."""
        return np.asarray([record[key] for record in records], dtype=dtype)

    @staticmethod
    def _record_matrix(
        records: list[dict[str, Any]],
        key: str,
        dtype: Any = np.float32,
    ) -> np.ndarray:
        """Return a 2-D component-by-time array from parsed record dictionaries."""
        return np.stack(
            [np.asarray(record[key], dtype=dtype) for record in records],
            axis=1,
        )

    @staticmethod
    def _direction_labels(coord_axes: str) -> list[str]:
        """Return DOLfYN-like direction labels for a Nortek coordinate system."""
        if coord_axes == "ENU":
            return ["E", "N", "U"]
        if coord_axes == "XYZ":
            return ["X", "Y", "Z"]
        return ["1", "2", "3"]

    @staticmethod
    def _attrs(
        config: dict[str, Any],
        records: list[dict[str, Any]],
        coord_axes: str,
        string_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return dataset attrs for Nortek2 averaged-product records."""
        id_config = config.get("ID", {}) if isinstance(config.get("ID"), dict) else {}
        model = id_config.get("STR", "Aquadopp Gen2")
        serial_number = id_config.get("SN") or records[0]["serial_number"]
        coord_sys = {"ENU": "earth", "XYZ": "inst", "BEAM": "beam"}.get(
            coord_axes,
            coord_axes.lower(),
        )
        return {
            "filehead_config": json.dumps(config, ensure_ascii=False, default=str),
            "nortek_string_records": json.dumps(
                string_records,
                ensure_ascii=False,
                default=str,
            ),
            "inst_model": model,
            "inst_make": "Nortek",
            "inst_type": "ADCP",
            "serial_number": str(serial_number),
            "coord_sys": coord_sys,
            "coord_sys_axes_avg": coord_axes,
            "n_cells_avg": 1,
            "n_beams_avg": 3,
            "decoder_note": (
                "Nortek2 averaged ID 38 product decoded by SeaSenseLib because "
                "the installed DOLfYN Nortek2 indexer does not include this "
                "packet family."
            ),
        }


class _ClassicAquadoppTemplateRepair:
    """Patch incomplete DOLfYN classic Aquadopp templates for one read call.

    Responsibility
        This class handles a compatibility issue in some DOLfYN/MHKiT versions
        for classic Nortek Aquadopp ``.aqd`` files. The backend template for
        0x01 data blocks can miss timestamp and environmental fields that are
        present in the matching system template.

    What it fixes
        When the template is incomplete, DOLfYN may fail to decode classic
        Aquadopp single-point blocks even though DOLfYN already contains the
        necessary field definitions elsewhere. This repair copies only the
        missing known fields from ``vec_sys`` into ``vec_data``.

    How it stays bounded
        The patch is applied only for ``.aqd`` files, only when the missing
        fields are found in DOLfYN's own definitions, and only inside the
        context manager around a single backend read. Original DOLfYN module
        state is restored in ``finally``. SeaSenseLib does not reinterpret the
        binary payload here; DOLfYN still performs the actual decode.
    """

    @classmethod
    @contextmanager
    def context(
        cls,
        filename: str,
        read_nortek: Callable[..., xr.Dataset],
    ) -> Iterator[dict[str, str] | None]:
        """Temporarily fill missing Aquadopp 0x01 template fields if needed."""
        if not filename.lower().endswith(".aqd"):
            yield None
            return

        module_name = getattr(read_nortek, "__module__", "")
        if not module_name:
            yield None
            return

        try:
            nortek_module = importlib.import_module(module_name)
            defs_base = (
                module_name
                if module_name.endswith(".io")
                else module_name.rsplit(".", 1)[0]
            )
            defs_module = importlib.import_module(f"{defs_base}.nortek_defs")
        except (ImportError, ValueError):
            yield None
            return

        vec_data = getattr(defs_module, "vec_data", None)
        vec_sys = getattr(defs_module, "vec_sys", None)
        if not isinstance(vec_data, dict) or not isinstance(vec_sys, dict):
            yield None
            return

        missing = [
            field
            for field in _AQUADOPP_TEMPLATE_FIELDS
            if field not in vec_data and field in vec_sys
        ]
        if not missing:
            yield None
            return

        patched = dict(vec_data)
        for field in missing:
            patched[field] = vec_sys[field]

        module_defs = getattr(nortek_module, "defs", None)
        if not hasattr(module_defs, "vec_data"):
            yield None
            return

        original_defs = defs_module.vec_data
        original_nortek_defs = module_defs.vec_data
        defs_module.vec_data = patched
        module_defs.vec_data = patched
        try:
            yield {
                "name": "aquadopp_single_point_template",
                "scope": "in_memory_for_this_read",
                "reason": (
                    "Adds missing timestamp and environmental variable "
                    "definitions for classic Aquadopp 0x01 blocks when the "
                    "backend template is incomplete."
                ),
            }
        finally:
            defs_module.vec_data = original_defs
            module_defs.vec_data = original_nortek_defs


class _Nortek2AquadoppAverageTailRepair:
    """Patch DOLfYN's Gen2 average-record reader for one backend read call.

    Responsibility
        This class contains the scoped compatibility repair used for full
        Nortek Gen2/Aquadopp2 ``.aqd`` packet streams that are otherwise decoded
        by DOLfYN's Nortek2 reader.

    What it fixes
        In the validated Aquadopp Gen2 file, DOLfYN recognizes average record
        packets but its private payload layout stops before the final vector
        sample block. Velocity, amplitude and correlation bytes remain unread.
        The next packet header is then read from the wrong file position, which
        leads to DOLfYN's ``Out of sync!`` error.

    How it works
        The context manager temporarily wraps DOLfYN's private ``_read_hdr`` and
        ``_read_burst`` methods. The wrapper records the current packet boundary,
        lets DOLfYN decode the normal fields first, then checks whether bytes are
        still left inside a supported average packet. If the unread tail matches
        the guarded Aquadopp2 vector-tail layout, it writes the raw
        ``vel``/``amp``/``corr`` values back into DOLfYN's arrays before DOLfYN
        applies its usual scaling and dataset construction.

    How it stays bounded
        The patch is installed only during one ``read_signature()`` call and is
        always removed in ``finally``. It only acts on average record ID 22, only
        when DOLfYN produced ``vel``, ``amp`` and ``corr`` arrays, and only when
        ``DatOffset`` plus unread packet size match the validated layout. If a
        future DOLfYN release consumes the whole packet natively, no unread tail
        remains and this repair becomes a no-op.
    """

    @classmethod
    @contextmanager
    def context(
        cls,
        read_signature: Callable[..., xr.Dataset],
    ) -> Iterator[dict[str, str] | None]:
        """Temporarily repair DOLfYN's Aquadopp2 average-record alignment.

        This is a scoped monkey patch around DOLfYN's private Nortek2 reader
        class. It exists for AD2CP/Aquadopp2 average packets where DOLfYN can
        identify and start reading the packet, but its internal payload
        structure is shorter than the packet size declared in the binary header.
        In the validated example this leaves the final velocity, amplitude and
        correlation bytes unread. Without intervention, DOLfYN then reads the
        next packet header from the wrong byte position and raises
        ``Out of sync!``.

        The patch is intentionally narrow:

        * It is installed only while one ``read_signature()`` call is running.
        * The original ``_read_hdr`` and ``_read_burst`` methods are restored in
          the ``finally`` block.
        * It does not replace DOLfYN's decoder. DOLfYN still parses the normal
          packet fields, creates the xarray structure and applies its normal
          scaling.
        * SeaSenseLib only records the current packet boundary and, when a
          supported unread tail is present, overwrites the raw
          ``vel``/``amp``/``corr`` arrays before DOLfYN's science-unit
          conversion step.

        If a future DOLfYN version reads this packet layout completely, there
        will be no unread tail and this repair becomes a no-op. At that point
        the compatibility context can be removed or disabled by default after
        regression tests confirm the upstream decoder is correct.
        """
        module_name = getattr(read_signature, "__module__", "")
        if not module_name:
            yield None
            return

        try:
            nortek2_module = importlib.import_module(module_name)
        except (ImportError, ValueError):
            yield None
            return

        reader_class = getattr(nortek2_module, "_Ad2cpReader", None)
        if reader_class is None:
            yield None
            return
        if not hasattr(reader_class, "_read_hdr"):
            yield None
            return
        if not hasattr(reader_class, "_read_burst"):
            yield None
            return

        original_read_header = reader_class._read_hdr
        original_read_burst = reader_class._read_burst

        def patched_read_header(self, do_cs=False):
            # DOLfYN returns only the parsed header, but the repair needs to
            # know where the payload started so it can compare the declared
            # packet size with the file pointer after the burst reader ran.
            header_start = self.f.tell()
            header = original_read_header(self, do_cs=do_cs)
            self._seasenselib_last_payload_start = header_start + int(
                header.get("hsz", 10)
            )
            self._seasenselib_last_header = header
            return header

        def patched_read_burst(self, record_id, data, ensemble_index, echo=False):
            payload_start = getattr(self, "_seasenselib_last_payload_start", None)
            header = getattr(self, "_seasenselib_last_header", None)
            # First let DOLfYN do its ordinary decoding. The repair below only
            # touches bytes DOLfYN demonstrably left unread in the same packet.
            original_read_burst(self, record_id, data, ensemble_index, echo=echo)
            if header is None or payload_start is None:
                return
            cls._repair_tail(
                self,
                header,
                record_id,
                data,
                ensemble_index,
                payload_start,
            )

        reader_class._read_hdr = patched_read_header
        reader_class._read_burst = patched_read_burst
        try:
            yield {
                "name": "nortek2_aquadopp_average_record_tail",
                "scope": "in_memory_for_this_read",
                "reason": (
                    "Repairs AD2CP/Aquadopp2 average records where DOLfYN's "
                    "layout leaves the final velocity, amplitude and "
                    "correlation samples unread."
                ),
            }
        finally:
            reader_class._read_hdr = original_read_header
            reader_class._read_burst = original_read_burst

    @classmethod
    def _repair_tail(
        cls,
        reader: Any,
        header: dict[str, Any],
        record_id: int,
        data: dict[str, Any],
        ensemble_index: int,
        payload_start: int,
    ) -> None:
        """Read Aquadopp2 tail fields when DOLfYN's structure is too short.

        DOLfYN has already populated ``data`` for the current ensemble when this
        method runs. The file pointer therefore tells us how many bytes DOLfYN
        consumed. The binary packet header tells us how many bytes belong to the
        payload. If bytes are left inside an average data packet, this method
        checks whether the tail is large enough to contain the vector sample
        block:

        ``int16 velocity`` + ``uint8 amplitude`` + ``uint8 correlation``

        The values are written back into DOLfYN's raw arrays, not directly into
        an xarray object. DOLfYN's later ``sci_data()`` step still applies the
        velocity scale and amplitude half-count scale. This keeps the repair as
        close as possible to DOLfYN's own processing path.

        Unsupported packets simply return. The only hard error is a packet that
        already looked repairable but then cannot provide the required tail
        bytes, because silently continuing there would leave known-bad vector
        values.
        """
        if record_id != _NORTEK2_AVERAGE_RECORD_ID:
            return
        if not {"vel", "amp", "corr"}.issubset(data):
            return

        payload_size = int(header.get("sz", 0))
        payload_end = payload_start + payload_size
        unread_size = payload_end - reader.f.tell()
        if unread_size <= 0:
            return

        velocity_shape = tuple(
            int(size) for size in np.asarray(data["vel"]).shape[:-1]
        )
        if not velocity_shape:
            return

        value_count = int(np.prod(velocity_shape))
        velocity_nbytes = value_count * np.dtype("<i2").itemsize
        required_size = velocity_nbytes + value_count + value_count
        if not cls._is_tail_vector_layout(
            data,
            ensemble_index,
            unread_size,
            required_size,
        ):
            return

        tail = reader.f.read(unread_size)
        if len(tail) < required_size:
            raise ValueError(
                "Unsupported Nortek Gen2 average-record layout: the unread "
                "packet tail is too short to contain velocity, amplitude and "
                "correlation samples."
            )

        vector_block = tail[-required_size:]
        velocity_stop = velocity_nbytes
        amplitude_stop = velocity_stop + value_count

        velocity = np.frombuffer(vector_block[:velocity_stop], dtype="<i2").reshape(
            velocity_shape
        )
        amplitude = np.frombuffer(
            vector_block[velocity_stop:amplitude_stop],
            dtype=np.uint8,
        ).reshape(velocity_shape)
        correlation = np.frombuffer(
            vector_block[amplitude_stop:],
            dtype=np.uint8,
        ).reshape(velocity_shape)

        data["vel"][..., ensemble_index] = velocity
        data["amp"][..., ensemble_index] = amplitude
        data["corr"][..., ensemble_index] = correlation

    @classmethod
    def _is_tail_vector_layout(
        cls,
        data: dict[str, Any],
        ensemble_index: int,
        unread_size: int,
        required_size: int,
    ) -> bool:
        """Return True when the packet tail can contain the vector block.

        The guard intentionally uses observed binary layout evidence instead of
        a sidecar file name or a broad instrument label:

        * ``DatOffset == 76`` identifies the Aquadopp2 average packet header
          length seen in the validated Gen2 data.
        * ``unread_size >= required_size`` ensures the remaining packet bytes
          can hold velocity, amplitude and correlation for the decoded
          beam/cell shape.

        If DOLfYN adds native support later, the unread size will be zero and
        this predicate will not trigger. If another Nortek2 layout appears, this
        method is the place to add a new guarded branch rather than widening the
        current repair blindly.
        """
        dat_offset = cls._value_at_ensemble(data.get("DatOffset"), ensemble_index)
        return dat_offset == 76 and unread_size >= required_size

    @staticmethod
    def _value_at_ensemble(value: Any, ensemble_index: int) -> int | None:
        """Return a scalar value from an ensemble-indexed backend array.

        DOLfYN stores packet fields in numpy arrays with the ensemble dimension
        last, even for fields that are scalar in the binary record. The repair
        only needs the current ensemble's ``DatOffset`` value, so this helper
        hides the numpy indexing details and returns ``None`` when the expected
        field is absent or has an unexpected shape.
        """
        if value is None:
            return None
        values = np.asarray(value)
        try:
            if values.ndim == 0:
                return int(values.item())
            return int(values[..., ensemble_index].item())
        except (IndexError, TypeError, ValueError):
            return None


class NortekRawReader(AbstractReader):
    """Read Nortek raw binary files with MHKiT DOLfYN.

    Responsibility
        ``NortekRawReader`` is the public SeaSenseLib wrapper for Nortek binary
        raw-like files. It keeps backend decoding as close as possible to DOLfYN
        while adding SeaSenseLib provenance, conservative metadata annotations,
        and safe scalar variable mappings.

    Decode path selection
        Classic Nortek files are delegated to DOLfYN's classic Nortek reader.
        Gen2/AD2CP-style ``.aqd`` files are selected from the binary header. Full
        Gen2 raw packet streams go through DOLfYN's Nortek2 reader, optionally
        with the scoped average-record repair above. Already averaged ID 38
        ``*_avgd.aqd`` products use the small SeaSenseLib fallback decoder
        because current DOLfYN builds do not index that packet family.

    Compatibility policy
        The compatibility helpers are intentionally narrow and temporary: they
        patch DOLfYN only in memory, only during a single read, and only after
        guarded evidence from the file/backend state indicates the known layout
        issue. They are not intended to replace DOLfYN as the normal decoder.

    This reader is marked experimental because support is still being validated
    across Nortek raw variants.

    Velocity is intentionally preserved as vector variable ``vel``. Its
    component meaning depends on ``ds.attrs["coord_sys"]`` and the ``dir``
    coordinate, so automatic CF component variables would be a scientific
    interpretation step rather than a safe reader cleanup.
    """

    def __init__(
        self,
        input_file: str,
        userdata: bool | str | None = None,
        nens: int | tuple[int, int] | None = None,
        debug: bool | None = None,
        do_checksum: bool | None = None,
        rebuild_index: bool | None = None,
        dual_profile: bool | None = None,
        show_decoder_output: bool = False,
        apply_aquadopp_compatibility: bool = True,
        apply_nortek2_aquadopp_compatibility: bool = True,
        mapping: dict | None = None,
        **kwargs,
    ):
        """Initialize the Nortek raw reader.

        Parameters
        ----------
        input_file
            Path to a Nortek raw binary file. This reader currently advertises
            classic Nortek ``.aqd``, ``.vec`` and ``.wpr`` files.
        userdata
            Passed to DOLfYN. Use ``True`` to search for a sibling
            ``*.userdata.json`` file, ``False`` to skip it, or a string path
            to use a specific metadata file. ``None`` keeps DOLfYN's default.
        nens
            Number of ensembles to read, or a start/stop tuple for backend
            versions that support sliced reads.
        debug
            DOLfYN debug flag. ``None`` keeps DOLfYN's default.
        do_checksum
            Ask DOLfYN to verify Nortek block checksums. ``None`` keeps the
            backend default.
        rebuild_index
            Passed to DOLfYN's Gen2/AD2CP reader. ``None`` keeps the backend
            default.
        dual_profile
            Passed to DOLfYN's Gen2/AD2CP reader. ``None`` keeps the backend
            default.
        show_decoder_output
            If True, let the backend decoder write progress messages to
            stdout. The default keeps SeaSenseLib reads quiet.
        apply_aquadopp_compatibility
            Apply a small in-memory compatibility patch for DOLfYN builds where
            classic Aquadopp 0x01 blocks miss timestamp/environmental template
            definitions. The raw binary values are still decoded by DOLfYN.
        apply_nortek2_aquadopp_compatibility
            Apply a small in-memory compatibility patch for Nortek Gen2
            Aquadopp average records where DOLfYN's packet layout is too short
            for the recorded payload. This affects full Gen2 raw ``.aqd``
            packet streams read through DOLfYN. Averaged ID 38 ``*_avgd.aqd``
            products use SeaSenseLib's separate fallback decoder instead.
        mapping
            Additional SeaSenseLib variable mappings.
        **kwargs
            Base reader options such as ``perform_default_postprocessing`` and
            ``use_steps``.
        """
        self._userdata = userdata
        self._nens = nens
        self._debug = debug
        self._do_checksum = do_checksum
        self._rebuild_index = rebuild_index
        self._dual_profile = dual_profile
        self._show_decoder_output = show_decoder_output
        self._apply_aquadopp_compatibility = apply_aquadopp_compatibility
        self._apply_nortek2_aquadopp_compatibility = (
            apply_nortek2_aquadopp_compatibility
        )
        self._decoder_source = ""
        self._compatibility_notes: list[dict[str, str]] = []
        self._raw_metadata_blocks: dict[str, Any] = {}
        self._raw_metadata_variables: dict[str, Any] = {}
        super().__init__(input_file, mapping, **kwargs)
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...]:
        """Return supported Nortek raw binary extensions."""
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
                "bool",
                None,
                "DOLfYN debug flag.",
            ),
            cls._reader_arg(
                "do_checksum",
                "bool",
                None,
                "Ask DOLfYN to verify Nortek block checksums.",
            ),
            cls._reader_arg(
                "rebuild_index",
                "bool",
                None,
                "Pass DOLfYN's Gen2/AD2CP rebuild-index option.",
            ),
            cls._reader_arg(
                "dual_profile",
                "bool",
                None,
                "Pass DOLfYN's Gen2/AD2CP dual-profile option.",
            ),
            cls._reader_arg(
                "show_decoder_output",
                "bool",
                False,
                "Allow backend decoder progress messages on stdout.",
            ),
            cls._reader_arg(
                "apply_aquadopp_compatibility",
                "bool",
                True,
                "Apply SeaSenseLib's classic Aquadopp compatibility patch when needed.",
            ),
            cls._reader_arg(
                "apply_nortek2_aquadopp_compatibility",
                "bool",
                True,
                "Apply SeaSenseLib's Nortek Gen2 Aquadopp compatibility patch when needed.",
            ),
        ]

    def _load_data(self) -> xr.Dataset:
        """Load the Nortek raw data and return an xarray Dataset."""
        if _Nortek2PacketInspector.looks_like_file(self.input_file):
            if _Nortek2PacketInspector.looks_like_avgd_product(self.input_file):
                self._decoder_source = _NORTEK2_AVGD_DECODER
                ds = _Nortek2AvgdProductDecoder.read(self.input_file)
            else:
                read_nortek2, source = _read_nortek2_import()
                self._decoder_source = source
                ds = self._call_read_nortek2(read_nortek2)
        else:
            read_nortek, source = _read_nortek_import()
            self._decoder_source = source
            ds = self._call_read_nortek(read_nortek)
        if not isinstance(ds, xr.Dataset):
            raise TypeError(
                f"DOLfYN returned {type(ds)!r}; expected xarray.Dataset."
            )

        ds = self._annotate_decoded_dataset(ds)
        self._raw_metadata_blocks = self._build_raw_metadata_blocks(ds)
        self._raw_metadata_variables = self._build_raw_variable_metadata(ds)
        return ds

    def _call_read_nortek(
        self,
        read_nortek: Callable[..., xr.Dataset],
    ) -> xr.Dataset:
        """Call DOLfYN's Nortek reader while tolerating small API changes."""
        kwargs = self._read_kwargs(read_nortek)

        if self._show_decoder_output:
            return self._read_with_optional_compatibility(read_nortek, kwargs)

        captured_stdout = io.StringIO()
        try:
            with redirect_stdout(captured_stdout):
                return self._read_with_optional_compatibility(read_nortek, kwargs)
        finally:
            output = captured_stdout.getvalue().strip()
            if output:
                logger.debug("Suppressed Nortek decoder stdout:\n%s", output)

    def _call_read_nortek2(
        self,
        read_signature: Callable[..., xr.Dataset],
    ) -> xr.Dataset:
        """Call DOLfYN's Nortek Gen2 reader while tolerating API changes."""
        kwargs = self._read_nortek2_kwargs(read_signature)

        if self._show_decoder_output:
            return self._read_nortek2_with_optional_compatibility(
                read_signature,
                kwargs,
            )

        captured_stdout = io.StringIO()
        try:
            with redirect_stdout(captured_stdout):
                return self._read_nortek2_with_optional_compatibility(
                    read_signature,
                    kwargs,
                )
        finally:
            output = captured_stdout.getvalue().strip()
            if output:
                logger.debug("Suppressed Nortek Gen2 decoder stdout:\n%s", output)

    def _read_kwargs(self, read_nortek: Callable[..., xr.Dataset]) -> dict[str, Any]:
        """Build backend keyword arguments accepted by this DOLfYN version."""
        kwargs: dict[str, Any] = {}
        for name, value in (
            ("userdata", self._userdata),
            ("nens", self._nens),
            ("debug", self._debug),
            ("do_checksum", self._do_checksum),
        ):
            if value is not None:
                kwargs[name] = value

        signature = inspect.signature(read_nortek)
        parameters = signature.parameters
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in parameters.values()
        )
        if not accepts_kwargs:
            kwargs = {key: value for key, value in kwargs.items() if key in parameters}
        return kwargs

    def _read_nortek2_kwargs(
        self,
        read_signature: Callable[..., xr.Dataset],
    ) -> dict[str, Any]:
        """Build backend keyword arguments accepted by this DOLfYN version."""
        kwargs: dict[str, Any] = {}
        for name, value in (
            ("userdata", self._userdata),
            ("nens", self._nens),
            ("debug", self._debug),
            ("rebuild_index", self._rebuild_index),
            ("dual_profile", self._dual_profile),
        ):
            if value is not None:
                kwargs[name] = value

        signature = inspect.signature(read_signature)
        parameters = signature.parameters
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in parameters.values()
        )
        if not accepts_kwargs:
            kwargs = {key: value for key, value in kwargs.items() if key in parameters}
        return kwargs

    def _read_with_optional_compatibility(
        self,
        read_nortek: Callable[..., xr.Dataset],
        kwargs: dict[str, Any],
    ) -> xr.Dataset:
        """Run the backend reader, optionally applying the Aquadopp template fix."""
        if not self._apply_aquadopp_compatibility:
            return read_nortek(self.input_file, **kwargs)

        with _ClassicAquadoppTemplateRepair.context(
            self.input_file,
            read_nortek,
        ) as note:
            if note is not None:
                self._compatibility_notes.append(note)
            return read_nortek(self.input_file, **kwargs)

    def _read_nortek2_with_optional_compatibility(
        self,
        read_signature: Callable[..., xr.Dataset],
        kwargs: dict[str, Any],
    ) -> xr.Dataset:
        """Run the Gen2 backend reader with the optional Aquadopp2 fix."""
        if not self._apply_nortek2_aquadopp_compatibility:
            return read_signature(self.input_file, **kwargs)

        with _Nortek2AquadoppAverageTailRepair.context(read_signature) as note:
            if note is not None:
                self._compatibility_notes.append(note)
            return read_signature(self.input_file, **kwargs)

    def _annotate_decoded_dataset(self, ds: xr.Dataset) -> xr.Dataset:
        """Add SeaSenseLib provenance and conservative metadata defaults."""
        ds = self._rename_non_measurement_fields(ds)
        self._normalize_time_attrs(ds)

        for variable_name, attrs in _NORTEK_ATTR_DEFAULTS.items():
            for candidate_name in (variable_name, f"{variable_name}_avg"):
                if candidate_name not in ds:
                    continue
                for attr_name, attr_value in attrs.items():
                    ds[candidate_name].attrs.setdefault(attr_name, attr_value)

        self._normalize_orientation_standard_names(ds)
        self._annotate_environmental_sources(ds)
        self._annotate_orientation_sources(ds)

        for variable_name in list(ds.coords) + list(ds.data_vars):
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
        if "vel" in ds:
            coord_sys = str(ds.attrs.get("coord_sys", "")).strip().lower()
            if coord_sys:
                ds["vel"].attrs.setdefault("coordinate_system", coord_sys)
        return ds

    def _rename_non_measurement_fields(self, ds: xr.Dataset) -> xr.Dataset:
        """Avoid presenting configured or placeholder fields as measurements."""
        rename_map = {}
        sound_speed_setting = (
            "c_sound" in ds
            and self._is_truthy(ds.attrs.get("user_specified_sound_speed"))
        )
        pressure_placeholder = False
        pressure_placeholder_basis = ""
        if "pressure" in ds:
            pressure_all_zero = self._is_zero_placeholder(ds["pressure"])
            pressure_available = self._pressure_sensor_available(ds)
            pressure_placeholder = pressure_all_zero or not pressure_available
            if pressure_all_zero:
                pressure_placeholder_basis = "nortek_pressure_all_zero"
            elif not pressure_available:
                pressure_placeholder_basis = "nortek_pressure_sensor_header"
        correlation_placeholder = (
            "corr" in ds and self._is_zero_placeholder(ds["corr"])
        )

        if sound_speed_setting:
            rename_map["c_sound"] = _NORTEK_SOUND_SPEED_SETTING
        if pressure_placeholder:
            rename_map["pressure"] = _NORTEK_PRESSURE_PLACEHOLDER
        if correlation_placeholder:
            rename_map["corr"] = _NORTEK_CORRELATION_PLACEHOLDER

        renamed = ds.rename(rename_map) if rename_map else ds
        for original_name, renamed_name in rename_map.items():
            attrs = renamed[renamed_name].attrs
            attrs.setdefault("original_name", original_name)
            if "units" in attrs:
                attrs.setdefault("original_units", attrs["units"])
            attrs.pop("standard_name", None)
            attrs.update(_NORTEK_ATTR_DEFAULTS[renamed_name])
            if renamed_name == _NORTEK_SOUND_SPEED_SETTING:
                self._set_source_attrs(
                    attrs,
                    "configured",
                    "nortek_user_specified_sound_speed",
                )
            elif renamed_name == _NORTEK_PRESSURE_PLACEHOLDER:
                self._set_source_attrs(
                    attrs,
                    "placeholder",
                    pressure_placeholder_basis or "nortek_pressure_all_zero",
                )
            elif renamed_name == _NORTEK_CORRELATION_PLACEHOLDER:
                self._set_source_attrs(
                    attrs,
                    "placeholder",
                    "nortek_correlation_all_zero",
                )
        return renamed

    @staticmethod
    def _normalize_time_attrs(ds: xr.Dataset) -> None:
        """Move datetime serialization attrs away from xarray-reserved keys."""
        for coord_name in ds.coords:
            coord = ds[coord_name]
            if not np.issubdtype(coord.dtype, np.datetime64):
                continue
            attrs = coord.attrs
            if "units" in attrs:
                attrs.setdefault("original_units", attrs.pop("units"))
            if "calendar" in attrs:
                attrs.setdefault("original_calendar", attrs.pop("calendar"))

    @staticmethod
    def _normalize_orientation_standard_names(ds: xr.Dataset) -> None:
        """Use SeaSenseLib's orientation standard names while keeping originals."""
        for variable_name, canonical in (
            ("heading", params.HEADING),
            ("pitch", params.PITCH),
            ("roll", params.ROLL),
        ):
            for candidate_name in (variable_name, f"{variable_name}_avg"):
                if candidate_name not in ds:
                    continue
                expected = params.metadata.get(canonical, {}).get("standard_name")
                if not expected:
                    continue
                attrs = ds[candidate_name].attrs
                current = attrs.get("standard_name")
                if current and current != expected:
                    attrs.setdefault("original_standard_name", current)
                attrs["standard_name"] = expected

    @staticmethod
    def _set_source_attrs(
        attrs: dict[str, Any],
        source: str,
        basis: str,
    ) -> None:
        """Set compact source annotations shared with other raw readers."""
        attrs["sensor_source"] = source
        attrs["sensor_source_basis"] = basis

    @staticmethod
    def _annotate_environmental_sources(ds: xr.Dataset) -> None:
        """Add source annotations where Nortek metadata gives clear evidence."""
        for pressure_name in ("pressure", "pressure_avg"):
            if pressure_name not in ds:
                continue
            attrs = ds[pressure_name].attrs
            if NortekRawReader._pressure_sensor_available(ds):
                basis = (
                    "nortek_pressure_sensor_header"
                    if ds.attrs.get("pressure_sensor") is not None
                    else "nortek_pressure_nonzero"
                )
                NortekRawReader._set_source_attrs(attrs, "sensor", basis)

    @staticmethod
    def _annotate_orientation_sources(ds: xr.Dataset) -> None:
        """Add concise source comments when Nortek sensor flags are available."""
        compass = NortekRawReader._is_truthy(ds.attrs.get("compass"))
        tilt = NortekRawReader._is_truthy(ds.attrs.get("tilt_sensor"))
        if "heading" in ds and ds.attrs.get("compass") is not None:
            attrs = ds["heading"].attrs
            if compass:
                NortekRawReader._set_source_attrs(
                    attrs,
                    "sensor",
                    "nortek_compass_header",
                )
                attrs.setdefault(
                    "comment",
                    "Heading decoded from the Nortek compass sensor.",
                )
            else:
                attrs["measurement_type"] = "Unknown"
                NortekRawReader._set_source_attrs(
                    attrs,
                    "unknown",
                    "nortek_compass_header",
                )
                attrs.setdefault(
                    "comment",
                    "Heading was decoded, but the Nortek header does not "
                    "confirm an available compass sensor.",
                )
        for name in ("pitch", "roll"):
            if name not in ds or ds.attrs.get("tilt_sensor") is None:
                continue
            attrs = ds[name].attrs
            if tilt:
                NortekRawReader._set_source_attrs(
                    attrs,
                    "sensor",
                    "nortek_tilt_sensor_header",
                )
                attrs.setdefault(
                    "comment",
                    f"{name.capitalize()} decoded from the Nortek tilt sensor.",
                )
            else:
                attrs["measurement_type"] = "Unknown"
                NortekRawReader._set_source_attrs(
                    attrs,
                    "unknown",
                    "nortek_tilt_sensor_header",
                )
                attrs.setdefault(
                    "comment",
                    f"{name.capitalize()} was decoded, but the Nortek header "
                    "does not confirm an available tilt sensor.",
                )

    @staticmethod
    def _pressure_sensor_available(ds: xr.Dataset) -> bool:
        """Return False only when the header explicitly says no pressure sensor."""
        value = ds.attrs.get("pressure_sensor")
        if value is None:
            return True
        return NortekRawReader._is_truthy(value)

    @staticmethod
    def _is_truthy(value: Any) -> bool:
        """Interpret common Nortek/DOLfYN truthy attribute values."""
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        return text in {"1", "true", "yes", "y", "on", "available", "present"}

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
        """Build compact raw metadata blocks for the finalization stage."""
        blocks: dict[str, Any] = {
            "configuration": {
                "decoder": self._decoder_source,
                "status": "experimental",
                "note": _EXPERIMENTAL_NOTE,
                "reader_options": self._read_options(),
            },
            "sensor_sources": self._sensor_source_summary(ds),
            "mapping_notes": self._mapping_notes(ds),
        }
        if self._compatibility_notes:
            blocks["configuration"]["compatibility"] = list(self._compatibility_notes)
        return blocks

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
                "original_standard_name",
                "measurement_type",
                "sensor_source",
                "sensor_source_basis",
                "coordinate_system",
            ):
                if attr_name in attrs:
                    variable_metadata[attr_name] = attrs[attr_name]
            variables[name] = variable_metadata
        return variables

    def _sensor_source_summary(self, ds: xr.Dataset) -> dict[str, Any]:
        """Return compact Nortek source annotations for raw metadata."""
        fields = {}
        for name in ds.data_vars:
            attrs = ds[name].attrs
            if "sensor_source" not in attrs:
                continue
            fields[name] = {
                "source": attrs["sensor_source"],
                "basis": attrs.get("sensor_source_basis", "unknown"),
            }

        return {
            "note": (
                "sensor_source values are compact SeaSenseLib annotations. "
                "sensor_source_basis values with nortek_* are evidence from "
                "decoded Nortek header fields or conservative value checks. "
                "These annotations are not external standard terms."
            ),
            "definitions": {
                "sensor_source": _SENSOR_SOURCE_DESCRIPTIONS,
                "sensor_source_basis": _NORTEK_SENSOR_BASIS_DESCRIPTIONS,
            },
            "raw_fields": {
                "pressure_sensor": ds.attrs.get("pressure_sensor"),
                "compass": ds.attrs.get("compass"),
                "tilt_sensor": ds.attrs.get("tilt_sensor"),
                "user_specified_sound_speed": ds.attrs.get(
                    "user_specified_sound_speed"
                ),
            },
            "fields": fields,
        }

    def pipeline_transformations(self, ds: xr.Dataset) -> list[Any]:
        """Return no reader-provided coordinate transformations for raw data.

        Nortek ASCII and CSV readers expose velocity as explicit SeaSenseLib
        component triplets such as ``velocity_beam1``/``velocity_beam2``/
        ``velocity_beam3`` or ``east_velocity``/``north_velocity``/
        ``up_velocity``. The coordinate transformation handler works on those
        scalar triplets.

        The raw reader intentionally preserves DOLfYN's decoded vector variable
        ``vel`` and its ``dir`` coordinate. Splitting that vector into scalar
        components is a separate interpretation step, because the meaning of
        ``dir`` depends on DOLfYN metadata such as ``coord_sys`` and on raw-file
        variants that still need validation. Returning an empty list here makes
        that limitation explicit and keeps raw reads reproducible.
        """
        return []

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
            "do_checksum": self._do_checksum,
            "rebuild_index": self._rebuild_index,
            "dual_profile": self._dual_profile,
            "show_decoder_output": self._show_decoder_output,
            "apply_aquadopp_compatibility": self._apply_aquadopp_compatibility,
            "apply_nortek2_aquadopp_compatibility": (
                self._apply_nortek2_aquadopp_compatibility
            ),
        }

    def _mapping_notes(self, ds: xr.Dataset) -> dict[str, Any]:
        """Describe conservative mapping choices."""
        coord_sys = str(ds.attrs.get("coord_sys", "")).strip().lower() or None
        safe_mappings = {}
        for source, canonical in (
            ("temp", params.TEMPERATURE),
            ("temp_avg", params.TEMPERATURE),
            ("c_sound", params.SPEED_OF_SOUND),
            ("c_sound_avg", params.SPEED_OF_SOUND),
            ("pressure", params.PRESSURE),
            ("pressure_avg", params.PRESSURE),
            ("batt", params.BATTERY_VOLTAGE),
            ("batt_avg", params.BATTERY_VOLTAGE),
        ):
            if source in ds:
                safe_mappings[source] = canonical

        not_mapped: dict[str, str] = {}
        for original, renamed in (
            ("c_sound", _NORTEK_SOUND_SPEED_SETTING),
            ("pressure", _NORTEK_PRESSURE_PLACEHOLDER),
            ("corr", _NORTEK_CORRELATION_PLACEHOLDER),
        ):
            if renamed in ds:
                not_mapped[original] = f"Kept as {renamed}; not a safe measurement mapping."
        for velocity_name in ("vel", "vel_avg"):
            if velocity_name in ds:
                not_mapped[velocity_name] = (
                    f"Kept as vector variable {velocity_name}; component "
                    "splitting depends on coord_sys and the decoded dir "
                    "coordinate."
                )
        for amplitude_name in ("amp", "amp_avg"):
            if amplitude_name in ds:
                not_mapped[amplitude_name] = (
                    f"Kept as vector variable {amplitude_name}; beam/component "
                    "semantics depend on the decoded coordinate system."
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
        """Return conservative Nortek-to-SeaSenseLib variable mappings."""
        return {
            params.TEMPERATURE: ["temp", "temp_avg"],
            params.SPEED_OF_SOUND: ["c_sound", "c_sound_avg"],
            params.PRESSURE: ["pressure", "pressure_avg"],
            params.BATTERY_VOLTAGE: ["batt", "batt_avg"],
        }

    @classmethod
    def format_key(cls) -> str:
        return "nortek-raw"

    @classmethod
    def format_name(cls) -> str:
        return "Nortek Raw (experimental)"

    @classmethod
    def file_extension(cls) -> str | None:
        return ".aqd"

    @classmethod
    def file_extensions(cls) -> tuple[str, ...]:
        return _SUPPORTED_EXTENSIONS


__all__ = ["NortekRawReader"]
