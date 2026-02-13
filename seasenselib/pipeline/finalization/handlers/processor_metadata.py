"""
Processor metadata handler.

Adds processor_* provenance attributes describing the L1 conversion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any
import logging
import platform

from ...base import StageContext

logger = logging.getLogger(__name__)

try:
    from importlib.metadata import version as _get_version
    _SSL_VERSION = _get_version("seasenselib")
except Exception:
    _SSL_VERSION = "unknown"


@dataclass
class ProcessorMetadata:
    """Add processor_* metadata attributes."""

    level: str = "L1"
    include_machine: bool = True
    include_os: bool = True

    def configure(self, config: Dict[str, Any]) -> None:
        if not isinstance(config, dict):
            return
        if "level" in config:
            self.level = str(config["level"])
        if "include_machine" in config:
            self.include_machine = bool(config["include_machine"])
        if "include_os" in config:
            self.include_os = bool(config["include_os"])

    def process(self, context: StageContext) -> StageContext:
        ds = context.dataset
        meta = context.metadata

        def set_attr(key: str, value: Any) -> None:
            if value is None or value == "":
                return
            if key in ds.attrs:
                return
            ds.attrs[key] = value

        set_attr("processor_name", "SeaSenseLib")
        set_attr("processor_version", _SSL_VERSION)
        set_attr("processor_level", self.level)
        set_attr("processing_level", self.level)

        reader_module = meta.get("reader_module")
        reader_name = meta.get("format_name") or meta.get("reader_class")
        reader_key = meta.get("format_key")

        set_attr("processor_module", reader_module)
        set_attr("processor_module_name", reader_name)
        set_attr("processor_module_key", reader_key)

        set_attr("processor_runtime", platform.python_implementation())
        set_attr("processor_runtime_version", platform.python_version())
        set_attr(
            "processor_execution_time_utc",
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

        if self.include_machine:
            set_attr("processor_machine", platform.node())
        if self.include_os:
            set_attr("processor_os", f"{platform.system()} {platform.release()}")

        # After processor metadata is added, parse sensor information
        self._add_sensor_variables(ds, context)
        
        context.dataset = ds
        logger.debug("Added processor metadata attributes")
        return context

    def _add_sensor_variables(self, ds, context: StageContext) -> None:
        """Add sensor variables after processor metadata is available."""
        from .raw_metadata import RawMetadata
        
        # Get raw metadata container from dataset attributes
        raw_metadata_json = ds.attrs.get("raw_metadata")
        if not raw_metadata_json:
            return
            
        try:
            import json
            raw_container = json.loads(raw_metadata_json)
        except (json.JSONDecodeError, TypeError):
            logger.debug("Could not parse raw_metadata for sensor processing")
            return
            
        # Create a RawMetadata instance to use its sensor parsing methods
        raw_metadata_handler = RawMetadata()
        
        # Process sensor variables based on processor module key (now available)
        processor_key = ds.attrs.get("processor_module_key", "")
        raw_format = raw_container.get("raw_format", "")
        
        logger.debug(f"Sensor parsing: raw_format='{raw_format}', processor_key='{processor_key}'")
        
        # Handle SeaBird data  
        if "cnv" in raw_format.lower():
            logger.debug("Processing SeaBird sensors")
            raw_metadata_handler._process_seabird_sensors(ds, raw_container)
        # Handle RBR data
        elif "rbr" in processor_key.lower():
            logger.debug("Processing RBR sensors")  
            raw_metadata_handler._process_rbr_sensors(ds, raw_container)
        else:
            logger.debug(f"No sensor processing for format '{raw_format}' with processor '{processor_key}'")


__all__ = ["ProcessorMetadata"]
