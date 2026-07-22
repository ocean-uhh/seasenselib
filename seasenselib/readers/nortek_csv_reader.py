"""
Reader wrapper and helper functions for Nortek CSV exports.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pandas as pd
import xarray as xr

import seasenselib.parameters as params
from .base import AbstractReader

<<<<<<< Updated upstream
_NORTEK_VECTOR_COLUMN_RE = re.compile(
=======

_NORTEK_VECTOR_BEAM_COLUMN_RE = re.compile(
>>>>>>> Stashed changes
    r"^(?P<kind>vel|velocity|amp|amplitude|corr|correlation)"
    r"(?:(?:Beam(?P<beam>\d+))|(?P<axis>East|North|Up))"
    r"#(?P<cell>\d+)$",
    re.IGNORECASE,
)
_NORTEK_VELOCITY_COMPONENT_COLUMN_RE = re.compile(
    r"^(?P<kind>vel|velocity)(?P<component>East|North|Up|X|Y|Z)"
    r"#(?P<cell>\d+)$",
    re.IGNORECASE,
)

_NORTEK_VECTOR_KIND_ALIASES = {
    "vel": "vel",
    "velocity": "vel",
    "amp": "amp",
    "amplitude": "amp",
    "corr": "corr",
    "correlation": "corr",
}

_VELOCITY_AXIS_NAMES = {
    1: "x_velocity",
    2: "y_velocity",
    3: "z_velocity",
}
_VELOCITY_AXIS_NAMES_BY_LABEL = {
    "X": "x_velocity",
    "Y": "y_velocity",
    "Z": "z_velocity",
}

_VELOCITY_ENU_NAMES = {
    1: params.EAST_VELOCITY,
    2: params.NORTH_VELOCITY,
    3: params.UP_VELOCITY,
}
_VELOCITY_ENU_NAMES_BY_LABEL = {
    "EAST": params.EAST_VELOCITY,
    "NORTH": params.NORTH_VELOCITY,
    "UP": params.UP_VELOCITY,
}

_COORDINATE_SYSTEM_CODES = {
    "00": "ENU",
    "0": "ENU",
    "01": "XYZ",
    "1": "XYZ",
    "10": "BEAM",
    "2": "BEAM",
}

_ENVIRONMENT_COLUMNS = [
    ("temperature", params.TEMPERATURE, "Water Temperature"),
    ("pressure", params.PRESSURE, "Pressure"),
    ("heading", params.HEADING, "Heading"),
    ("pitch", params.PITCH, "Pitch"),
    ("roll", params.ROLL, "Roll"),
    ("speedOfSound", params.SPEED_OF_SOUND, "Speed of Sound"),
    ("batteryVoltage", params.BATTERY_VOLTAGE, "Battery Voltage"),
]

_DEFAULT_UNITS = {
    params.TEMPERATURE: "degrees_C",
    params.PRESSURE: "dbar",
    params.HEADING: "degrees",
    params.PITCH: "degrees",
    params.ROLL: "degrees",
    params.SPEED_OF_SOUND: "m/s",
    params.BATTERY_VOLTAGE: "V",
    "vel": "m/s",
    "amp": "counts",
    "corr": "%",
}


def _clean_metadata_value(value: Any) -> Any:
    """Convert pandas-ish missing values to None and trim strings."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        return cleaned

    return value


def _parse_scalar(value: str) -> Any:
    """Parse one value from the Nortek string-data command stream."""
    value = value.strip().strip('"')
    lower = value.lower()

    if lower in {"true", "false"}:
        return lower == "true"

    try:
        if any(char in value for char in ".eE"):
            return float(value)
        return int(value)
    except ValueError:
        return value


def _normalise_coordinate_system(value: Any) -> Optional[str]:
    """Normalize Nortek coordinate-system labels and numeric codes."""
    value = _clean_metadata_value(value)
    if value is None:
        return None

    text = str(value).strip().strip('"').upper()
    if text in {"BEAM", "XYZ", "ENU"}:
        return text
    return _COORDINATE_SYSTEM_CODES.get(text)


