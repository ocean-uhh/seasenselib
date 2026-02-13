"""
SeaBird metadata parser for extracting instrument details from raw CNV metadata.

This module provides utilities to parse SeaBird instrument metadata from the 
raw_metadata JSON structure and extract key instrument characteristics like
device type, serial numbers, calibration coefficients, and hardware details.
"""

import re
import json
from datetime import datetime
from typing import Dict, Any, Optional, Union


def parse_seabird_metadata(raw_metadata: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse SeaBird CNV raw metadata to extract key instrument information.
    
    Parameters
    ----------
    raw_metadata : str or dict
        Raw metadata JSON string from SeaBird CNV reader, or pre-parsed dict
        
    Returns
    -------
    dict
        Parsed instrument metadata containing:
        - device_type: Instrument model (e.g., 'SBE37SM-RS232')
        - serial_number: Instrument serial number
        - sbe_pump_installed: Whether pump is installed ('yes'/'no')
        - calibration_date: ISO8601 formatted calibration date
        - {Parameter}_calibration_coefficients: Calibration coefficients for each sensor
    """
    parsed = {}
    
    # Parse JSON string if needed (raw_metadata is typically a JSON string)
    if isinstance(raw_metadata, str):
        try:
            metadata_dict = json.loads(raw_metadata)
        except json.JSONDecodeError:
            return parsed
    elif isinstance(raw_metadata, dict):
        metadata_dict = raw_metadata
    else:
        return parsed
    
    # Extract the header block which contains the XML metadata
    blocks = metadata_dict.get('blocks', {})
    header_block = blocks.get('header', '')
    
    if not header_block:
        return parsed
    
    # Extract device type and serial number from HardwareData
    hardware_match = re.search(r"<HardwareData\s+DeviceType='([^']+)'\s+SerialNumber='([^']+)'", header_block)
    if hardware_match:
        parsed['device_type'] = hardware_match.group(1)
        parsed['serial_number'] = hardware_match.group(2)
    
    # Extract pump installation status
    pump_match = re.search(r"<PumpInstalled>([^<]+)</PumpInstalled>", header_block)
    if pump_match:
        parsed['sbe_pump_installed'] = pump_match.group(1).strip()
    
    # Extract calibration date
    cal_date_match = re.search(r"<CalibrationDate>([^<]+)</CalibrationDate>", header_block)
    if cal_date_match:
        cal_date_str = cal_date_match.group(1).strip()
        try:
            # Parse date like "31-Dec-09" and convert to ISO8601
            cal_date = datetime.strptime(cal_date_str, "%d-%b-%y")
            parsed['calibration_date'] = cal_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            # Try alternative formats if needed
            try:
                cal_date = datetime.strptime(cal_date_str, "%d-%b-%Y")
                parsed['calibration_date'] = cal_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                parsed['calibration_date'] = cal_date_str  # Store as-is if parsing fails
    
    # Extract calibration coefficients for each sensor
    cal_pattern = r"<Calibration[^>]*id='([^']+)'[^>]*>(.*?)</Calibration>"
    calibrations = re.findall(cal_pattern, header_block, re.DOTALL)
    
    for sensor_id, cal_block in calibrations:
        coefficients = []
        
        # Find all coefficient tags (excluding SerialNum and CalDate)
        coeff_pattern = r"<([A-Z][A-Z0-9]*[A-Z0-9])>([^<]+)</[A-Z][A-Z0-9]*[A-Z0-9]>"
        coeff_matches = re.findall(coeff_pattern, cal_block)
        
        for coeff_name, coeff_value in coeff_matches:
            # Skip non-coefficient fields
            if coeff_name not in ['SerialNum', 'CalDate']:
                coefficients.append(f"{coeff_name}={coeff_value.strip()}")
        
        if coefficients:
            key = f"{sensor_id}_calibration_coefficients"
            parsed[key] = ", ".join(coefficients)
    
    return parsed


def extract_sensor_serial_numbers(raw_metadata: Union[str, Dict[str, Any]]) -> Dict[str, str]:
    """
    Extract serial numbers for each sensor type from calibration blocks.
    
    Parameters
    ----------
    raw_metadata : dict or str
        Raw metadata dictionary or JSON string from SeaBird CNV reader
        
    Returns
    -------
    dict
        Dictionary mapping sensor type to serial number
    """
    serial_numbers = {}
    
    # Parse JSON string if needed
    if isinstance(raw_metadata, str):
        try:
            metadata_dict = json.loads(raw_metadata)
        except json.JSONDecodeError:
            return serial_numbers
    elif isinstance(raw_metadata, dict):
        metadata_dict = raw_metadata
    else:
        return serial_numbers
    
    blocks = metadata_dict.get('blocks', {})
    header_block = blocks.get('header', '')
    
    if not header_block:
        return serial_numbers
    
    # Extract serial numbers from each calibration block
    cal_pattern = r"<Calibration[^>]*id='([^']+)'[^>]*>(.*?)</Calibration>"
    calibrations = re.findall(cal_pattern, header_block, re.DOTALL)
    
    for sensor_id, cal_block in calibrations:
        serial_match = re.search(r"<SerialNum>([^<]+)</SerialNum>", cal_block)
        if serial_match:
            serial_numbers[sensor_id] = serial_match.group(1).strip()
    
    return serial_numbers


def get_instrument_summary(raw_metadata: Union[str, Dict[str, Any]]) -> str:
    """
    Generate a human-readable summary of the SeaBird instrument.
    
    Parameters
    ----------
    raw_metadata : dict or str
        Raw metadata dictionary or JSON string from SeaBird CNV reader
        
    Returns
    -------
    str
        Human-readable instrument summary
    """
    parsed = parse_seabird_metadata(raw_metadata)
    
    if not parsed:
        return "SeaBird instrument (details unavailable)"
    
    summary_parts = []
    
    # Basic instrument info
    device_type = parsed.get('device_type', 'Unknown SeaBird instrument')
    serial_number = parsed.get('serial_number', 'Unknown S/N')
    summary_parts.append(f"{device_type} (S/N: {serial_number})")
    
    # Pump status
    pump_status = parsed.get('sbe_pump_installed', '').lower()
    if pump_status == 'yes':
        summary_parts.append("with pump")
    elif pump_status == 'no':
        summary_parts.append("without pump")
    
    # Calibration date
    cal_date = parsed.get('calibration_date')
    if cal_date:
        if cal_date.endswith('Z'):
            # ISO format, extract year
            cal_year = cal_date[:4]
            summary_parts.append(f"calibrated {cal_year}")
        else:
            summary_parts.append(f"calibrated {cal_date}")
    
    # Number of sensors with calibration
    sensor_count = len([k for k in parsed.keys() if k.endswith('_calibration_coefficients')])
    if sensor_count > 0:
        summary_parts.append(f"{sensor_count} calibrated sensors")
    
    return ", ".join(summary_parts)


def parse_sbe9_sensors(raw_metadata: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse SBE 9 CTD sensor metadata to extract individual sensor information.
    
    Parameters
    ----------
    raw_metadata : str or dict
        Raw metadata JSON string from SeaBird CNV reader, or pre-parsed dict
        
    Returns
    -------
    dict
        Parsed sensor metadata containing:
        - sensors: List of sensor dictionaries with type, serial number, coefficients
    """
    sensors = []
    
    # Parse JSON string if needed
    if isinstance(raw_metadata, str):
        try:
            metadata_dict = json.loads(raw_metadata)
        except json.JSONDecodeError:
            return {'sensors': sensors}
    elif isinstance(raw_metadata, dict):
        metadata_dict = raw_metadata
    else:
        return {'sensors': sensors}
    
    # Extract the header block which contains the XML metadata
    blocks = metadata_dict.get('blocks', {})
    header_block = blocks.get('header', '')
    
    if not header_block:
        return {'sensors': sensors}
    
    # Find all sensor blocks
    sensor_pattern = r'<sensor Channel="(\d+)"[^>]*>(.*?)</sensor>'
    sensor_matches = re.findall(sensor_pattern, header_block, re.DOTALL)
    
    for channel, sensor_block in sensor_matches:
        # Check for different sensor types
        temp_match = re.search(r'<TemperatureSensor[^>]*SensorID="([^"]+)"[^>]*>(.*?)</TemperatureSensor>', sensor_block, re.DOTALL)
        cond_match = re.search(r'<ConductivitySensor[^>]*SensorID="([^"]+)"[^>]*>(.*?)</ConductivitySensor>', sensor_block, re.DOTALL)
        pres_match = re.search(r'<PressureSensor[^>]*SensorID="([^"]+)"[^>]*>(.*?)</PressureSensor>', sensor_block, re.DOTALL)
        
        if temp_match:
            sensor_info = _parse_temperature_sensor(temp_match.group(2), channel)
            if sensor_info:
                sensors.append(sensor_info)
                
        elif cond_match:
            sensor_info = _parse_conductivity_sensor(cond_match.group(2), channel)
            if sensor_info:
                sensors.append(sensor_info)
                
        elif pres_match:
            sensor_info = _parse_pressure_sensor(pres_match.group(2), channel)
            if sensor_info:
                sensors.append(sensor_info)
    
    return {'sensors': sensors}


def _parse_temperature_sensor(sensor_xml: str, channel: str) -> Optional[Dict[str, Any]]:
    """Parse temperature sensor XML block."""
    # Extract basic info
    serial_match = re.search(r'<SerialNumber>([^<]+)</SerialNumber>', sensor_xml)
    cal_date_match = re.search(r'<CalibrationDate>([^<]+)</CalibrationDate>', sensor_xml)
    
    if not serial_match:
        return None
        
    serial_number = serial_match.group(1).strip()
    
    # Parse calibration date
    calibration_date = None
    if cal_date_match:
        cal_date_str = cal_date_match.group(1).strip()
        try:
            cal_date = datetime.strptime(cal_date_str, "%d-%b-%y")
            calibration_date = cal_date.strftime("%Y-%m-%d")
        except ValueError:
            try:
                cal_date = datetime.strptime(cal_date_str, "%d-%b-%Y")
                calibration_date = cal_date.strftime("%Y-%m-%d")
            except ValueError:
                calibration_date = cal_date_str
    
    # Extract calibration coefficients (G, H, I, J for SBE 3plus)
    coefficients = []
    for coeff in ['G', 'H', 'I', 'J', 'Slope', 'Offset']:
        coeff_match = re.search(f'<{coeff}>([^<]+)</{coeff}>', sensor_xml)
        if coeff_match:
            coefficients.append(f"{coeff}={coeff_match.group(1).strip()}")
    
    return {
        'sensor_type': 'Temperature',
        'serial_number': serial_number,
        'calibration_date': calibration_date,
        'channel': channel,
        'coefficients': ', '.join(coefficients) if coefficients else None,
        'sensor_model': 'Sea-Bird SBE 3plus temperature sensor',
        'sensor_model_vocabulary': 'https://vocab.nerc.ac.uk/collection/L22/current/TOOL0416/',
        'sensor_maker': 'Sea-Bird Scientific',
        'sensor_maker_vocabulary': 'http://vocab.nerc.ac.uk/collection/L35/current/MAN0013/',
        'sensor_type_vocabulary': 'http://vocab.nerc.ac.uk/collection/L05/current/134/'
    }


def _parse_conductivity_sensor(sensor_xml: str, channel: str) -> Optional[Dict[str, Any]]:
    """Parse conductivity sensor XML block."""
    # Extract basic info
    serial_match = re.search(r'<SerialNumber>([^<]+)</SerialNumber>', sensor_xml)
    cal_date_match = re.search(r'<CalibrationDate>([^<]+)</CalibrationDate>', sensor_xml)
    
    if not serial_match:
        return None
        
    serial_number = serial_match.group(1).strip()
    
    # Parse calibration date
    calibration_date = None
    if cal_date_match:
        cal_date_str = cal_date_match.group(1).strip()
        try:
            cal_date = datetime.strptime(cal_date_str, "%d-%b-%y")
            calibration_date = cal_date.strftime("%Y-%m-%d")
        except ValueError:
            try:
                cal_date = datetime.strptime(cal_date_str, "%d-%b-%Y")
                calibration_date = cal_date.strftime("%Y-%m-%d")
            except ValueError:
                calibration_date = cal_date_str
    
    # Extract calibration coefficients (G, H, I, J from equation 1, plus slope/offset)
    coefficients = []
    
    # Look for coefficients in equation="1" block (preferred for SBE 4C)
    eq1_match = re.search(r'<Coefficients equation="1"[^>]*>(.*?)</Coefficients>', sensor_xml, re.DOTALL)
    if eq1_match:
        eq1_block = eq1_match.group(1)
        for coeff in ['G', 'H', 'I', 'J', 'CPcor', 'CTcor', 'WBOTC']:
            coeff_match = re.search(f'<{coeff}>([^<]+)</{coeff}>', eq1_block)
            if coeff_match:
                coefficients.append(f"{coeff}={coeff_match.group(1).strip()}")
    
    # Add slope and offset from main block
    for coeff in ['Slope', 'Offset']:
        coeff_match = re.search(f'<{coeff}>([^<]+)</{coeff}>', sensor_xml)
        if coeff_match:
            coefficients.append(f"{coeff}={coeff_match.group(1).strip()}")
    
    return {
        'sensor_type': 'Conductivity',
        'serial_number': serial_number,
        'calibration_date': calibration_date,
        'channel': channel,
        'coefficients': ', '.join(coefficients) if coefficients else None,
        'sensor_model': 'Sea-Bird SBE 4C conductivity sensor',
        'sensor_model_vocabulary': 'https://vocab.nerc.ac.uk/collection/L22/current/TOOL0417/',
        'sensor_maker': 'Sea-Bird Scientific',
        'sensor_maker_vocabulary': 'http://vocab.nerc.ac.uk/collection/L35/current/MAN0013/',
        'sensor_type_vocabulary': 'http://vocab.nerc.ac.uk/collection/L05/current/133/'
    }


def _parse_pressure_sensor(sensor_xml: str, channel: str) -> Optional[Dict[str, Any]]:
    """Parse pressure sensor XML block."""
    # Extract basic info
    serial_match = re.search(r'<SerialNumber>([^<]+)</SerialNumber>', sensor_xml)
    cal_date_match = re.search(r'<CalibrationDate>([^<]+)</CalibrationDate>', sensor_xml)
    
    if not serial_match:
        return None
        
    serial_number = serial_match.group(1).strip()
    
    # Parse calibration date
    calibration_date = None
    if cal_date_match:
        cal_date_str = cal_date_match.group(1).strip()
        try:
            cal_date = datetime.strptime(cal_date_str, "%d-%b-%y")
            calibration_date = cal_date.strftime("%Y-%m-%d")
        except ValueError:
            try:
                cal_date = datetime.strptime(cal_date_str, "%d-%b-%Y")
                calibration_date = cal_date.strftime("%Y-%m-%d")
            except ValueError:
                calibration_date = cal_date_str
    
    # Check if this is a Digiquartz sensor (look for comment or specific coefficients)
    is_digiquartz = 'Digiquartz' in sensor_xml or re.search(r'<C1>.*</C1>', sensor_xml)
    
    # Extract calibration coefficients
    coefficients = []
    if is_digiquartz:
        # Digiquartz coefficients: C1, C2, C3, D1, D2, T1-T5, etc.
        for coeff in ['C1', 'C2', 'C3', 'D1', 'D2', 'T1', 'T2', 'T3', 'T4', 'T5', 'AD590M', 'AD590B', 'Slope', 'Offset']:
            coeff_match = re.search(f'<{coeff}>([^<]+)</{coeff}>', sensor_xml)
            if coeff_match:
                coefficients.append(f"{coeff}={coeff_match.group(1).strip()}")
    else:
        # Standard pressure sensor coefficients
        for coeff in ['PA0', 'PA1', 'PA2', 'PTCA0', 'PTCA1', 'PTCA2', 'PTCB0', 'PTCB1', 'PTCB2', 'PTEMPA0', 'PTEMPA1', 'PTEMPA2', 'POFFSET', 'PRANGE']:
            coeff_match = re.search(f'<{coeff}>([^<]+)</{coeff}>', sensor_xml)
            if coeff_match:
                coefficients.append(f"{coeff}={coeff_match.group(1).strip()}")
    
    # Determine sensor model and vocabulary based on type
    if is_digiquartz:
        sensor_model = 'Paroscientific Digiquartz depth sensor'
        sensor_model_vocab = 'https://vocab.nerc.ac.uk/collection/L22/current/TOOL0931/'
        sensor_maker = 'Paroscientific Inc.'
        sensor_maker_vocab = 'http://vocab.nerc.ac.uk/collection/L35/current/MAN0049/'
    else:
        sensor_model = 'Sea-Bird pressure sensor'
        sensor_model_vocab = 'http://vocab.nerc.ac.uk/collection/L22/current/TOOL0420/'
        sensor_maker = 'Sea-Bird Scientific'
        sensor_maker_vocab = 'http://vocab.nerc.ac.uk/collection/L35/current/MAN0013/'
    
    return {
        'sensor_type': 'Pressure',
        'serial_number': serial_number,
        'calibration_date': calibration_date,
        'channel': channel,
        'coefficients': ', '.join(coefficients) if coefficients else None,
        'sensor_model': sensor_model,
        'sensor_model_vocabulary': sensor_model_vocab,
        'sensor_maker': sensor_maker,
        'sensor_maker_vocabulary': sensor_maker_vocab,
        'sensor_type_vocabulary': 'http://vocab.nerc.ac.uk/collection/L05/current/138/'
    }


def get_sensor_model_info(parsed_metadata: Dict[str, Any]) -> Dict[str, str]:
    """
    Map SeaBird device information to NERC L22 sensor model vocabulary.
    
    Parameters
    ----------
    parsed_metadata : dict
        Parsed SeaBird metadata from parse_seabird_metadata()
        
    Returns
    -------
    dict
        Dictionary with 'sensor_model' and 'sensor_model_vocabulary' keys
    """
    device_type = parsed_metadata.get('device_type', '').upper()
    pump_installed = parsed_metadata.get('sbe_pump_installed', '').lower()
    
    # Check for pressure calibration coefficients
    has_pressure = any(key.startswith('Pressure_') and key.endswith('_calibration_coefficients') 
                      for key in parsed_metadata.keys())
    
    # Default fallback
    result = {
        'sensor_model': device_type,
        'sensor_model_vocabulary': None
    }
    
    # SeaBird SBE 37 series mapping
    if 'SBE37' in device_type or 'SBE 37' in device_type:
        
        # Determine if it's pumped
        is_pumped = pump_installed == 'yes'
        
        if is_pumped:
            if has_pressure:
                # SBE 37 MicroCat SMP-CTP (submersible) CTD sensor - pumped with pressure
                result['sensor_model'] = 'Sea-Bird SBE 37 MicroCat SMP-CTP (submersible) CTD sensor'
                result['sensor_model_vocabulary'] = 'https://vocab.nerc.ac.uk/collection/L22/current/TOOL1457/'
            else:
                # Pumped CT only - would need another NERC code if available
                result['sensor_model'] = 'Sea-Bird SBE 37 MicroCat (submersible) CT sensor series'
                result['sensor_model_vocabulary'] = None  # No specific pumped CT-only code provided
        else:
            # Not pumped
            if has_pressure:
                if 'IM' in device_type:
                    # SBE 37 MicroCat IM-CTP (submersible) CTD sensor
                    result['sensor_model'] = 'Sea-Bird SBE 37 MicroCat IM-CTP (submersible) CTD sensor'
                    result['sensor_model_vocabulary'] = 'https://vocab.nerc.ac.uk/collection/L22/current/TOOL1450/'
                elif 'RS232' in device_type or 'SM' in device_type:
                    # SBE 37 MicroCat CTP (submersible) CTD sensor series
                    result['sensor_model'] = 'Sea-Bird SBE 37 MicroCat CTP (submersible) CTD sensor series'
                    result['sensor_model_vocabulary'] = 'https://vocab.nerc.ac.uk/collection/L22/current/TOOL1393/'
                else:
                    # Generic CTP
                    result['sensor_model'] = 'Sea-Bird SBE 37 MicroCat CTP (submersible) CTD sensor series'
                    result['sensor_model_vocabulary'] = 'https://vocab.nerc.ac.uk/collection/L22/current/TOOL1393/'
            else:
                if 'IM' in device_type:
                    # SBE 37 MicroCat IM-CT with optional pressure
                    result['sensor_model'] = 'Sea-Bird SBE 37 MicroCat IM-CT with optional pressure (submersible) CTD sensor series'
                    result['sensor_model_vocabulary'] = 'https://vocab.nerc.ac.uk/collection/L22/current/TOOL0022/'
                else:
                    # SBE 37 MicroCat CT (submersible) CT sensor series
                    result['sensor_model'] = 'Sea-Bird SBE 37 MicroCat CT (submersible) CT sensor series'
                    result['sensor_model_vocabulary'] = 'https://vocab.nerc.ac.uk/collection/L22/current/TOOL1394/'
    
    # Could add other SeaBird models here (SBE9, SBE19, etc.)
    
    return result


def format_calibration_summary(raw_metadata: Union[str, Dict[str, Any]]) -> Dict[str, str]:
    """
    Format calibration information for display in reports.
    
    Parameters
    ----------
    raw_metadata : dict or str
        Raw metadata dictionary or JSON string from SeaBird CNV reader
        
    Returns
    -------
    dict
        Dictionary with formatted calibration summaries
    """
    parsed = parse_seabird_metadata(raw_metadata)
    formatted = {}
    
    # Add basic instrument info
    if 'device_type' in parsed:
        formatted['Instrument Model'] = parsed['device_type']
    if 'serial_number' in parsed:
        formatted['Serial Number'] = parsed['serial_number']
    if 'calibration_date' in parsed:
        formatted['Calibration Date'] = parsed['calibration_date']
    if 'sbe_pump_installed' in parsed:
        formatted['Pump Installed'] = parsed['sbe_pump_installed']
    
    # Add calibration coefficients with cleaner names
    for key, value in parsed.items():
        if key.endswith('_calibration_coefficients'):
            sensor_name = key.replace('_calibration_coefficients', '')
            formatted[f'{sensor_name} Calibration'] = value
    
    return formatted