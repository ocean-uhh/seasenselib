"""
Sorting logic.

Sorts variables and coordinates based on a canonical order for consistent output presentation.
"""

from ...base import StageContext
from .... import parameters as params


# Define canonical sort order using parameter constants
# Each parameter from parameters.py is included exactly once
var_sort_order = [
    # Measured varaiables
    params.TEMPERATURE,
    params.CONDUCTIVITY,
    params.PRESSURE,
    params.OXYGEN,
    params.CHLOROPHYLL,
    params.FLUORESCENCE,
    params.TURBIDITY,
    params.EAST_VELOCITY,
    params.NORTH_VELOCITY,
    params.UP_VELOCITY,
    params.EAST_AMPLITUDE,
    params.NORTH_AMPLITUDE,
    params.UP_AMPLITUDE,
    params.DIRECTION,
    params.MAGNITUDE,

    # Measured engineering
    params.ECHO_INTENSITY,
    params.CORRELATION,
    params.PITCH,
    params.ROLL,
    params.HEADING,
    params.BATTERY_VOLTAGE,
    params.ALTIMETER,
    params.POWER_SUPPLY_INPUT_VOLTAGE,

    # Derived variables
    params.DEPTH,
    params.DENSITY,
    params.POTENTIAL_TEMPERATURE,
    params.SALINITY,
    params.CONSERVATIVE_TEMPERATURE,
    params.ABSOLUTE_SALINITY,
    params.SPEED_OF_SOUND,
    params.SOUNDSPEED,  # Note: this duplicates SPEED_OF_SOUND but keeping both

    # Coordinates variables
    params.DATE,
    params.TIME,
    params.LATITUDE,
    params.LONGITUDE,
    params.TIME_J,
    params.TIME_Q,
    params.TIME_N,
    params.TIME_S,
    'flag',  # No constant for flag in parameters.py
]

attr_sort_order = [
    # Dataset identification
    "title",
    "summary",
    "description",
    "program",
    "project",
    "source",
    "id",
    "naming_authority",
    # Legal and licensing
    "license",
    "acknowledgment",
    "citation",
    "doi",
    "uri",
    "references",
    "weblink",
    "distribution_statement",
    # Platform and methodology
    "platform",
    "platform_type",
    "platform_vocabulary",
    "platform_code",
    "wmo_platform_code",
    "data_product",
    # Site and network
    "site",
    "site_code",
    "site_vocabulary",
    "array",
    "network",
    "program_vocabulary",
    "internal_mission_identifier",
    # Geospatial and temporal coverage
    "start_date",
    "time_coverage_start",
    "time_coverage_end",
    "time_coverage_duration",
    "time_coverage_resolution",
    "geospatial_lat_min",
    "geospatial_lat_max",
    "geospatial_lon_min",
    "geospatial_lon_max",
    "geospatial_vertical_min",
    "geospatial_vertical_max",
    "geospatial_vertical_positive",
    "sea_name",
    # Contributors and attribution
    "creator_name",
    "creator_email",
    "creator_url",
    "creator_institution",
    "contributor_name",
    "contributor_role",
    "contributor_role_vocabulary",
    "contributor_url",
    "contributor_email",
    "contributor_id",
    "contributor_institution",
    "contributing_institutions",
    "contributing_institutions_vocabulary",
    "contributing_institutions_role",
    "contributing_institutions_role_vocabulary",
    "institution",
    "publisher_name",
    "publisher_email",
    "publisher_url",
    "publisher_institution",
    "publisher_type",
    # Technical metadata
    "Conventions",  # preserve exact case
    "CF_version",
    "ACDD_version",
    "standard_name_vocabulary",
    "ncei_template_version",
    "featureType",  # preserve exact case
    "featureType_vocabulary",
    "cdm_data_type",
    "data_type",
    # Data provenance
    "source_file",
    "source_path",
    "source_url",
    "date_created",
    "date_modified",
    "history",
    "product_version",
    "format_version",
    "variable_mapping",
    "original_variable_metadata",
    "applied_variable_mapping",
    # Keywords and quality control
    "keywords",
    "keywords_vocabulary",
    "rtqc_method",
    "rtqc_method_doi",
    # Links
    "data_url",
    # Other
    "uuid",
    "update_interval",  # OceanSITES-1.5: use VOID if not regular
    "comment",

    "raw",
    "processor"
]

class Sorting:
    """
    Sort variables and coordinates in the dataset by canonical order.
    
    This is a cosmetic step that ensures consistent variable ordering
    in the output. Variables are sorted by their prefix according to
    the canonical order, and within each prefix group alphabetically.
    
    This step should typically run last since it
    only affects presentation, not data content.
    """
    
    def process(self, context: StageContext) -> StageContext:
        """
        Sort all variables and coordinates by canonical order.
        
        Parameters
        ----------
        context : StageContext
            The processing context.
        
        Returns
        -------
        StageContext
            Updated context with sorted dataset.
        """
        ds = context.dataset
        
        # Get all variable and coordinate names
        all_names = list(ds.data_vars) + list(ds.coords)
        
        def get_sort_key(name):
            """Get sort key for a variable name based on prefix and suffix."""
            # Check for sensor variables first (should come last)
            if name.startswith('SENSOR_'):
                return (1000, name)  # Large number to sort sensor variables last
            
            # Find matching prefix from var_sort_order
            for i, prefix in enumerate(var_sort_order):
                if name.startswith(prefix):
                    return (i, name)  # Use position in sort_order, then alphabetical
            
            # If no prefix match, sort alphabetically at the end (but before sensors)
            return (999, name)
        
        # Sort using the custom key
        sorted_names = sorted(all_names, key=get_sort_key)
        
        # Create new dataset with sorted order
        ds_sorted = ds[sorted_names]
        
        # Sort global attributes using canonical order
        original_attr_list = list(ds.attrs.items())
        matched_attrs = []
        unmatched_attrs = []
        
        for attr_name, attr_value in original_attr_list:
            matched = False
            
            # Check for exact match in attr_sort_order
            if attr_name in attr_sort_order:
                matched_attrs.append((attr_sort_order.index(attr_name), attr_name, attr_value))
                matched = True
            else:
                # Handle prefixed attributes (raw*, processor*, etc.)
                for i, canonical_attr in enumerate(attr_sort_order):
                    if canonical_attr.endswith('*'):
                        # Remove the * to get the prefix
                        prefix = canonical_attr[:-1]
                        if attr_name.startswith(prefix):
                            # Sort alphabetically within this prefix group
                            matched_attrs.append((i, attr_name, attr_value))
                            matched = True
                            break
            
            # If no match found, keep in original order at the end
            if not matched:
                unmatched_attrs.append((attr_name, attr_value))
        
        # Sort matched attributes by their canonical position and name
        sorted_matched = sorted(matched_attrs, key=lambda x: (x[0], x[1]))
        
        # Combine sorted matched attributes with unmatched in original order
        final_attrs = [(name, value) for _, name, value in sorted_matched] + unmatched_attrs
        ds_sorted.attrs = dict(final_attrs)
        
        context.dataset = ds_sorted
        
        return context