def _first_command(commands: Dict[str, Any], name: str) -> Dict[str, Any]:
    """Return a command dictionary even if that command occurred repeatedly."""
    value = commands.get(name)
    if isinstance(value, list):
        return value[0] if value else {}
    if isinstance(value, dict):
        return value
    return {}


<<<<<<< Updated upstream
def _parse_vector_column(source_column: str) -> Optional[Dict[str, int | str]]:
    """Parse a Nortek vector CSV column name into kind, beam_or_dir, and cell."""
    match = _NORTEK_VECTOR_COLUMN_RE.match(source_column.strip())
    if not match:
        return None

    return {
        "kind": _NORTEK_VECTOR_KIND_ALIASES[match.group("kind")],
        "beam": match.group("beam"),
        "axis": match.group("axis"),
        "cell": match.group("cell"),
    }
=======
def _parse_vector_column(
    source_column: str,
) -> Optional[Dict[str, int | str | None]]:
    """Parse a Nortek vector CSV column name into kind, component, and cell."""
    match = _NORTEK_VECTOR_BEAM_COLUMN_RE.match(source_column.strip())
    if match:
        return {
            "kind": _NORTEK_VECTOR_KIND_ALIASES[match.group("kind").lower()],
            "beam": int(match.group("beam")),
            "axis": None,
            "enu": None,
            "cell": int(match.group("cell")),
        }

    match = _NORTEK_VELOCITY_COMPONENT_COLUMN_RE.match(source_column.strip())
    if match:
        component = match.group("component").upper()
        return {
            "kind": _NORTEK_VECTOR_KIND_ALIASES[match.group("kind").lower()],
            "beam": None,
            "axis": component if component in _VELOCITY_AXIS_NAMES_BY_LABEL else None,
            "enu": component if component in _VELOCITY_ENU_NAMES_BY_LABEL else None,
            "cell": int(match.group("cell")),
        }

    return None
>>>>>>> Stashed changes


def _first_existing_command(
    commands: Dict[str, Any],
    names: tuple[str, ...],
) -> tuple[Optional[str], Dict[str, Any]]:
    """Return the first available command name and dictionary from ``names``."""
    for name in names:
        command = _first_command(commands, name)
        if command:
            return name, command
    return None, {}


def _read_nortek_string_data(
    header_file: Optional[Union[str, Path]],
) -> Dict[str, Any]:
    """Read and parse a Nortek ``String Data.csv`` file."""
    if not header_file:
        return {}

    header_path = Path(header_file)
    if not header_path.exists():
        raise FileNotFoundError(f"Nortek CSV header file not found: {header_path}")

    lines = header_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    raw_strings = []
    for line in lines[1:]:
        if not line.strip():
            continue
        _, separator, value = line.partition(";")
        raw_strings.append(value if separator else line)

    commands: Dict[str, Any] = {}
    for raw_string in raw_strings:
        for raw_segment in raw_string.split("|"):
            segment = raw_segment.strip()
            if not segment:
                continue

            command_match = re.search(r"[A-Z][A-Z0-9]+", segment)
            if not command_match:
                continue
            segment = segment[command_match.start():]

            parts = next(csv.reader([segment], delimiter=","))
            if not parts:
                continue

            command_name = parts[0].strip().upper()
            values = {}
            for part in parts[1:]:
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                values[key.strip()] = _parse_scalar(value)

            if command_name in commands:
                existing = commands[command_name]
                if isinstance(existing, list):
                    existing.append(values)
                else:
                    commands[command_name] = [existing, values]
            else:
                commands[command_name] = values

    return commands


