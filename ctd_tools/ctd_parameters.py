
TEMPERATURE = 'temperature'
OXYGEN = 'oxygen'
PRESSURE = 'pressure'
SALINITY = 'salinity'
TURBIDITY = 'turbidity'
CONDUCTIVITY = 'conductivity'
DEPTH = 'depth'
DATE = 'date'
TIME = 'time'
LATITUDE = 'latitude'
LONGITUDE = 'longitude'
DENSITY = 'density'
POTENTIAL_TEMPERATURE = 'potential_temperature'
SPEED_OF_SOUND = 'speed_of_sound'
TIME_J = 'julian_days_offset'
TIME_Q = 'seconds_since_jan_1_2000'
TIME_N = 'timeN'
TIME_S = 'timeS'
POWER_SUPPLY_INPUT_VOLTAGE = 'power_supply_input'

# Meta data should use standardized values from https://cfconventions.org/
metadata = {
    TEMPERATURE: {
        'long_name': "Temperature",
        'units': "ITS-90, deg C",
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'sea_water_temperature',
        'short_name': "WT",
        'measurement_type': "Measured",
    },
    PRESSURE: {
        'long_name': "Pressure",
        'units': "dbar",
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'sea_water_pressure',
        'short_name': "WP",
        'measurement_type': "Measured",
    },
    CONDUCTIVITY: {
        'long_name': "Conductivity",
        'coverage_content_type': 'physicalMeasurement',
        'units': "S m-1",
        'standard_name': 'sea_water_electrical_conductivity',
        'short_name': "COND",
        'measurement_type': "Measured",
    },
    SALINITY: {
        'long_name': "Salinity",
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'sea_water_salinity',
        'short_name': 'SAL',
        'measurement_type': 'Derived', 
    },
    TURBIDITY: {
        'long_name': "Turbidity",
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'sea_water_turbidity',
        'measurement_type': "Measured",
        'short_name': "Tur", 
    }, 
    OXYGEN: {
        'long_name': "Oxygen",
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'volume_fraction_of_oxygen_in_sea_water'
    },
    DEPTH: {
        'long_name': 'Depth',
        'units': 'meters',
        'positive': 'up',
        'standard_name': 'depth',
        'coverage_content_type': 'coordinate',
        'short_name': "D",
    },
    DENSITY: {
        'long_name': 'Density',
        'units': 'kg m-3',
        'standard_name': 'sea_water_density',
        'measurement_type': 'Derived',
    },
    POTENTIAL_TEMPERATURE: {
        'long_name': 'Potential Temperature θ',
        'units': 'degC',
        'standard_name': 'sea_water_potential_temperature',
        'measurement_type': 'Derived',
    },
    SPEED_OF_SOUND: {
        'long_name': 'Speed of Sound',
        'units': 'm s-1',
        'standard_name': 'speed_of_sound_in_sea_water',
        'measurement_type': 'Derived',
    },
    LATITUDE: {
        'long_name': 'Latitude',
        'units': 'degrees_north',
        'standard_name': 'latitude',
        'coverage_content_type': 'coordinate',
        'short_name': "lat",
    },
    LONGITUDE: {
        'long_name': 'Longitude',
        'units': 'degrees_east',
        'standard_name': 'longitude',
        'coverage_content_type': 'coordinate',
        'short_name': "lon",
    },
    TIME: {
        'long_name': 'Time',
        'standard_name': 'time',
        'coverage_content_type': 'coordinate' 
    },
    POWER_SUPPLY_INPUT_VOLTAGE: {
        'long_name': 'Power supply input voltage',
        'units': 'V',
    }

}

default_mappings = {
    TEMPERATURE: [
        't090C', 't068', 'tv290C', 't190C', 'TEMP'
    ],
    SALINITY: [
        'sal00', 'sal11', 'PSAL2'
    ],
    CONDUCTIVITY: [
        'c0mS/cm', 'c0', 'c1mS/cm', 'c1', 'cond0mS/cm'
    ],
    PRESSURE: [
        'prdM', 'prDM', 'pr', 'PRES'
    ],
    TURBIDITY: [
        'turbWETntu0'
    ],
    DEPTH: [
        'depSM'
    ],
    TIME_J: [
        'timeJ', 'timeJV2', 'timeSCP'
    ],
    TIME_Q: [
        'timeQ', 'timeK'
    ],
    TIME_N: [
        'timeN'
    ],
    TIME_S: [
        'timeS'
    ],
    OXYGEN: [
        'oxsatMm/Kg', 'oxsolMm/Kg', 'sbeox0', 'sbeox1'
    ],
    LATITUDE: [
        'latitude', 'LONGITUDE'
    ], 
    LONGITUDE: [
        'longitude', 'LATITUDE'
    ],
    POWER_SUPPLY_INPUT_VOLTAGE: {
        'Vbatt', 'Vcharge', 'Vmote'
    }
}

def allowed_parameters():
    return {
        TEMPERATURE: 'Temperature in degrees Celsius',
        SALINITY: 'Salinity in PSU',
        CONDUCTIVITY: 'Conductivity in S/m',
        PRESSURE: 'Pressure in Dbar',
        OXYGEN: 'Oxygen in micromoles/kg',
        TURBIDITY: 'Turbidity in NTU',
        DEPTH: 'Depth in meters',
        DATE: 'Date of the measurement'
    }