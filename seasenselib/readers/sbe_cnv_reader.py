"""Module for reading CTD data from SBE CNV files.
"""

from __future__ import annotations
import contextlib
import importlib
import io
import logging
import re
import sys
import threading
import types
import warnings
from datetime import datetime
import pandas as pd
import numpy as np
import xarray as xr

from seasenselib.readers.base import AbstractReader
import seasenselib.parameters as params

logger = logging.getLogger(__name__)

_PKG_RESOURCES_DEPRECATION_MESSAGE = r"pkg_resources is deprecated as an API.*"


@contextlib.contextmanager
def _suppress_pkg_resources_deprecation():
    """Suppress the known setuptools warning emitted by pycnv imports."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=_PKG_RESOURCES_DEPRECATION_MESSAGE,
            category=Warning,
        )
        yield


@contextlib.contextmanager
def _preserve_root_logging():
    """Prevent pycnv import-time logging.basicConfig from changing root logging."""
    root_logger = logging.getLogger()
    original_level = root_logger.level
    original_handlers = list(root_logger.handlers)

    try:
        yield
    finally:
        for handler in list(root_logger.handlers):
            if handler not in original_handlers:
                root_logger.removeHandler(handler)
                handler.close()
        for handler in original_handlers:
            if handler not in root_logger.handlers:
                root_logger.addHandler(handler)
        root_logger.setLevel(original_level)


class _PycnvLogForwarder(logging.Handler):
    """Forward pycnv records through the SeaSenseLib reader logger."""

    def emit(self, record: logging.LogRecord) -> None:
        logger.log(record.levelno, "pycnv: %s", record.getMessage())


class _ThreadLocalPycnvHandler(logging.Handler):
    """Log handler installed once on the pycnv logger; routes records per-thread.

    Each thread that calls :func:`_controlled_pycnv_logging` sets its own
    forwarder in thread-local storage.  Records arriving on threads that have
    no active forwarder are silently dropped, so pycnv noise never escapes
    this module unintentionally.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self._local = threading.local()

    def get_active_forwarder(self) -> logging.Handler | None:
        """Return the active forwarder for the current thread, or ``None``."""
        return getattr(self._local, "forwarder", None)

    def set_active_forwarder(self, handler: logging.Handler | None) -> None:
        """Activate *handler* for the current thread (or clear it when ``None``)."""
        self._local.forwarder = handler

    def emit(self, record: logging.LogRecord) -> None:
        forwarder = self.get_active_forwarder()
        if forwarder is not None and record.levelno >= forwarder.level:
            forwarder.emit(record)


_pycnv_handler_install_lock = threading.Lock()
_pycnv_thread_local_handler: _ThreadLocalPycnvHandler | None = None


def _ensure_controlled_pycnv_logger(pycnv_logger: logging.Logger) -> None:
    """Install and reassert the SeaSenseLib-owned pycnv logging state.

    pycnv mutates its logger level during normal reads.  Because the handler is
    intentionally persistent and thread-local, every guarded call must restore
    the controlled logger state instead of only doing it at first installation.
    """
    global _pycnv_thread_local_handler

    with _pycnv_handler_install_lock:
        if _pycnv_thread_local_handler is None:
            _pycnv_thread_local_handler = _ThreadLocalPycnvHandler()

        for handler in list(pycnv_logger.handlers):
            if handler is not _pycnv_thread_local_handler:
                pycnv_logger.removeHandler(handler)

        if _pycnv_thread_local_handler not in pycnv_logger.handlers:
            pycnv_logger.addHandler(_pycnv_thread_local_handler)

        pycnv_logger.setLevel(logging.NOTSET)
        pycnv_logger.propagate = False


@contextlib.contextmanager
def _controlled_pycnv_logging(level: int):
    """Route pycnv logging through this module, thread-safely.

    A single :class:`_ThreadLocalPycnvHandler` is installed on the ``pycnv``
    logger the first time this context manager runs.  Subsequent calls only
    update thread-local state, so concurrent readers never interfere with each
    other's log configuration.
    """
    pycnv_logger = logging.getLogger("pycnv")
    _ensure_controlled_pycnv_logger(pycnv_logger)

    forwarder = _PycnvLogForwarder(level=level)
    _pycnv_thread_local_handler.set_active_forwarder(forwarder)
    try:
        yield
    finally:
        _pycnv_thread_local_handler.set_active_forwarder(None)
        _ensure_controlled_pycnv_logger(pycnv_logger)


_stdout_capture_lock = threading.Lock()


class _ThreadLocalStdoutProxy:
    """sys.stdout proxy that routes writes to a per-thread capture buffer when active."""

    def __init__(self, original):
        self._original = original
        self._local = threading.local()

    def get_capture_stream(self):
        """Return the active capture stream for the current thread, or None."""
        return getattr(self._local, "stream", None)

    def set_capture_stream(self, stream):
        """Set the capture stream for the current thread."""
        self._local.stream = stream

    def write(self, text):
        stream = self.get_capture_stream()
        if stream is not None:
            return stream.write(text)
        return self._original.write(text)

    def flush(self):
        stream = self.get_capture_stream()
        if stream is not None:
            stream.flush()
        else:
            self._original.flush()

    def __getattr__(self, name):
        return getattr(self._original, name)