def _settings_from_string_data(commands: Dict[str, Any]) -> Dict[str, Any]:
    """Extract common instrument settings from parsed Nortek string data."""
    settings: Dict[str, Any] = {}

    id_record = _first_command(commands, "ID")
    if id_record.get("STR") is not None:
        settings["instrument_type"] = id_record["STR"]
    if id_record.get("SN") is not None:
        settings["serial_number"] = str(id_record["SN"])

    avg_record = _first_command(commands, "GETAVG")
    coordinate_system = _normalise_coordinate_system(avg_record.get("CY"))
    if coordinate_system:
        settings["coordinate_system"] = coordinate_system
    for source_key, target_key in [
        ("NC", "number_of_cells"),
        ("CS", "cell_size"),
        ("BD", "blanking_distance"),
        ("NB", "number_of_beams"),
        ("NPING", "average_pings"),
    ]:
        if avg_record.get(source_key) is not None:
            settings[target_key] = avg_record[source_key]

    hardware_record = _first_command(commands, "GETHW")
    if hardware_record.get("FW") is not None:
        settings["firmware_version"] = hardware_record["FW"]
    if hardware_record.get("FPGA") is not None:
        settings["fpga_version"] = hardware_record["FPGA"]

    software_record = _first_command(commands, "GETSWMETA")
    if software_record.get("SWVER") is not None:
        settings["software_version"] = software_record["SWVER"]

    return settings


def _matrix_from_command(command: Dict[str, Any]) -> Optional[list[list[Any]]]:
    """Return an M11..MNN matrix from a parsed Nortek command."""
    if not command:
        return None

    try:
        rows = int(command.get("ROWS", 3))
        columns = int(command.get("COLS", 3))
    except (TypeError, ValueError):
        rows = 3
        columns = 3

    matrix = []
    for row in range(1, rows + 1):
        values = []
        for column in range(1, columns + 1):
            key = f"M{row}{column}"
            if key not in command:
                return None
            values.append(command[key])
        matrix.append(values)
    return matrix


def _copy_calibration_source_commands(
    commands: Dict[str, Any],
    names: tuple[str, ...],
) -> Dict[str, Any]:
    """Copy original Nortek calibration commands for provenance."""
    sources = {}
    for name in names:
        command = commands.get(name)
        if command:
            sources[name] = command
    return sources


