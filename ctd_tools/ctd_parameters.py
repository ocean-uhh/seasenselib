
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
TIME_J = 'julian_days_offset'

metadata = {
    TEMPERATURE: {
        'long_name': "Sea Water Temperature",
        'units': "ITS-90, deg C",
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'sea_water_temperature',
        'short_name': "WT",
        'measurement_type': "Measured",
    },
    PRESSURE: {
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'sea_water_pressure',
        'short_name': "WP",
        'measurement_type': "Measured",
    },
    CONDUCTIVITY: {
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'sea_water_electrical_conductivity',
        'short_name': "COND",
        'measurement_type': "Measured",
    },
    SALINITY: {
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'sea_water_salinity',
        'short_name': 'SAL',
        'measurement_type': 'Derived', 
    },
    CONDUCTIVITY: {
        'coverage_content_type': 'physicalMeasurement',
        'standard_name': 'sea_water_turbidity',
        'measurement_type': "Measured",
        'short_name': "Tur", 
    }, 
    OXYGEN: {
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
    }

}

default_mappings = {
    TEMPERATURE: [
        't090C', 't068', 'tv290C'
    ],
    SALINITY: [
        'sal00'
    ],
    CONDUCTIVITY: [
        'c0mS/cm', 'c0', 'c1mS/cm', 'c1', 'cond0mS/cm'
    ],
    PRESSURE: [
        'prdM', 'prDM', 'pr'
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
    OXYGEN: [
        'oxsatMm/Kg', 'oxsolMm/Kg', 'sbeox0', 'sbeox1'
    ]
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