@contextlib.contextmanager
def _capture_pycnv_stdout():
    """Capture pycnv print output and expose it only as debug logging.

    Uses a thread-local proxy so concurrent threads are not affected.
    """
    with _stdout_capture_lock:
        if not isinstance(sys.stdout, _ThreadLocalStdoutProxy):
            sys.stdout = _ThreadLocalStdoutProxy(sys.stdout)
    proxy = sys.stdout
    stream = io.StringIO()
    previous = proxy.get_capture_stream()
    proxy.set_capture_stream(stream)
    try:
        yield
    finally:
        proxy.set_capture_stream(previous)
        output = stream.getvalue().strip()
        if output:
            for line in output.splitlines():
                logger.debug("pycnv stdout: %s", line)


def _pycnv_verbosity() -> int:
    """Return the logging level pycnv should use for the current reader call."""
    level = logger.getEffectiveLevel()
    if level == logging.NOTSET:
        return logging.ERROR
    return level


def _import_pkg_resources_for_pycnv():
    """Import pkg_resources for pycnv while suppressing its deprecation warning."""
    with _suppress_pkg_resources_deprecation():
        try:
            import pkg_resources  # noqa: F401
        except Exception:
            return None
    return pkg_resources


def _import_pycnv():
    """Import pycnv without letting it reconfigure root logging."""
    with _preserve_root_logging(), _suppress_pkg_resources_deprecation():
        import pycnv
    return pycnv


def _ensure_lazy_pylab() -> None:
    """Provide a lazy pylab module to avoid importing matplotlib on read."""
    if 'pylab' in sys.modules:
        return

    class _LazyPylab(types.ModuleType):
        _module = None

        def _load(self):
            if self._module is None:
                self._module = importlib.import_module('matplotlib.pylab')
                sys.modules['pylab'] = self._module
            return self._module

        def __getattr__(self, name):
            return getattr(self._load(), name)

        def __dir__(self):
            return dir(self._load())

    sys.modules['pylab'] = _LazyPylab('pylab')


