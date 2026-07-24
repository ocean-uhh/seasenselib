"""
Module for reading Nortek ASCII data files into xarray Datasets.
"""

from __future__ import annotations
from pathlib import Path
import re
import pandas as pd
import xarray as xr
import seasenselib.parameters as params
from .base import AbstractReader


_VELOCITY_COLUMN_RE = re.compile(
    r"^Velocity \(Beam(?P<beam>\d+)\|(?P<axis>[XYZ])\|(?P<enu>East|North|Up)\)$"
)
_AMPLITUDE_COLUMN_RE = re.compile(r"^Amplitude \(Beam(?P<beam>\d+)\)$")


_VELOCITY_AXIS_NAMES = {
    "X": "x_velocity",
    "Y": "y_velocity",
    "Z": "z_velocity",
}

_VELOCITY_ENU_NAMES = {
    "East": params.EAST_VELOCITY,
    "North": params.NORTH_VELOCITY,
    "Up": params.UP_VELOCITY,
}

_NORTEK_COLUMN_NAMES = {
    "Month": "month",
    "Day": "day",
    "Year": "year",
    "Hour": "hour",
    "Minute": "minute",
    "Second": "second",
    "Error code": "error_code",
    "Status code": "status_code",
    "Battery voltage": params.BATTERY_VOLTAGE,
    "Soundspeed": params.SPEED_OF_SOUND,
    "Soundspeed used": "speed_of_sound_used",
    "Heading": params.HEADING,
    "Pitch": params.PITCH,
    "Roll": params.ROLL,
    "Temperature": params.TEMPERATURE,
    "Analog input 1": "analog_input_1",
    "Analog input 2": "analog_input_2",
    "Speed": params.MAGNITUDE,
    "Direction": params.DIRECTION,
}