def _calibration_from_string_data(commands: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured calibration matrices from parsed Nortek commands."""
    calibration: Dict[str, Any] = {}

    source_commands = _copy_calibration_source_commands(
        commands,
        (
            "GETXFAVG",
            "GETXFBURST",
            "GETCOMPASSCAL",
            "CALCOMPGET",
            "CALMAGNALIGNGET",
        ),
    )
    if source_commands:
        calibration["source_commands"] = source_commands

    _, transformation_record = _first_existing_command(
        commands,
        ("GETXFAVG", "GETXFBURST"),
    )
    transformation_matrix = _matrix_from_command(transformation_record)
    if transformation_matrix is not None:
        calibration["transformation_matrix"] = transformation_matrix

    _, compass_record = _first_existing_command(
        commands,
        ("GETCOMPASSCAL", "CALCOMPGET"),
    )
    compass_matrix = _matrix_from_command(compass_record)
    if compass_matrix is not None:
        calibration["magnetometer_calibration_matrix"] = compass_matrix

    hard_iron = [
        compass_record.get(axis)
        for axis in ("DX", "DY", "DZ")
        if compass_record.get(axis) is not None
    ]
    if len(hard_iron) == 3:
        calibration["compass_hard_iron_calibration"] = hard_iron

    magnetic_alignment_matrix = _matrix_from_command(
        _first_command(commands, "CALMAGNALIGNGET")
    )
    if magnetic_alignment_matrix is not None:
        calibration["magnetometer_alignment_matrix"] = magnetic_alignment_matrix

    return calibration


def _read_units_metadata(
    units_file: Optional[Union[str, Path]],
) -> Dict[str, Dict[str, str]]:
    """Read a Nortek ``Units.csv`` file into a per-source-column mapping."""
    if not units_file:
        return {}

    units_path = Path(units_file)
    if not units_path.exists():
        raise FileNotFoundError(f"Nortek CSV units file not found: {units_path}")

    units_df = pd.read_csv(
        units_path,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    units: Dict[str, Dict[str, str]] = {}
    for row in units_df.to_dict("records"):
        variable = _clean_metadata_value(row.get("Variable"))
        if not variable:
            continue

        entry = {}
        unit = _clean_metadata_value(row.get("Unit"))
        description = _clean_metadata_value(row.get("Description"))
        if unit is not None:
            entry["units"] = str(unit)
        if description is not None:
            entry["description"] = str(description)
        units[str(variable)] = entry

    return units


def _coordinate_system_from_data(df: pd.DataFrame) -> Optional[str]:
    """Return the coordinate system declared in the data file, if present."""
    if "coordinateSystem" not in df.columns:
        return None

    for value in df["coordinateSystem"]:
        coordinate_system = _normalise_coordinate_system(value)
        if coordinate_system:
            return coordinate_system

    return None


def _coordinate_system_from_vector_columns(df: pd.DataFrame) -> Optional[str]:
    """Infer coordinate system from explicit velocity component column names."""
    coordinate_systems = set()
    for source_column in df.columns:
        vector_column = _parse_vector_column(source_column)
        if not vector_column or vector_column["kind"] != "vel":
            continue
        if vector_column.get("enu"):
            coordinate_systems.add("ENU")
        elif vector_column.get("axis"):
            coordinate_systems.add("XYZ")

    if len(coordinate_systems) == 1:
        return coordinate_systems.pop()
    return None


def _units_for_source_column(
    source_column: str,
    variable_name: str,
    units_metadata: Dict[str, Dict[str, str]],
) -> Dict[str, str]:
    """Return units metadata for a concrete CSV source column."""
    if source_column in units_metadata:
        return units_metadata[source_column]

    vector_column = _parse_vector_column(source_column)
    if vector_column:
        return units_metadata.get(str(vector_column["kind"]), {})

    if variable_name in units_metadata:
        return units_metadata[variable_name]

    return {}


<<<<<<< Updated upstream
def _velocity_variable_name(beam_or_axis: str, cell: int, coordinate_system: str) -> str:
    """Map Nortek velocity columns to coordinate-aware variable names."""
    if coordinate_system == "XYZ":
        variable_name = _VELOCITY_AXIS_NAMES.get(beam_or_axis, f"velocity_beam{beam_or_axis}")
    elif coordinate_system == "ENU":
        variable_name = _VELOCITY_ENU_NAMES.get(beam_or_axis, f"velocity_{beam_or_axis}")
=======
def _velocity_variable_name(
    beam: Optional[int],
    cell: int,
    coordinate_system: str,
    axis: Optional[str] = None,
    enu: Optional[str] = None,
) -> str:
    """Map Nortek velocity columns to coordinate-aware variable names."""
    if enu:
        variable_name = _VELOCITY_ENU_NAMES_BY_LABEL.get(
            enu,
            f"velocity_{enu.lower()}",
        )
    elif axis:
        variable_name = _VELOCITY_AXIS_NAMES_BY_LABEL.get(
            axis,
            f"{axis.lower()}_velocity",
        )
    elif coordinate_system == "XYZ" and beam is not None:
        variable_name = _VELOCITY_AXIS_NAMES.get(beam, f"velocity_beam{beam}")
    elif coordinate_system == "ENU" and beam is not None:
        variable_name = _VELOCITY_ENU_NAMES.get(beam, f"velocity_beam{beam}")
>>>>>>> Stashed changes
    else:
        variable_name = f"velocity_beam{beam_or_axis}"

    if cell > 1:
        return f"{variable_name}_cell{cell}"
    return variable_name


def _velocity_long_name(variable_name: str, beam: int | str, cell: int) -> str:
    """Build a readable long name for velocity variables."""
    if variable_name.startswith("velocity_beam"):
        name = f"Velocity Beam {beam}"
    else:
        name = variable_name
        cell_suffix = f"_cell{cell}"
        if name.endswith(cell_suffix):
            name = name[: -len(cell_suffix)]
        name = name.replace("_", " ").title()

    if cell > 1:
        return f"{name} Cell {cell}"
    return name


def _build_nortek_csv_columns(
    df: pd.DataFrame,
    coordinate_system: str,
    units_metadata: Dict[str, Dict[str, str]],
) -> list[Dict[str, Any]]:
    """Build variable definitions from data columns and metadata files."""
    columns: list[Dict[str, Any]] = []

    for source_column, variable_name, long_name in _ENVIRONMENT_COLUMNS:
        if source_column not in df.columns:
            continue
        units_entry = _units_for_source_column(source_column, variable_name, units_metadata)
        columns.append(
            {
                "column_number": str(df.columns.get_loc(source_column) + 1),
                "source_column": source_column,
                "variable_name": variable_name,
                "unit_key": variable_name,
                "units": units_entry.get("units", _DEFAULT_UNITS.get(variable_name)),
                "description": units_entry.get("description"),
                "long_name": long_name,
            }
        )

    for source_column in df.columns:
        vector_column = _parse_vector_column(source_column)
        if not vector_column:
            continue

<<<<<<< Updated upstream
        kind = str(vector_column["kind"]).lower()
        if vector_column["beam"] is not None:
            beam = str(vector_column["beam"]).lower()
        else:
            beam = None
        if vector_column["axis"] is not None:
            axis = str(vector_column["axis"]).lower()
        else:
            axis = None
        cell = int(vector_column["cell"])

        if kind == "vel":
            if beam is not None:
                variable_name = _velocity_variable_name(beam, cell, coordinate_system)
                long_name = _velocity_long_name(variable_name, beam, cell)
            if axis is not None:
                variable_name = _velocity_variable_name(axis, cell, coordinate_system)
                long_name = _velocity_long_name(variable_name, axis, cell)
=======
        kind = str(vector_column["kind"])
        beam = (
            int(vector_column["beam"])
            if vector_column["beam"] is not None
            else None
        )
        axis = str(vector_column["axis"]) if vector_column["axis"] is not None else None
        enu = str(vector_column["enu"]) if vector_column["enu"] is not None else None
        cell = int(vector_column["cell"])

        if kind == "vel":
            variable_name = _velocity_variable_name(
                beam,
                cell,
                coordinate_system,
                axis=axis,
                enu=enu,
            )
            long_name = _velocity_long_name(
                variable_name,
                beam if beam is not None else axis or enu or "",
                cell,
            )
>>>>>>> Stashed changes
        elif kind == "amp":
            variable_name = f"amplitude_beam{beam}"
            if cell > 1:
                variable_name = f"{variable_name}_cell{cell}"
            long_name = f"Amplitude Beam {beam}"
            if cell > 1:
                long_name = f"{long_name} Cell {cell}"
        else:
            variable_name = f"correlation_beam{beam}"
            if cell > 1:
                variable_name = f"{variable_name}_cell{cell}"
            long_name = f"Correlation Beam {beam}"
            if cell > 1:
                long_name = f"{long_name} Cell {cell}"

        units_entry = _units_for_source_column(source_column, variable_name, units_metadata)
        columns.append(
            {
                "column_number": str(df.columns.get_loc(source_column) + 1),
                "source_column": source_column,
                "variable_name": variable_name,
                "unit_key": kind,
                "units": units_entry.get("units", _DEFAULT_UNITS.get(kind)),
                "description": units_entry.get("description"),
                "long_name": long_name,
                "beam": beam,
                "axis": axis,
                "enu": enu,
                "cell": cell,
            }
        )

    return columns


def _parse_nortek_csv_columns(
    df: pd.DataFrame,
    coordinate_system: str = "BEAM",
    units_metadata: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict:
    """
    Extract data variables from Nortek CSV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with Nortek CSV data
    coordinate_system : str, default="BEAM"
        Coordinate system used to name velocity variables.
    units_metadata : dict, optional
        Metadata parsed from ``Units.csv``.

    Returns
    -------
    Dict
        Dictionary of data variables for xarray Dataset
    """
    units_metadata = units_metadata or {}
    columns = _build_nortek_csv_columns(df, coordinate_system, units_metadata)
    return {
        column["variable_name"]: (["time"], df[column["source_column"]].values)
        for column in columns
    }


def _raw_variable_metadata(columns: list[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """Build raw metadata for variables parsed from Nortek CSV files."""
    variables = {}
    for column in columns:
        metadata = {
            "column_number": column["column_number"],
            "original_name": column["source_column"],
        }
        if column.get("units"):
            metadata["units"] = column["units"]
        if column.get("description"):
            metadata["description"] = column["description"]
        variables[column["variable_name"]] = metadata
    return variables


def _add_nortek_variable_attributes(
    ds: xr.Dataset,
    columns: list[Dict[str, Any]],
    coordinate_system: str,
) -> xr.Dataset:
    """
    Add units and metadata attributes to Nortek dataset variables.

    Parameters
    ----------
    ds : xr.Dataset
        Dataset to add attributes to
    columns : list of dict
        Parsed data-column definitions.
    coordinate_system : str
        Nortek velocity coordinate system.

    Returns
    -------
    xr.Dataset
        Dataset with variable attributes added
    """
    for column in columns:
        variable_name = column["variable_name"]
        if variable_name not in ds.data_vars:
            continue

        ds[variable_name].attrs["original_name"] = column["source_column"]
        if column.get("units"):
            ds[variable_name].attrs["units"] = column["units"]
        if column.get("long_name"):
            ds[variable_name].attrs["long_name"] = column["long_name"]
        if column.get("description"):
            ds[variable_name].attrs["description"] = column["description"]

        if column["unit_key"] == "vel":
            ds[variable_name].attrs["coordinate_system"] = coordinate_system
        elif column["unit_key"] in {"amp", "corr"}:
            ds[variable_name].attrs["coordinate_system"] = "BEAM"

    return ds


def _load_nortek_csv_dataset(
    file_path: Union[str, Path],
    header_file: Optional[Union[str, Path]] = None,
    units_file: Optional[Union[str, Path]] = None,
) -> tuple[xr.Dataset, Dict[str, Any]]:
    """Load Nortek CSV data and return dataset plus reader metadata."""
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    string_commands = _read_nortek_string_data(header_file)
    units_metadata = _read_units_metadata(units_file)
    settings = _settings_from_string_data(string_commands)
    calibration = _calibration_from_string_data(string_commands)

    # Read CSV and parse time
    df = pd.read_csv(file_path, delimiter=";")
    if "dateTime" not in df.columns:
        raise ValueError(
            "Nortek CSV missing required 'dateTime' column; "
            f"available columns: {', '.join(df.columns)}"
        )
    times = pd.to_datetime(df["dateTime"]).values

    coordinate_system = (
        _coordinate_system_from_data(df)
        or _coordinate_system_from_vector_columns(df)
        or settings.get("coordinate_system")
        or "BEAM"
    )
    settings["coordinate_system"] = coordinate_system

    # Extract data variables
    columns = _build_nortek_csv_columns(df, coordinate_system, units_metadata)
    data_vars = {
        column["variable_name"]: (["time"], df[column["source_column"]].values)
        for column in columns
    }

    # Create dataset
    ds = xr.Dataset(data_vars, coords={"time": times})

    # Add global metadata
    instrument_type = settings.get("instrument_type", "Nortek_Aquadopp")
    ds.attrs.update(
        {
            "instrument_type": instrument_type,
            "filename": str(file_path),
            "data_format": "Nortek_CSV_Export",
            "coordinate_system": coordinate_system,
        }
    )
    if header_file:
        ds.attrs["nortek_header_file"] = str(Path(header_file))
    if units_file:
        ds.attrs["nortek_units_file"] = str(Path(units_file))

    # Extract serial number
    if "serialNumber" in df.columns:
        ds.attrs["serial_number"] = str(df["serialNumber"].iloc[0])
        settings["serial_number"] = str(df["serialNumber"].iloc[0])
    elif settings.get("serial_number") is not None:
        ds.attrs["serial_number"] = str(settings["serial_number"])

    # Add variable attributes
    ds = _add_nortek_variable_attributes(ds, columns, coordinate_system)

    metadata = {
        "blocks": {
            "attributes": settings,
        },
        "variables": _raw_variable_metadata(columns),
    }
    if string_commands:
        metadata["blocks"]["configuration"] = string_commands
    if calibration:
        metadata["blocks"]["calibration"] = calibration
    if units_metadata:
        metadata["blocks"]["units"] = units_metadata

    return ds, metadata


def load_nortek_csv_data(
    file_path: Union[str, Path],
    header_file: Optional[Union[str, Path]] = None,
    units_file: Optional[Union[str, Path]] = None,
) -> xr.Dataset:
    """
    Load Nortek CSV data exported from AquaPro software.

    Parameters
    ----------
    file_path : str or Path
        Path to the CSV data file (e.g., "Average Velocity DF3.csv")
    header_file : str, optional
        Path to the Nortek ``String Data.csv`` metadata file.
    units_file : str, optional
        Path to the Nortek ``Units.csv`` metadata file.

    Returns
    -------
    xr.Dataset
        Dataset with Nortek CSV data
    """
    ds, _ = _load_nortek_csv_dataset(
        file_path,
        header_file=header_file,
        units_file=units_file,
    )

    print(f"  Nortek CSV: loaded {ds.sizes['time']} samples from {Path(file_path).name}")

    return ds


class NortekCsvReader(AbstractReader):
    """
    Read Nortek CSV data exported from AquaPro software.

    This class is a SeaSenseLib wrapper around the original Nortek CSV helper
    functions. The parsing logic is kept in ``load_nortek_csv_data`` and the
    class only adapts it to the common reader interface.
    """

    def __init__(
        self,
        input_file: str,
        mapping: dict | None = None,
        input_header_file: str | None = None,
        units_file: str | None = None,
        **kwargs,
    ):
        """Initialize NortekCsvReader.

        Parameters
        ----------
        input_file : str
            Path to the Nortek CSV file.
        mapping : dict, optional
            Variable name mapping dictionary.
        input_header_file : str, optional
            Optional ``String Data.csv`` path.
        units_file : str, optional
            Optional ``Units.csv`` path. From the CLI, pass it as
            ``--reader-arg units-file=/path/to/Units.csv``.
        **kwargs
            Additional base class parameters.
        """
        super().__init__(
            input_file,
            mapping,
            input_header_file=input_header_file,
            **kwargs,
        )
        self.units_file = units_file
        self._nortek_header_settings: Dict[str, Any] = {}
        self._raw_metadata_blocks: Dict[str, Any] = {}
        self._raw_metadata_variables: Dict[str, Any] = {}
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...]:
        """Return valid file extensions for Nortek CSV exports."""
        return (".csv",)

    def _load_data(self) -> xr.Dataset:
        """Load the Nortek CSV file and return an xarray Dataset."""
        ds, metadata = _load_nortek_csv_dataset(
            self.input_file,
            header_file=self.input_header_file,
            units_file=self.units_file,
        )

        self._raw_metadata_blocks = metadata["blocks"]
        self._raw_metadata_variables = metadata["variables"]
        self._nortek_header_settings = metadata["blocks"]["attributes"]
        return ds

    def _postprocess_after_pipeline(self, ds: xr.Dataset) -> xr.Dataset:
        """Restore Nortek-specific metadata after the generic pipeline."""
        coordinate_system = self._nortek_header_settings.get("coordinate_system")
        if coordinate_system:
            ds.attrs["coordinate_system"] = coordinate_system
        return ds

    @classmethod
    def format_key(cls) -> str:
        return "nortek-csv"

    @classmethod
    def format_name(cls) -> str:
        return "Nortek CSV"

    @classmethod
    def file_extension(cls) -> str | None:
        return None