class SbeCnvReader(AbstractReader):
    """ Reads sensor data from a SeaBird CNV file into a xarray Dataset. 

    This class is used to read SeaBird CNV files, which are commonly used for storing
    sensor data. The provided data is expected to be in a CNV format, and this reader
    is designed to parse that format correctly.

    The reader includes automatic file sanitization for common issues such as
    trailing whitespace and malformed lines that cause pycnv errors.

    Attributes
    ----------
    data : xr.Dataset
        The xarray Dataset containing the sensor data to be read from the CNV file.
    input_file : str
        The path to the input CNV file containing the sensor data.
    mapping : dict
        A mapping dictionary for renaming variables or attributes in the dataset.
    sanitize_input : bool
        Whether to automatically fix file format issues (default: True).
    Methods
    -------
    __init__(input_file, sanitize_input=True, use_default_latitude=None, default_latitude=None, mapping=None, **kwargs):
        Initializes the CnvReader with the input file and configuration options.
    data():
        Returns the xarray Dataset containing the sensor data.
    format_name():
        Returns the format of the file being read, which is 'SBE CNV'.
    file_extension():
        Returns the file extension for this reader, which is '.cnv'.
    
    Examples
    --------
    >>> # Default behavior (auto-fix enabled)
    >>> reader = SbeCnvReader('mooring_data.cnv')
    >>> ds = reader.data
    
    >>> # Disable file sanitization (stricter parsing)
    >>> reader = SbeCnvReader('data.cnv', sanitize_input=False)
    """

    _TIME_SOURCE_SECONDS_SINCE_2000 = "seconds_since_2000"
    _TIME_SOURCE_SECONDS_SINCE_1970 = "seconds_since_1970"
    _TIME_SOURCE_SECONDS_SINCE_START = "seconds_since_start_time"
    _TIME_SOURCE_JULIAN_DAYS = "julian_days"
    _TIME_SOURCE_INTERVAL = "start_time_plus_interval"

    _TIME_SOURCE_CANDIDATES = (
        # Preserve the legacy CNV preference order: high-resolution elapsed
        # scan time should win over coarser absolute time channels when both
        # are present.
        (params.TIME_S, _TIME_SOURCE_SECONDS_SINCE_START),
        (params.TIME_J, _TIME_SOURCE_JULIAN_DAYS),
        (params.TIME_Q, _TIME_SOURCE_SECONDS_SINCE_2000),
        (params.TIME_N, _TIME_SOURCE_SECONDS_SINCE_1970),
    )

    _TIME_SOURCE_FALLBACK_ALIASES = {
        params.TIME_Q: ("timeQ", "timeK"),
        params.TIME_N: ("timeN",),
        params.TIME_S: ("timeS",),
        params.TIME_J: ("timeJ", "timeJV2", "timeSCP"),
    }

    def __init__(self, input_file: str,
                 sanitize_input: bool = True,
                 use_default_latitude: bool | None = None,
                 default_latitude: float | None = None,
                 mapping: dict | None = None,
                 **kwargs):
        """Initialize SbeCnvReader with configuration options.
        
        Parameters
        ----------
        input_file : str
            Path to the CNV file.
        sanitize_input : bool, default=True
            Whether to automatically fix known file format issues (e.g., trailing
            whitespace in start_time lines). When False, files with format issues
            may fail to load. CLI: --reader-arg sanitize-input=false
        use_default_latitude : bool, optional
            Programmatic compatibility option for enabling fallback latitude use.
            The CLI exposes this as the global --default-latitude option instead.
        default_latitude : float, optional
            Latitude used for pressure-to-depth derivation when latitude is missing
            and fallback latitude use is enabled.
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
        default_latitude_configured = (
            use_default_latitude is not None
            or default_latitude is not None
            or "fix_missing_coords" in kwargs
        )
        if "fix_missing_coords" in kwargs:
            use_default_latitude = bool(kwargs.pop("fix_missing_coords"))

        super().__init__(input_file, mapping, **kwargs)
        self._sanitize_input = sanitize_input
        self._default_latitude_configured = default_latitude_configured
        self._use_default_latitude = (
            bool(use_default_latitude)
            if use_default_latitude is not None
            else default_latitude is not None
        )
        self._default_latitude = 45.0 if default_latitude is None else default_latitude
        self._validate_file()

    @classmethod
    def _get_valid_extensions(cls) -> tuple[str, ...]:
        """Return valid file extensions for CNV files."""
        return ('.cnv',)

    @classmethod
    def reader_args(cls) -> list[dict]:
        return [
            cls._reader_arg(
                "sanitize_input",
                "bool",
                True,
                "Automatically fix known CNV formatting issues before parsing.",
            ),
        ]

    def __get_scan_interval_in_seconds(self, string):
        pattern = r'^# interval = seconds: ([\d.]+)$'
        match = re.search(pattern, string, re.MULTILINE)
        if match:
            seconds = float(match.group(1))
            return seconds
        return None

    def __get_bad_flag(self, string):
        pattern = r'^# bad_flag = (.+)$'
        match = re.search(pattern, string, re.MULTILINE)
        if match:
            bad_flag = match.group(1)
            return bad_flag
        return None

    def __get_start_time_from_header(self, header_string: str) -> pd.Timestamp | None:
        """Extract start_time from CNV header.
        
        Parameters
        ----------
        header_string : str
            The header string from the CNV file.

        Returns
        -------
        pd.Timestamp | None
            The extracted start time or None if not found.
        """

        pattern = r'^# start_time = ([A-Za-z]{3} \d{1,2} \d{4} \d{2}:\d{2}:\d{2})'
        match = re.search(pattern, header_string, re.MULTILINE)
        if match:
            time_str = match.group(1)
            try:
                # Parse the time string like "Aug 01 2025 10:10:08"
                return pd.to_datetime(time_str, format='%b %d %Y %H:%M:%S')
            except ValueError:
                return None
        return None

    def __normalize_time_coords(self, time_coords):
        """Normalize time coordinates to ensure consistent format."""
        if time_coords is None or len(time_coords) == 0:
            return time_coords
        
        # Convert to pandas datetime if it's not already
        try:
            time_coords_normalized = pd.to_datetime(time_coords)
            #print(f"Normalized time_coords type: {type(time_coords_normalized)}")
            #print(f"Normalized time_coords dtype: {time_coords_normalized.dtype}")
            #if len(time_coords_normalized) > 0:
                #print(f"Normalized time_coords[0]: {time_coords_normalized[0]}")
            
            # Convert DatetimeIndex to numpy array for xarray compatibility
            if isinstance(time_coords_normalized, pd.DatetimeIndex):
                time_coords_normalized = time_coords_normalized.to_numpy()
                #print(f"Converted to numpy array: {type(time_coords_normalized)}")
                #print(f"Numpy array dtype: {time_coords_normalized.dtype}")
            
            return time_coords_normalized
        except Exception as e:
            logger.warning("Error normalizing time coordinates: %s", e)
            return time_coords

    def __get_time_aliases(self, canonical_name: str) -> tuple[str, ...]:
        """Return raw CNV names that should be interpreted as a time source."""
        aliases = [canonical_name]
        aliases.extend(params.default_mappings.get(canonical_name, []))
        aliases.extend(self._TIME_SOURCE_FALLBACK_ALIASES.get(canonical_name, ()))
        return tuple(dict.fromkeys(aliases))

    def __find_time_source(
        self,
        xarray_data: dict,
        canonical_name: str,
    ) -> tuple[str | None, np.ndarray | None]:
        """Find a raw time source by canonical name and known CNV aliases."""
        aliases = self.__get_time_aliases(canonical_name)

        for alias in aliases:
            if alias in xarray_data:
                return alias, xarray_data[alias]

        lower_to_key = {key.lower(): key for key in xarray_data}
        for alias in aliases:
            key = lower_to_key.get(alias.lower())
            if key is not None:
                return key, xarray_data[key]

        return None, None

    def __set_time_coordinate_source(
        self,
        source_name: str | None,
        source_type: str | None,
    ) -> None:
        self._time_coordinate_source_name = source_name
        self._time_coordinate_source_type = source_type

    def __calculate_time_coordinates(
        self,
        xarray_data: dict,
        cnv: pycnv.pycnv,
        max_count: int,
    ) -> np.ndarray | None:
        """Calculate time coordinates from various time formats in CNV data.

        Parameters
        ----------
        xarray_data : dict
            Dictionary containing sensor data.
        cnv : pycnv.pycnv
            CNV object containing metadata.
        max_count : int
            Maximum number of data points.

        Returns
        -------
        numpy.ndarray | None
            Time coordinates as datetime values.
        """

        from seasenselib.readers.utils import TimeConverter
        
        # Try to extract start_time from header instead of using cnv.date
        start_time_from_header = self.__get_start_time_from_header(cnv.header)
        if start_time_from_header:
            offset_datetime = start_time_from_header
            logger.debug(f"Using header start_time: {offset_datetime}")
        else:
            # Fallback to cnv.date
            if cnv.date is not None:
                offset_datetime = pd.to_datetime(cnv.date.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                # Final fallback - use January 1st of current year
                current_year = datetime.now().year
                offset_datetime = pd.to_datetime(f"{current_year}-01-01 00:00:00")
            logger.debug(f"Using cnv.date fallback: {offset_datetime}")

        self.__set_time_coordinate_source(None, None)

        time_coords = None
        for canonical_name, source_type in self._TIME_SOURCE_CANDIDATES:
            source_name, values = self.__find_time_source(xarray_data, canonical_name)
            if source_name is None or values is None:
                continue

            self.__set_time_coordinate_source(source_name, source_type)
            if source_type == self._TIME_SOURCE_SECONDS_SINCE_2000:
                time_coords = np.array([
                    TimeConverter.elapsed_seconds_since_jan_2000_to_datetime(elapsed_seconds)
                    for elapsed_seconds in values
                ])
            elif source_type == self._TIME_SOURCE_SECONDS_SINCE_1970:
                time_coords = np.array([
                    TimeConverter.elapsed_seconds_since_jan_1970_to_datetime(elapsed_seconds)
                    for elapsed_seconds in values
                ])
            elif source_type == self._TIME_SOURCE_SECONDS_SINCE_START:
                time_coords = np.array([
                    TimeConverter.elapsed_seconds_since_offset_to_datetime(
                        elapsed_seconds,
                        offset_datetime,
                    )
                    for elapsed_seconds in values
                ])
            elif source_type == self._TIME_SOURCE_JULIAN_DAYS:
                year_startdate = datetime(year=offset_datetime.year, month=1, day=1)
                time_coords = np.array([
                    TimeConverter.julian_to_gregorian(jday, year_startdate)
                    for jday in values
                ])
            break

        if time_coords is None:
            timedelta = self.__get_scan_interval_in_seconds(cnv.header)
            if timedelta:
                self.__set_time_coordinate_source(
                    "start_time + interval",
                    self._TIME_SOURCE_INTERVAL,
                )
                time_coords = [
                    offset_datetime + pd.Timedelta(seconds=i * timedelta)
                    for i in range(max_count)
                ][:]

        # Normalize time coordinates to ensure consistent format
        return self.__normalize_time_coords(time_coords)

    def __assign_time_coordinate_metadata(self, ds):
        """Record how the CNV time coordinate was derived."""
        source_name = getattr(self, "_time_coordinate_source_name", None)
        source_type = getattr(self, "_time_coordinate_source_type", None)
        if source_name:
            ds.attrs["cnv_time_source_variable"] = source_name
        if source_type:
            ds.attrs["cnv_time_source_type"] = source_type
        if params.TIME in ds.coords:
            if source_name:
                ds[params.TIME].attrs.setdefault("source_variable", source_name)
            if source_type:
                ds[params.TIME].attrs.setdefault("source_type", source_type)
        return ds

    def __assign_cnv_metadata(self, ds, xarray_labels, xarray_units, channel_names, cnv):
        """Assign CNV-specific metadata while preserving CF-compliant units when CNV units are missing.
        
        Parameters
        ----------
        ds
            xarray Dataset to add metadata to.
        xarray_labels
            Dictionary containing CNV channel labels/names.
        xarray_units
            Dictionary containing CNV channel units.
        channel_names
            List of original channel names from CNV.
        cnv
            CNV object containing header information.
            
        Returns
        -------
        xarray.Dataset 
            Dataset with CNV metadata assigned.
        """
        
        for var_name in ds.data_vars:
            # Find the original CNV channel name that corresponds to this variable
            original_channel = None
            
            # Check if this variable name directly matches a channel name
            if var_name in channel_names:
                original_channel = var_name
            else:
                # For renamed variables, try to find the original channel
                # This is a bit tricky after postprocessing, so we check both directions
                for channel in channel_names:
                    if channel.lower() == var_name.lower():
                        original_channel = channel
                        break
            
            if original_channel:
                # Store original CNV name and label
                if original_channel in xarray_labels:
                    ds[var_name].attrs['cnv_original_name'] = original_channel
                    ds[var_name].attrs['cnv_original_label'] = xarray_labels[original_channel]
                    ds[var_name].attrs['cnv_original_unit'] = xarray_units[original_channel]

                # Handle units: CNV units take precedence if they exist
                if original_channel in xarray_units and xarray_units[original_channel]:
                    cnv_unit = xarray_units[original_channel].strip()
                    if cnv_unit:  # Only use non-empty units
                        ds[var_name].attrs['units'] = cnv_unit
        
        return ds

    def __assign_cnv_global_attributes(self, ds, cnv):
        """Assign CNV-specific global attributes to the xarray Dataset.
        
        Parameters
        ----------
        ds
            xarray Dataset to add global attributes to.
        cnv
            CNV object containing metadata from pycnv.

        Returns
        -------
        xarray.Dataset
            Dataset with CNV global attributes assigned.
        """

        # Extract metadata from CNV header if available
        if cnv.header:
            # Extract SBE model via regex. Example: "* Sea-Bird SBE 9plus Data File:"
            sbe_model_match = re.search(r"\* Sea-Bird SBE *(?P<value>\d.*?) +Data File:", 
                                      cnv.header, re.IGNORECASE)
            if sbe_model_match:
                ds.attrs['cnv_sbe_model'] = "SBE " + sbe_model_match.group("value")
            
            # Extract software version via regex. Example: "* Software Version Seasave V 7.26.7.121"
            software_version_match = re.search(r"\* Software Version (?P<value>.+?)(?:\s*$)", 
                                             cnv.header, re.MULTILINE | re.IGNORECASE)
            if software_version_match:
                ds.attrs['cnv_software_version'] = software_version_match.group("value").strip()
        
        # Assign date/time attributes
        if cnv.date:
            ds.attrs['cnv_start_date'] = cnv.date.strftime("%Y-%m-%d %H:%M:%S")
        
        if cnv.upload_date:
            ds.attrs['cnv_upload_date'] = cnv.upload_date.strftime("%Y-%m-%d %H:%M:%S")
        
        if cnv.nmea_date:
            ds.attrs['cnv_nmea_date'] = cnv.nmea_date.strftime("%Y-%m-%d %H:%M:%S")
        
        # Assign scan interval if available
        if hasattr(cnv, 'interval_s') and cnv.interval_s:
            ds.attrs['cnv_interval_seconds'] = cnv.interval_s
        else:
            # Fallback: try to extract from header
            interval_from_header = self.__get_scan_interval_in_seconds(cnv.header)
            if interval_from_header:
                ds.attrs['cnv_interval_seconds'] = interval_from_header
        
        # Assign list of sensor information
        sensor_metadata = self.__extract_sensor_metadata_from_xml(cnv.header)
        for channel_num, metadata in sensor_metadata.items():
            entry_name = f'cnv_sensor_{channel_num}'
            # Create list of sensor information for a sensor without empty entries
            combined_sensor_metadata = {k: v for k, v in metadata.items() if v is not None}
            ds.attrs[entry_name] = combined_sensor_metadata

        return ds

    def __extract_sensor_metadata_from_xml(self, cnv_header):
        """Extract sensor metadata from XML-style sensor entries in CNV header.

        Parameters
        ----------
        cnv_header
            CNV header string containing XML sensor information.

        Returns
        -------
        dict
            Dictionary mapping channel numbers to sensor metadata.
        """

        import xml.etree.ElementTree as ET
        
        sensor_metadata: dict[int, dict[str, str | int]] = {}
        
        try:
            # Extract the XML sensor block from the CNV header
            xml_start = cnv_header.find('# <Sensors count=')
            if xml_start == -1:
                return sensor_metadata
            
            # Find the end of the XML block (look for closing </Sensors>)
            xml_end = cnv_header.find('# </Sensors>', xml_start)
            if xml_end == -1:
                # If no closing tag found, try to find where XML ends
                lines = cnv_header[xml_start:].split('\n')
                xml_lines = []
                for line in lines:
                    if line.startswith('#') and ('<' in line or '>' in line):
                        xml_lines.append(line[1:].strip())  # Remove '# ' prefix
                    else:
                        break
                xml_content = '\n'.join(xml_lines)
            else:
                xml_block = cnv_header[xml_start:xml_end + len('# </Sensors>')]
                # Remove '# ' prefix from each line
                xml_lines = []
                for line in xml_block.split('\n'):
                    if line.startswith('# '):
                        xml_lines.append(line[2:])
                xml_content = '\n'.join(xml_lines)
            
            # Parse the XML
            root = ET.fromstring(xml_content)
            
            # Extract sensor information
            for sensor in root.findall('sensor'):
                channel_attr = sensor.get('Channel')
                if channel_attr:
                    channel_num = int(channel_attr)
                    metadata: dict[str, str | int] = {'channel': channel_num}
                    
                    # Find sensor type and extract information
                    for sensor_element in sensor:
                        if sensor_element.tag.endswith('Sensor'):
                            sensor_type = sensor_element.tag
                            metadata['sensor_type'] = sensor_type
                            
                            # Extract SerialNumber
                            serial_elem = sensor_element.find('SerialNumber')
                            if serial_elem is not None and serial_elem.text:
                                metadata['serial_number'] = serial_elem.text
                            
                            # Extract CalibrationDate
                            cal_date_elem = sensor_element.find('CalibrationDate')
                            if cal_date_elem is not None and cal_date_elem.text:
                                metadata['calibration_date'] = cal_date_elem.text
                            
                            # Extract SensorID if available
                            sensor_id = sensor_element.get('SensorID')
                            if sensor_id:
                                metadata['sensor_id'] = sensor_id
                    
                    sensor_metadata[channel_num] = metadata
        
        except Exception as e:
            # If XML parsing fails, fall back to regex extraction
            logger.warning("XML parsing failed, trying regex fallback: %s", e)
            return self.__extract_sensor_metadata_from_regex(cnv_header)
        
        return sensor_metadata

    def __extract_sensor_metadata_from_regex(self, cnv_header):
        """Fallback method to extract sensor metadata using regex when XML parsing fails.

        Parameters
        ----------
        cnv_header
            CNV header string.
            
        Returns
        -------
        dict
            Dictionary mapping channel numbers to sensor metadata.
        """

        sensor_metadata: dict[int, dict[str, str | int]] = {}
        
        # Look for sensor channel patterns
        sensor_pattern = r'#\s*<sensor Channel="(\d+)"\s*>'
        sensor_matches = re.finditer(sensor_pattern, cnv_header)
        
        for match in sensor_matches:
            channel_num = int(match.group(1))
            metadata: dict[str, str | int] = {'channel': channel_num}
            
            # Find the content for this sensor (until next sensor or end)
            start_pos = match.end()
            next_sensor = re.search(r'#\s*<sensor Channel="(\d+)"\s*>', cnv_header[start_pos:])
            if next_sensor:
                end_pos = start_pos + next_sensor.start()
                sensor_content = cnv_header[start_pos:end_pos]
            else:
                # Look for closing sensor tag or end of sensors block
                end_match = re.search(r'#\s*</sensor>|#\s*</Sensors>', cnv_header[start_pos:])
                if end_match:
                    end_pos = start_pos + end_match.end()
                    sensor_content = cnv_header[start_pos:end_pos]
                else:
                    sensor_content = cnv_header[start_pos:]
            
            # Extract comment information
            comment_match = re.search(r'#\s*<!--\s*([^>]+?)\s*-->', sensor_content)
            if comment_match:
                comment_text = comment_match.group(1).strip()
                metadata['sensor_comment'] = comment_text
                
                # Parse frequency and parameter info from comment
                freq_match = re.search(r'Frequency\s+(\d+)', comment_text, re.IGNORECASE)
                if freq_match:
                    metadata['frequency_channel'] = int(freq_match.group(1))
                
                # Extract parameter type from comment (Temperature, Conductivity, etc.)
                param_match = re.search(r'Frequency\s+\d+,\s*(.+)', comment_text, re.IGNORECASE)
                if param_match:
                    metadata['parameter_type'] = param_match.group(1).strip()
            
            # Extract SerialNumber
            serial_match = re.search(r'#\s*<SerialNumber>([^<]+)</SerialNumber>', sensor_content)
            if serial_match:
                metadata['serial_number'] = serial_match.group(1)
            
            # Extract CalibrationDate
            cal_date_match = re.search(r'#\s*<CalibrationDate>([^<]+)</CalibrationDate>', sensor_content)
            if cal_date_match:
                metadata['calibration_date'] = cal_date_match.group(1)
            
            # Extract sensor type
            sensor_type_match = re.search(r'#\s*<(\w+Sensor)\s+SensorID="([^"]*)"', sensor_content)
            if sensor_type_match:
                metadata['sensor_type'] = sensor_type_match.group(1)
                metadata['sensor_id'] = sensor_type_match.group(2)
            
            sensor_metadata[channel_num] = metadata
        
        return sensor_metadata
    
    def _sanitize_cnv_file(self, file):
        """ Sanitizes a CNV file to fix known issues that pycnv cannot handle.
        
        This function creates a temporary sanitized version of the CNV file,
        fixing common issues like trailing whitespace in start_time lines.
        
        Parameters
        ----------
        file : str
            Path to the CNV file to sanitize.

        Returns
        -------
        str
            Path to the sanitized file (may be a temporary file or the original).
        bool
            True if sanitization was needed, False if file was already clean.
        """
        import tempfile
        import os
        
        needs_sanitization = False
        sanitized_lines = []
        
        # Read file and check/fix problematic patterns
        with open(file, 'r', encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                # Fix 1: Remove trailing whitespace from start_time lines
                if re.match(r'^# start_time \= [A-Za-z]{3} \d{1,2} \d{4} \d{2}:\d{2}:\d{2}\s+$', line):
                    line = line.rstrip() + '\n'
                    needs_sanitization = True
                    logger.debug(
                        "Fixed trailing whitespace in start_time at line %d",
                        line_num
                    )
                
                # Fix 2: Skip lines starting with multiple asterisks (malformed)
                if re.match(r'^\* \*', line):
                    logger.warning(
                        "Skipping malformed line %d: %s",
                        line_num,
                        line.strip()
                    )
                    needs_sanitization = True
                    continue
                
                sanitized_lines.append(line)
        
        # If sanitization was needed, create a temporary file
        if needs_sanitization:
            # Create temporary file in the same directory to preserve relative paths
            temp_fd, temp_path = tempfile.mkstemp(suffix='.cnv', prefix='sanitized_', 
                                                   dir=os.path.dirname(file) or '.')
            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    f.writelines(sanitized_lines)
                logger.debug("Created sanitized temporary file for pycnv processing")
                return temp_path, True
            except Exception as e:
                # Clean up temp file if writing fails
                try:
                    os.unlink(temp_path)
                except Exception:
                    # Ignore errors during cleanup - the original exception is more important
                    pass
                raise e
        
        return file, False

    def _read_raw_header(self, file: str) -> str | None:
        """Read the CNV header verbatim (up to *END*)."""
        try:
            lines = []
            with open(file, 'r', encoding='utf-8', errors='replace') as handle:
                for line in handle:
                    lines.append(line.rstrip("\n"))
                    if line.strip().startswith("*END*"):
                        break
            if lines:
                return "\n".join(lines)
        except Exception as exc:
            logger.debug("Failed to read raw CNV header: %s", exc)
        return None

    def _load_data(self) -> xr.Dataset:
        """ Reads a CNV file and converts it to a xarray Dataset.
        
        Returns
        -------
        xr.Dataset
            The loaded dataset.
        """

        _ensure_lazy_pylab()
        pkg_resources = _import_pkg_resources_for_pycnv()

        if pkg_resources is None or not all(
            hasattr(pkg_resources, attr)
            for attr in ("resource_filename", "resource_stream", "resource_string")
        ):
            # pycnv still imports pkg_resources (deprecated). Provide a minimal shim so
            # imports succeed on environments without setuptools (e.g., Python 3.13).
            import sys
            import types
            from importlib import resources as _resources

            def _as_package_name(pkg) -> str:
                if isinstance(pkg, str):
                    return pkg
                for attr in ("project_name", "name", "key"):
                    if hasattr(pkg, attr):
                        return str(getattr(pkg, attr))
                return str(pkg)

            def _resource_path(pkg, resource: str) -> str:
                pkg_name = _as_package_name(pkg)
                if hasattr(_resources, "files"):
                    return str(_resources.files(pkg_name).joinpath(resource))
                with _resources.path(pkg_name, resource) as p:
                    return str(p)

            def _resource_filename(pkg, resource: str) -> str:
                return _resource_path(pkg, resource)

            def _resource_stream(pkg, resource: str):
                return open(_resource_path(pkg, resource), "rb")

            def _resource_string(pkg, resource: str) -> bytes:
                with open(_resource_path(pkg, resource), "rb") as handle:
                    return handle.read()

            if pkg_resources is None:
                pkg_resources = types.ModuleType("pkg_resources")
                sys.modules.setdefault("pkg_resources", pkg_resources)
                logger.debug(
                    "pkg_resources not available; using stub for pycnv import"
                )
            else:
                logger.debug(
                    "pkg_resources missing resource helpers; patching for pycnv import"
                )

            if not hasattr(pkg_resources, "resource_filename"):
                pkg_resources.resource_filename = _resource_filename
            if not hasattr(pkg_resources, "resource_stream"):
                pkg_resources.resource_stream = _resource_stream
            if not hasattr(pkg_resources, "resource_string"):
                pkg_resources.resource_string = _resource_string
        pycnv = _import_pycnv()
        import os

        # Sanitize the file if sanitize_input is enabled (fixes pycnv incompatibilities)
        self._raw_header = self._read_raw_header(self.input_file)
        if self._sanitize_input:
            file_to_read, was_sanitized = self._sanitize_cnv_file(self.input_file)
        else:
            file_to_read = self.input_file
            was_sanitized = False
        
        try:
            # Read CNV file with pycnv reader
            pycnv_verbosity = _pycnv_verbosity()
            with _controlled_pycnv_logging(pycnv_verbosity), _capture_pycnv_stdout():
                cnv = pycnv.pycnv(file_to_read, verbosity=pycnv_verbosity)
        except Exception as e:
            # Clean up temp file before re-raising
            if was_sanitized and os.path.exists(file_to_read):
                try:
                    os.unlink(file_to_read)
                except Exception:
                    # Ignore errors during cleanup - the original exception is more important
                    pass
            
            # Provide helpful error message
            error_msg = str(e)
            if "dimension 'time' already exists" in error_msg:
                raise ValueError(
                    f"pycnv failed to parse CNV file: {error_msg}\n"
                    f"This is a known pycnv issue with certain CNV file formats. "
                    f"The file may have incompatible time variables or header formatting."
                ) from e
            else:
                raise ValueError(f"pycnv failed to parse CNV file: {error_msg}") from e

        # Store cnv object for metadata extraction
        self._cnv = cnv

        # Map column names ('channel names') to standard names
        channel_names = [d['name'] for d in cnv.channels if 'name' in d]

        # Validate required parameters
        #super()._validate_necessary_parameters(self.mapping, cnv.lat, cnv.lon, 'mapping data')

        # Create dictionaries with data, names, and labels
        xarray_data = dict()
        xarray_labels = dict()
        xarray_units = dict()
        max_count = 0

        for channel_name in channel_names:
            # Map channel names to standard names
            if cnv.data is not None and channel_name in cnv.data:
                xarray_data[channel_name] = cnv.data[channel_name][:]
                xarray_labels[channel_name] = cnv.names[channel_name]
                xarray_units[channel_name] = cnv.units[channel_name]
                max_count = max(max_count, len(cnv.data[channel_name]))

        # Calculate time coordinates
        time_coords = self.__calculate_time_coordinates(xarray_data, cnv, max_count)

        # Create xarray Dataset
        ds = self._get_xarray_dataset_template(time_coords, None, cnv.lat, cnv.lon)
        ds = self.__assign_time_coordinate_metadata(ds)

        # Assign data to xarray Dataset
        for key in xarray_data.keys():
            ds[key] = ([params.TIME], xarray_data[key])

        # Assign CNV-specific global attributes
        ds = self.__assign_cnv_global_attributes(ds, cnv)

        # Assign CNV-specific metadata (preserves CNV units, adds original names/labels)
        ds = self.__assign_cnv_metadata(ds, xarray_labels, xarray_units, channel_names, cnv)

        # Depth derivation is handled by the pipeline derivation stage.

        # Parameter derivation (density, potential_temperature, sound_speed) is 
        # handled by the parameter_derivation layer in the pipeline derivation stage.
        # This keeps readers focused on data loading, not processing.

        # Check for bad flag
        bad_flag = self.__get_bad_flag(cnv.header)
        if bad_flag is not None:
            for var in ds:
                ds[var] = ds[var].where(ds[var] != bad_flag, np.nan)

        # Clean up temporary sanitized file after all processing is complete
        if was_sanitized and os.path.exists(file_to_read):
            try:
                os.unlink(file_to_read)
            except Exception as e:
                logger.warning("Could not delete temporary file %s: %s", file_to_read, e)

        return ds

    @classmethod
    def format_key(cls) -> str:
        return 'sbe-cnv'

    @classmethod
    def format_name(cls) -> str:
        return 'SeaBird CNV'

    @classmethod
    def file_extension(cls) -> str | None:
        return '.cnv'
    
    @classmethod
    def format_mappings(cls) -> dict:
        """Get SeaBird CNV format-specific variable name mappings.
        
        Returns:
            Dictionary mapping canonical parameter names to SeaBird-specific
            variable name patterns commonly found in CNV files.
        """
        return {
            params.TEMPERATURE: ['t090C', 't068', 't190C', 't168', 'tv290C'],
            params.SALINITY: ['sal00', 'sal11'],
            params.CONDUCTIVITY: ['c0mS/cm', 'c0S/m', 'c1mS/cm', 'c1S/m', 'cond0S/m', 'cond1S/m', 'cond0mS/cm', 'cond1mS/cm'],
            params.PRESSURE: ['prdM', 'prDM', 'prSM', 'prM', 'pr50M', 'pr200M', 'pr350M'],
            params.DEPTH: ['depSM'],
            params.OXYGEN: ['sbeox0V', 'sbeox0', 'sbeox0ML/L', 'sbeox0Mm/Kg', 'sbeox1V', 'sbeox1ML/L'],
            params.TURBIDITY: ['turbWETntu0'],
            params.FLUORESCENCE: ['flECO-AFL'],
            params.DENSITY: ['sigma-t00', 'sigma-t11', 'sigma-theta00', 'sigma-theta11'],
            params.POTENTIAL_TEMPERATURE: ['potemp090C', 'potemp190C'],
        }