class NortekAsciiReader(AbstractReader):
    """ Reads Nortek ASCII data from a .dat file into a xarray Dataset. 
    
    This class reads Nortek ASCII data files, extracts column names and units from a .hdr file, 
    and organizes the data into an xarray Dataset. It handles duplicate column names by making 
    them unique, converts timestamps to datetime objects, and assigns metadata according to 
    CF conventions.
    
    Attributes
    ----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data.
    dat_file_path : str
        The path to the .dat file containing the Nortek ASCII data.
    header_file_path : str 
        The path to the .hdr file containing the header information for the Nortek ASCII data.
    
    Methods
    -------
    __init__(dat_file_path, header_file_path):
        Initializes the NortekAsciiReader with the paths to the .dat and .hdr files.
    _load_data():
        Reads the .dat and .hdr files, processes the data, and creates an xarray Dataset.
    
    Properties
    ----------
    data : xr.Dataset (read-only)
        Returns the xarray Dataset containing the sensor data.
        For backward compatibility, get_data() method is also available but deprecated.
    
    file_type : str
        A string indicating the type of file being read, in this case, 'Nortek ASCII'.
    """

    def __init__(self, dat_file_path: str,
                 header_file_path: str,
                 mapping: dict | None = None,
                 target_coordinate_system: str | None = None,
                 pointing_down: bool | str | None = None,
                 coordinate_transform_keep_source: bool = False,
                 coordinate_transform_overwrite: bool = False,
                 **kwargs):
        """Initialize NortekAsciiReader.
        
        Parameters
        ----------
        dat_file_path : str
            Path to the .dat file.
        header_file_path : str
            Path to the .hdr file.
        mapping : dict, optional
            Variable name mapping dictionary.
        target_coordinate_system : str, optional
            Optional target velocity coordinate system (``BEAM``, ``XYZ`` or
            ``ENU``). If omitted, no coordinate transformation is applied.
        pointing_down : bool or str, optional
            Instrument orientation for BEAM transformations. If omitted,
            SeaSenseLib uses ``status_code`` bit 0 when available.
        coordinate_transform_keep_source : bool, default=False
            Keep the original velocity component variables after creating the
            transformed variables.
        coordinate_transform_overwrite : bool, default=False
            Allow existing target velocity variables to be replaced.
        **kwargs
            Additional base class parameters:
            
            - perform_default_postprocessing : bool, default=True
                Whether to perform default post-processing.
            - rename_variables : bool, default=True
                Whether to rename variables to standard names.
            - assign_metadata : bool, default=True
                Whether to assign CF-compliant metadata.
            - sort_variables : bool, default=True
                Whether to sort variables alphabetically.
        """
        self._target_coordinate_system = target_coordinate_system
        self._coordinate_transform_pointing_down = pointing_down
        self._coordinate_transform_keep_source = coordinate_transform_keep_source
        self._coordinate_transform_overwrite = coordinate_transform_overwrite
        super().__init__(dat_file_path, mapping, input_header_file=header_file_path, **kwargs)
        self._nortek_header_settings = {}
        self._raw_metadata_blocks = {}
        self._raw_metadata_variables = {}
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...]:
        """Return valid file extensions for Nortek ASCII data files."""
        return ('.dat', '.txt', '.asc')

    @classmethod
    def _is_extension_validation_strict(cls) -> bool:
        """ASCII formats can have various extensions, so warn only."""
        return False

    @classmethod
    def reader_args(cls) -> list[dict]:
        return [
            cls._reader_arg(
                "target_coordinate_system",
                "str",
                None,
                "Transform velocity variables to the requested coordinate system.",
                choices=("BEAM", "XYZ", "ENU"),
            ),
            cls._reader_arg(
                "pointing_down",
                "bool | str",
                None,
                "Instrument orientation for BEAM transformations; omit to infer from status data.",
            ),
            cls._reader_arg(
                "coordinate_transform_keep_source",
                "bool",
                False,
                "Keep original velocity variables after adding transformed variables.",
            ),
            cls._reader_arg(
                "coordinate_transform_overwrite",
                "bool",
                False,
                "Allow transformed velocity variables to replace existing variables.",
            ),
        ]

    def _read_header_settings(self, hdr_file_path):
        """Reads the .hdr file to extract instrument settings."""
        settings = {}
        matrix_keys = {
            "transformation_matrix",
            "magnetometer_calibration_matrix",
        }
        current_matrix_key = None
        with open(hdr_file_path, 'r') as file:
            for line in file:
                if line.strip() == "Data file format":
                    break

                stripped = line.strip()
                if current_matrix_key and stripped and line[:1].isspace():
                    values = self._parse_numeric_values(stripped)
                    if values:
                        settings[current_matrix_key].append(values)
                        if len(settings[current_matrix_key]) >= 3:
                            current_matrix_key = None
                        continue
                if current_matrix_key and stripped:
                    current_matrix_key = None

                match = re.match(
                    r"^(?P<key>[A-Za-z][A-Za-z0-9 /_-]*?)\s{2,}(?P<value>.*)$",
                    line.rstrip(),
                )
                if not match:
                    continue

                current_matrix_key = None
                key = match.group("key").strip().lower().replace(" ", "_")
                value = match.group("value").strip()
                if key in matrix_keys:
                    settings[key] = [self._parse_numeric_values(value)]
                    current_matrix_key = key
                elif key == "compass_hard_iron_calibration":
                    settings[key] = self._parse_numeric_values(value)
                else:
                    settings[key] = value

        coordinate_system = settings.get("coordinate_system")
        if coordinate_system:
            settings["coordinate_system"] = coordinate_system.upper()

        return settings

    def _parse_numeric_values(self, value):
        """Parse a whitespace-separated row of numeric Nortek metadata."""
        values = []
        for item in value.split():
            try:
                if any(char in item for char in ".eE"):
                    values.append(float(item))
                else:
                    values.append(int(item))
            except ValueError:
                values.append(item)
        return values

    def _calibration_from_header_settings(self, settings):
        """Extract structured calibration metadata from parsed header settings."""
        calibration = {}
        for key in self._calibration_setting_keys():
            if settings.get(key):
                calibration[key] = settings[key]
        return calibration

    def _header_attributes_for_raw_metadata(self, settings):
        """Return header attributes without duplicated calibration entries."""
        calibration_keys = set(self._calibration_setting_keys())
        return {
            key: value
            for key, value in settings.items()
            if key not in calibration_keys
        }

    def _calibration_setting_keys(self):
        """Return parsed header-setting keys that belong to calibration."""
        return (
            "transformation_matrix",
            "magnetometer_calibration_matrix",
            "compass_hard_iron_calibration",
        )

    def _read_header(self, hdr_file_path, dat_file_path=None):
        """Reads the .hdr file to extract data-file column names and units."""
        headers = []
        blocks = []
        current_block = None

        with open(hdr_file_path, 'r') as file:
            capture = False
            for line in file:
                if line.strip() == "Data file format":
                    capture = True
                    continue
                if capture:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('---'):
                        continue

                    if stripped.startswith('[') and stripped.endswith(']'):
                        current_block = {
                            "file_path": stripped[1:-1],
                            "headers": [],
                        }
                        blocks.append(current_block)
                        continue

                    if current_block is None:
                        continue

                    header = self._parse_header_column_line(stripped)
                    if header is not None:
                        current_block["headers"].append(header)

        if blocks:
            selected_block = self._select_data_format_block(blocks, dat_file_path)
            headers = selected_block["headers"]

        return headers

    def _parse_header_column_line(self, line):
        """Parse one numbered Nortek data-format column line."""
        match = re.match(
            r"^(?P<number>\d+)\s+(?P<body>.*?)(?:\s+\((?P<unit>[^()]*)\))?$",
            line,
        )
        if not match:
            return None

        col_number = match.group("number")
        col_name = match.group("body").strip()
        unit = match.group("unit") or "unknown"
        return (col_number, col_name, unit)

    def _select_data_format_block(self, blocks, dat_file_path=None):
        """Select the header block that describes the requested data file."""
        if not blocks:
            raise ValueError("No data-file format block found in Nortek header.")

        if dat_file_path is None:
            return blocks[0]

        data_path = Path(dat_file_path)
        data_name = data_path.name.lower()
        data_suffix = data_path.suffix.lower()

        for block in blocks:
            block_name = Path(block["file_path"].replace("\\", "/")).name.lower()
            if block_name == data_name:
                return block

        for block in blocks:
            block_name = Path(block["file_path"].replace("\\", "/")).name.lower()
            if Path(block_name).suffix.lower() == data_suffix:
                return block

        return blocks[0]

    def _normalise_header_columns(self, headers, settings):
        """Build unique dataset column definitions from Nortek header columns."""
        coordinate_system = settings.get("coordinate_system", "BEAM")
        columns = []

        for column_number, raw_name, unit in headers:
            variable_name = self._normalise_column_name(
                raw_name,
                unit,
                coordinate_system,
            )
            columns.append(
                {
                    "column_number": column_number,
                    "raw_name": raw_name,
                    "variable_name": variable_name,
                    "unit": unit,
                }
            )

        seen = {}
        for column in columns:
            variable_name = column["variable_name"]
            if variable_name in seen:
                seen[variable_name] += 1
                column["variable_name"] = f"{variable_name}_{seen[variable_name]}"
            else:
                seen[variable_name] = 0

        return columns

    def _raw_variable_metadata(self, columns):
        """Build raw metadata for variables parsed from the Nortek header."""
        variables = {}
        for column in columns:
            variable_name = column["variable_name"]
            metadata = {
                "column_number": column["column_number"],
                "original_name": column["raw_name"],
            }
            if column["unit"] != "unknown":
                metadata["units"] = column["unit"]
            variables[variable_name] = metadata
        return variables

    def _normalise_column_name(self, raw_name, unit, coordinate_system):
        """Map a Nortek header column to its coordinate-aware variable name."""
        velocity_match = _VELOCITY_COLUMN_RE.match(raw_name)
        if velocity_match:
            if coordinate_system == "XYZ":
                return _VELOCITY_AXIS_NAMES[velocity_match.group("axis")]
            if coordinate_system == "ENU":
                return _VELOCITY_ENU_NAMES[velocity_match.group("enu")]
            return f"velocity_beam{velocity_match.group('beam')}"

        amplitude_match = _AMPLITUDE_COLUMN_RE.match(raw_name)
        if amplitude_match:
            return f"amplitude_beam{amplitude_match.group('beam')}"

        if raw_name == "Pressure":
            normalised_unit = unit.strip().lower()
            if normalised_unit in {"m", "meter", "meters"}:
                return params.DEPTH
            return params.PRESSURE

        if raw_name in _NORTEK_COLUMN_NAMES:
            return _NORTEK_COLUMN_NAMES[raw_name]

        return re.sub(r"[^0-9A-Za-z]+", "_", raw_name.strip()).strip("_").lower()

    def _parse_data(self, dat_file_path, columns):
        """Parses the .dat file using headers information."""
        column_names = [column["variable_name"] for column in columns]
        self._validate_data_column_count(dat_file_path, column_names)
        data = pd.read_csv(dat_file_path, sep=r'\s+', names=column_names)
        return data

    def _validate_data_column_count(self, dat_file_path, column_names):
        """Ensure the selected header block matches the data file columns."""
        with open(dat_file_path, "r") as data_file:
            for line_number, line in enumerate(data_file, start=1):
                fields = line.split()
                if not fields:
                    continue
                if len(fields) != len(column_names):
                    raise ValueError(
                        f"Nortek data line {line_number} has {len(fields)} "
                        f"columns, but the selected header block defines "
                        f"{len(column_names)} columns."
                    )
                return

    def _create_xarray_dataset(self, df, columns, settings):
        """Converts the DataFrame to an xarray Dataset, renaming columns and assigning units."""
        # Convert columns to datetime
        df['time'] = pd.to_datetime(
            {
                "year": df["year"],
                "month": df["month"],
                "day": df["day"],
                "hour": df["hour"],
                "minute": df["minute"],
                "second": df["second"],
            }
        )

        # Set datetime as the index
        df.set_index('time', inplace=True)

        # Convert the DataFrame to an xarray Dataset
        ds = xr.Dataset.from_dataframe(df)

        coordinate_system = settings.get("coordinate_system")
        if coordinate_system:
            ds.attrs["coordinate_system"] = coordinate_system

        for column in columns:
            variable = column["variable_name"]
            if variable not in ds:
                continue

            ds[variable].attrs["original_name"] = column["raw_name"]
            if column["unit"] != "unknown":
                ds[variable].attrs["units"] = column["unit"]

            if coordinate_system and (
                variable.startswith("velocity_") or variable.endswith("_velocity")
            ):
                ds[variable].attrs["coordinate_system"] = coordinate_system

            if variable.startswith("amplitude_beam"):
                ds[variable].attrs["coordinate_system"] = "BEAM"

        # Assign meta information for all attributes of the xarray Dataset
        for key in (list(ds.data_vars.keys()) + list(ds.coords.keys())):
            super()._assign_metadata_for_key_to_xarray_dataset( ds, key)

        return ds

    def _load_data(self) -> xr.Dataset:
        """Load the Nortek ASCII data and return an xarray Dataset.
        
        Returns
        -------
        xr.Dataset
            The loaded dataset.
        """
        settings = self._read_header_settings(self.input_header_file)
        self._nortek_header_settings = settings
        headers = self._read_header(self.input_header_file, self.input_file)
        columns = self._normalise_header_columns(headers, settings)
        self._raw_metadata_blocks = {
            "attributes": self._header_attributes_for_raw_metadata(settings)
        }
        calibration = self._calibration_from_header_settings(settings)
        if calibration:
            self._raw_metadata_blocks["calibration"] = calibration
        self._raw_metadata_variables = self._raw_variable_metadata(columns)
        data = self._parse_data(self.input_file, columns)
        ds = self._create_xarray_dataset(data, columns, settings)
        return ds

    def pipeline_transformations(self, ds: xr.Dataset) -> list:
        """Return reader-provided transformations for the pipeline.

        The base reader calls this hook after ``_load_data()`` and before the
        transformation stage runs. By then the Nortek header has already been
        parsed and stored in ``_raw_metadata_blocks``, so the transformation
        handler can read the BEAM-to-XYZ matrix from the normal pipeline
        metadata context. This method only decides whether a transformation was
        requested by the caller and passes through the reader-level options.

        If no target coordinate system was requested, no handler is returned and
        the default read path remains unchanged.
        """
        if not self._target_coordinate_system:
            return []

        # Import lazily to keep ordinary reader imports light and to avoid a
        # module-level dependency cycle with the transformation package.
        from seasenselib.pipeline.transformation.handlers import (
            NortekCoordinateTransformation,
        )

        return [
            NortekCoordinateTransformation(
                target_coordinate_system=self._target_coordinate_system,
                pointing_down=self._coordinate_transform_pointing_down,
                keep_source=self._coordinate_transform_keep_source,
                overwrite=self._coordinate_transform_overwrite,
            )
        ]

    def _postprocess_after_pipeline(self, ds: xr.Dataset) -> xr.Dataset:
        """Restore the final Nortek coordinate-system attribute.

        The finalization stage moves most reader/header-specific global
        attributes into ``raw_metadata``. ``coordinate_system`` is kept as a
        plain global attribute because downstream users need to know the current
        velocity frame without parsing the RAW metadata container.

        If the optional transformation ran, the processing metadata contains the
        final target coordinate system. Otherwise the dataset should keep the
        coordinate system declared in the Nortek header.
        """
        from seasenselib.pipeline.transformation.handlers import (
            transformed_coordinate_system_from_metadata,
        )

        # Prefer the transformation record over the original header value:
        # after BEAM -> XYZ/ENU, the header still describes the source frame.
        coordinate_system = transformed_coordinate_system_from_metadata(
            self._processing_metadata
        )
        coordinate_system = (
            coordinate_system
            or self._nortek_header_settings.get("coordinate_system")
        )
        if coordinate_system:
            ds.attrs["coordinate_system"] = coordinate_system
        return ds

    @classmethod
    def format_key(cls) -> str:
        return 'nortek-ascii'

    @classmethod
    def format_name(cls) -> str:
        return 'Nortek ASCII'

    @classmethod
    def file_extension(cls) -> str | None:
        return None
    
    @classmethod
    def format_mappings(cls) -> dict:
        """Get Nortek ASCII format-specific variable name mappings.
        
        Returns:
            Dictionary mapping canonical parameter names to Nortek-specific
            variable name patterns commonly found in ASCII export files.
        """
        return {
            params.SPEED_OF_SOUND: ['Soundspeed', 'Speed of Sound'],
            params.PRESSURE: ['Pressure'],
            params.TEMPERATURE: ['Temperature'],
        }
