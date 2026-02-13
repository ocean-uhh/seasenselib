"""
RAW metadata handler.

Moves raw-format-specific attributes into raw_* attributes and
adds a structured RAW metadata container.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import hashlib
import json
import logging

from ...base import StageContext
from ....utils.seabird_metadata_parser import parse_seabird_metadata, get_sensor_model_info, parse_sbe9_sensors

logger = logging.getLogger(__name__)


@dataclass
class RawMetadata:
    """Add RAW metadata attributes and container."""

    schema: str = "seasenselib/raw-opaque-1.0"

    def configure(self, config: Dict[str, Any]) -> None:
        if isinstance(config, dict) and config.get("schema"):
            self.schema = str(config["schema"])

    def process(self, context: StageContext) -> StageContext:
        ds = context.dataset
        metadata = context.metadata

        source_file = metadata.get("source_file")
        raw_format = metadata.get("format_key") or metadata.get("format_name")
        raw_filename = None
        if source_file:
            raw_filename = Path(source_file).name

        # Move reader-specific attributes into RAW container
        extracted_globals: Dict[str, Any] = {}
        extracted_vars: Dict[str, Dict[str, Any]] = {}

        user_globals = set(metadata.get("user_metadata_global_keys", []) or [])
        protected_globals = set(self._protected_global_keys())
        protected_globals.update(user_globals)

        raw_prefixes = (
            "cnv_",
            "rsk_",
            "adcp_",
            "rdadcp_",
            "uhhds_",
            "nortek_",
            "rcm_",
            "rbr_",
            "sbe_",
            "seasun_",
            "tob_",
        )

        # Move global attrs that are reader-specific or non-standard
        for key in list(ds.attrs.keys()):
            if key.startswith(raw_prefixes):
                extracted_globals[key] = ds.attrs.pop(key)
                continue
            if key in protected_globals or key.startswith("raw_") or key.startswith("processor_"):
                continue
            extracted_globals[key] = ds.attrs.pop(key)

        # Keep variable-level reader-specific attributes on the variables.
        # Raw metadata focuses on global/raw container content only.

        # File-based raw attributes
        if raw_format and "raw_format" not in ds.attrs:
            ds.attrs["raw_format"] = raw_format
        if raw_filename and "raw_filename" not in ds.attrs:
            ds.attrs["raw_filename"] = raw_filename

        if source_file:
            try:
                path = Path(source_file)
                if path.exists():
                    if "raw_filesize_bytes" not in ds.attrs:
                        ds.attrs["raw_filesize_bytes"] = int(path.stat().st_size)
                    if "raw_mtime_utc" not in ds.attrs:
                        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                        ds.attrs["raw_mtime_utc"] = mtime.isoformat().replace("+00:00", "Z")
                    if "raw_sha256" not in ds.attrs:
                        ds.attrs["raw_sha256"] = self._sha256(path)
            except Exception as exc:
                logger.debug("Failed to compute raw file attributes: %s", exc)

        raw_header = metadata.get("raw_header")

        if "raw_metadata_schema" not in ds.attrs:
            ds.attrs["raw_metadata_schema"] = self.schema

        # Build RAW metadata container (opaque JSON)
        raw_container: Dict[str, Any] = {
            "schema": self.schema,
            "raw_format": raw_format or "",
            "raw_filename": raw_filename or "",
            "blocks": {
                "header": raw_header or None,
                "calibration": None,
                "configuration": None,
                "other": None,
            },
        }

        if extracted_globals or extracted_vars:
            raw_container["blocks"]["other"] = {
                "global_attributes": extracted_globals,
                "variables": extracted_vars,
            }

        if "raw_metadata" not in ds.attrs:
            try:
                ds.attrs["raw_metadata"] = json.dumps(
                    raw_container,
                    ensure_ascii=False,
                    default=self._json_default,
                )
            except Exception:
                ds.attrs["raw_metadata"] = json.dumps(
                    raw_container,
                    default=self._json_default,
                )

        # Create sensor variables for SeaBird instruments
        self._add_seabird_sensor_variables(ds, raw_container)

        context.dataset = ds
        logger.debug("Added RAW metadata attributes")
        return context

    def _add_seabird_sensor_variables(self, ds, raw_container: Dict[str, Any]) -> None:
        """Add SeaBird sensor variables with calibration metadata."""
        try:
            import numpy as np
            import xarray as xr
        except ImportError:
            logger.debug("Cannot create sensor variables: numpy/xarray not available")
            return

        # Only process SeaBird data
        raw_format = raw_container.get("raw_format", "")
        if not raw_format or "cnv" not in raw_format.lower():
            return

        # Try to parse SeaBird metadata - first try SBE 9 format (individual sensors)
        sbe9_data = parse_sbe9_sensors(raw_container)
        sensors = sbe9_data.get('sensors', [])
        
        if sensors:
            # SBE 9 CTD format with individual sensors
            logger.debug(f"Found {len(sensors)} individual sensors in SBE 9 format")
            self._create_sbe9_sensor_variables(ds, sensors)
            # Link data variables to their sensor metadata
            self._link_data_variables_to_sensors(ds, sensors)
        else:
            # Fall back to SBE 37 format (single instrument)
            try:
                parsed_metadata = parse_seabird_metadata(raw_container)
            except Exception as e:
                logger.debug(f"Failed to parse SeaBird metadata: {e}")
                return

            if parsed_metadata:
                logger.debug("Using SBE 37/MicroCat format")
                self._create_sbe37_sensor_variable(ds, parsed_metadata)

    def _create_sbe9_sensor_variables(self, ds, sensors: list) -> None:
        """Create individual sensor variables for SBE 9 CTD sensors."""
        try:
            import numpy as np
            import xarray as xr
        except ImportError:
            return
            
        for sensor_info in sensors:
            sensor_type = sensor_info.get('sensor_type', '').upper()
            serial_number = sensor_info.get('serial_number', '')
            
            if not serial_number:
                continue
                
            # Create sensor variable name based on type and serial number
            if sensor_type == 'TEMPERATURE':
                sensor_var_name = f"SENSOR_TEMP_{serial_number}"
            elif sensor_type == 'CONDUCTIVITY':
                sensor_var_name = f"SENSOR_CNDC_{serial_number}"
            elif sensor_type == 'PRESSURE':
                sensor_var_name = f"SENSOR_PRES_{serial_number}"
            else:
                # Generic sensor type
                sensor_var_name = f"SENSOR_{sensor_type}_{serial_number}"
            
            # Don't overwrite existing variables
            if sensor_var_name in ds.data_vars:
                continue
                
            # Create empty, dimensionless variable
            sensor_var = xr.DataArray(
                data=np.array(0),  # Scalar value
                dims=[],  # No dimensions
                name=sensor_var_name
            )
            
            # Build attributes from sensor info
            sensor_attrs = {
                "long_name": f"{sensor_info.get('sensor_model', sensor_type)} sensor metadata",
                "description": f"Sensor metadata for {sensor_type} sensor serial {serial_number} (Channel {sensor_info.get('channel', 'unknown')})",
                "sensor_type": sensor_type,
                "sensor_serial_number": serial_number,
                "sensor_channel": sensor_info.get('channel', ''),
                "sensor_model": sensor_info.get('sensor_model', ''),
                "sensor_maker": sensor_info.get('sensor_maker', 'Sea-Bird Scientific'),
                "cf_role": "sensor_id",
                "coverage_content_type": "auxiliaryInformation",
                "ancillary_variables": sensor_var_name,
            }
            
            # Add vocabulary URIs
            if sensor_info.get('sensor_type_vocabulary'):
                sensor_attrs["sensor_type_vocabulary"] = sensor_info['sensor_type_vocabulary']
            if sensor_info.get('sensor_model_vocabulary'):
                sensor_attrs["sensor_model_vocabulary"] = sensor_info['sensor_model_vocabulary']
            if sensor_info.get('sensor_maker_vocabulary'):
                sensor_attrs["sensor_maker_vocabulary"] = sensor_info['sensor_maker_vocabulary']
            
            # Add calibration info
            if sensor_info.get('calibration_date'):
                sensor_attrs["sensor_calibration_date"] = sensor_info['calibration_date']
            if sensor_info.get('coefficients'):
                # Use sensor type for coefficient attribute name
                coeff_key = f"{sensor_type}_calibration_coefficients"
                sensor_attrs[coeff_key] = sensor_info['coefficients']
            
            sensor_var.attrs = sensor_attrs
            ds[sensor_var_name] = sensor_var
            logger.debug(f"Added SBE 9 sensor variable: {sensor_var_name}")

    def _create_sbe37_sensor_variable(self, ds, parsed_metadata: dict) -> None:
        """Create sensor variable for SBE 37 MicroCat (single instrument)."""
        try:
            import numpy as np
            import xarray as xr
        except ImportError:
            return
            
        # Extract key instrument information
        device_type = parsed_metadata.get("device_type", "")
        serial_number = parsed_metadata.get("serial_number", "")
        
        if not device_type or not serial_number:
            logger.debug("Missing device_type or serial_number for SBE 37 sensor variable")
            return
        
        # Get sensor model information using lookup
        sensor_model_info = get_sensor_model_info(parsed_metadata)
        
        # Determine sensor type vocabulary based on device type
        sensor_type = self._map_device_to_sensor_type(device_type)
        sensor_vocab_uri = self._get_sensor_vocabulary_uri(sensor_type)

        # Create sensor variable name: SENSOR_<type>_<serial>
        sensor_var_name = f"SENSOR_{sensor_type}_{serial_number}"

        # Don't overwrite existing variables
        if sensor_var_name in ds.data_vars:
            return

        # Create empty, dimensionless variable
        sensor_var = xr.DataArray(
            data=np.array(0),  # Scalar value
            dims=[],  # No dimensions
            name=sensor_var_name
        )

        # Add comprehensive attributes
        sensor_attrs = {
            "long_name": f"{device_type} sensor metadata",
            "description": f"Sensor metadata and calibration information for {device_type} serial {serial_number}",
            "sensor_type": sensor_type,
            "sensor_type_vocabulary": sensor_vocab_uri,
            "sensor_model": device_type,
            "sensor_serial_number": serial_number,
        }

        # Add calibration date if available
        if "calibration_date" in parsed_metadata:
            sensor_attrs["sensor_calibration_date"] = parsed_metadata["calibration_date"]

        # Add pump information if available
        if "sbe_pump_installed" in parsed_metadata:
            sensor_attrs["sbe_pump_installed"] = parsed_metadata["sbe_pump_installed"]

        # Add calibration coefficients as separate attributes
        for key, value in parsed_metadata.items():
            if key.endswith("_calibration_coefficients"):
                # Use the key as-is for the attribute name
                sensor_attrs[key] = value

        # Add sensor maker information for SeaBird instruments
        sensor_attrs.update({
            "sensor_maker": "Sea-Bird Scientific",
            "sensor_maker_vocabulary": "http://vocab.nerc.ac.uk/collection/L35/current/MAN0013/",
        })

        # Add sensor model information from lookup
        if sensor_model_info.get('sensor_model'):
            sensor_attrs["sensor_model"] = sensor_model_info["sensor_model"]
        if sensor_model_info.get('sensor_model_vocabulary'):
            sensor_attrs["sensor_model_vocabulary"] = sensor_model_info["sensor_model_vocabulary"]

        # Add CF compliance attributes
        sensor_attrs.update({
            "cf_role": "sensor_id",
            "coverage_content_type": "auxiliaryInformation",
            "ancillary_variables": sensor_var_name,
        })

        sensor_var.attrs = sensor_attrs
        ds[sensor_var_name] = sensor_var
        logger.debug(f"Added SBE 37 sensor variable: {sensor_var_name}")

    def _link_data_variables_to_sensors(self, ds, sensors: list) -> None:
        """Link data variables to their corresponding sensor metadata variables."""
        # Create a mapping from channel and sensor type to sensor variable name
        channel_to_sensor = {}
        
        for sensor_info in sensors:
            sensor_type = sensor_info.get('sensor_type', '').upper()
            channel = sensor_info.get('channel', '')
            serial_number = sensor_info.get('serial_number', '')
            
            if not channel or not serial_number:
                continue
                
            # Create sensor variable name
            if sensor_type == 'TEMPERATURE':
                sensor_var_name = f"SENSOR_TEMP_{serial_number}"
            elif sensor_type == 'CONDUCTIVITY':
                sensor_var_name = f"SENSOR_CNDC_{serial_number}"
            elif sensor_type == 'PRESSURE':
                sensor_var_name = f"SENSOR_PRES_{serial_number}"
            else:
                sensor_var_name = f"SENSOR_{sensor_type}_{serial_number}"
            
            # Map channel and type to sensor variable
            channel_key = (int(channel), sensor_type)
            channel_to_sensor[channel_key] = sensor_var_name
        
        # Now link data variables based on naming convention and channel mapping
        # SBE 9 typically has: temperature_1, temperature_2, conductivity_1, conductivity_2, pressure
        
        # Temperature variables (channels 1 and 4 typically)
        for var_name in ds.data_vars:
            if var_name.startswith('temperature_'):
                if var_name == 'temperature_1':
                    # Primary temperature (usually channel 1)
                    sensor_var = channel_to_sensor.get((1, 'TEMPERATURE'))
                elif var_name == 'temperature_2':
                    # Secondary temperature (usually channel 4)  
                    sensor_var = channel_to_sensor.get((4, 'TEMPERATURE'))
                else:
                    continue
                    
                if sensor_var and var_name in ds.data_vars:
                    ds[var_name].attrs['sensor'] = sensor_var
                    logger.debug(f"Linked {var_name} to {sensor_var}")
            
            elif var_name.startswith('conductivity_'):
                if var_name == 'conductivity_1':
                    # Primary conductivity (usually channel 2)
                    sensor_var = channel_to_sensor.get((2, 'CONDUCTIVITY'))
                elif var_name == 'conductivity_2':
                    # Secondary conductivity (usually channel 5)
                    sensor_var = channel_to_sensor.get((5, 'CONDUCTIVITY'))
                else:
                    continue
                    
                if sensor_var and var_name in ds.data_vars:
                    ds[var_name].attrs['sensor'] = sensor_var
                    logger.debug(f"Linked {var_name} to {sensor_var}")
            
            elif var_name == 'pressure':
                # Pressure (usually channel 3)
                sensor_var = channel_to_sensor.get((3, 'PRESSURE'))
                if sensor_var and var_name in ds.data_vars:
                    ds[var_name].attrs['sensor'] = sensor_var
                    logger.debug(f"Linked {var_name} to {sensor_var}")
            
            # Handle base variable names (SBE37 MicroCat format) - dynamically find sensors
            elif var_name in ['temperature', 'conductivity']:
                # Map variable name to sensor type
                target_sensor_type = 'TEMPERATURE' if var_name == 'temperature' else 'CONDUCTIVITY'
                
                # Find the sensor of this type from the actual metadata (any channel)
                sensor_var = None
                for (channel, sensor_type), sensor_var_name in channel_to_sensor.items():
                    if sensor_type == target_sensor_type:
                        sensor_var = sensor_var_name
                        logger.debug(f"Found {target_sensor_type} sensor on channel {channel}: {sensor_var}")
                        break
                        
                if sensor_var and var_name in ds.data_vars:
                    ds[var_name].attrs['sensor'] = sensor_var
                    logger.debug(f"Linked {var_name} to {sensor_var}")
                else:
                    logger.debug(f"No {target_sensor_type} sensor found for {var_name}")

    @staticmethod
    def _map_device_to_sensor_type(device_type: str) -> str:
        """Map SeaBird device type to standardized sensor type."""
        device_lower = device_type.lower()
        
        # CTD instruments
        if any(term in device_lower for term in ["sbe9", "sbe19", "sbe25", "sbe37", "sbe16", "sbe49"]):
            return "CTD"
        
        # Profiling instruments
        if any(term in device_lower for term in ["sbe21", "sbe39"]):
            return "PROFILER"
        
        # Wave and tide instruments
        if "sbe26" in device_lower or "sbe53" in device_lower:
            return "PRESSURE"
        
        # Default to CTD for most SeaBird instruments
        return "CTD"

    @staticmethod
    def _get_sensor_vocabulary_uri(sensor_type: str) -> str:
        """Get NERC vocabulary URI for sensor type."""
        # NERC L05 vocabulary URIs for instrument types
        vocab_map = {
            "CTD": "http://vocab.nerc.ac.uk/collection/L05/current/130/",
            "THERMISTOR": "http://vocab.nerc.ac.uk/collection/L05/current/134/", # temperature sensor
            "CM": "http://vocab.nerc.ac.uk/collection/L05/current/114/", # Current meter
            "ADCP": "http://vocab.nerc.ac.uk/collection/L05/current/115/", # Current profiler
        }
        return vocab_map.get(sensor_type, "http://vocab.nerc.ac.uk/collection/L05/current/130/")

    @staticmethod
    def _protected_global_keys() -> list[str]:
        keys: list[str] = [
            "Conventions",
            "history",
            "date_created",
            "date_modified",
            "featureType",
            "cdm_data_type",
            "processing_level",
            "standard_name_vocabulary",
            "raw_metadata",
            "raw_metadata_schema",
            "raw_format",
            "raw_filename",
            "raw_sha256",
            "raw_filesize_bytes",
            "raw_mtime_utc",
        ]
        try:
            from seasenselib.knowledge import load_json
            data = load_json("pipeline/metadata_enrichment/acdd.json")
            if isinstance(data, dict):
                keys.extend(data.get("required_global_attributes", []) or [])
                keys.extend(data.get("recommended_global_attributes", []) or [])
                defaults = data.get("defaults", {})
                if isinstance(defaults, dict):
                    keys.extend(defaults.keys())
            raw_policy = load_json("pipeline/finalization/raw_metadata.json")
            if isinstance(raw_policy, dict):
                keys.extend(raw_policy.get("preserve_global_attributes", []) or [])
        except Exception:
            logger.debug("Failed to load protected global keys from knowledge files", exc_info=True)
        return sorted(set(keys))

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _json_default(value: Any) -> Any:
        try:
            import numpy as np
        except Exception:
            np = None

        if np is not None:
            if isinstance(value, np.datetime64):
                if np.isnat(value):
                    return None
                return np.datetime_as_string(value, unit="s")
            if isinstance(value, np.ndarray):
                if np.issubdtype(value.dtype, np.datetime64):
                    if value.size == 0:
                        return []
                    flat = value.reshape(-1)
                    return [
                        None if np.isnat(item) else np.datetime_as_string(item, unit="s")
                        for item in flat
                    ]
                return value.tolist()
            if isinstance(value, np.generic):
                try:
                    return value.item()
                except Exception:
                    return str(value)

        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, set):
            return list(value)
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except Exception:
                return value.hex()
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                logger.debug("Failed to serialize isoformat value", exc_info=True)
                return str(value)
        return str(value)


__all__ = ["RawMetadata"]
