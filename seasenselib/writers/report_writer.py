"""
Module for generating comprehensive dataset reports in RST format.

This module provides the ReportWriter class for generating detailed reports
that document variable mappings, metadata changes, and processing pipelines
applied to oceanographic datasets.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
from pathlib import Path
import logging
import numpy as np
import pandas as pd
import xarray as xr

from .base import AbstractWriter

logger = logging.getLogger(__name__)


class ReportWriter(AbstractWriter):
    """
    Writer for generating comprehensive dataset reports in RST format.
    
    Creates detailed reports that document:
    - Variable mappings (original → standardized names)
    - Variable attributes and statistics
    - Coordinate information
    - Metadata changes from pipeline processing
    - Processing protocol and stages applied
    - Optional dataset visualizations
    
    Examples
    --------
    >>> import seasenselib as ssl
    >>> data = ssl.read('profile.cnv', pipeline_profile='default')
    >>> ssl.write(data, 'profile_report.rst', file_format='report')
    
    >>> # Or with direct instantiation
    >>> from seasenselib.writers import ReportWriter
    >>> writer = ReportWriter(data)
    >>> writer.write('profile_report.rst', title='CTD Profile Report')
    """

    @staticmethod
    def format_key() -> str:
        """Return the format key for this writer."""
        return "report"

    @staticmethod
    def format_name() -> str:
        """Return the human-readable format name."""
        return "Dataset Report (RST)"

    @staticmethod
    def file_extension() -> str:
        """Return the default file extension."""
        return ".rst"

    def write(self, file_name: str, title: Optional[str] = None, 
              include_plot: bool = True, plot_output_dir: Optional[str] = None,
              processing_metadata: Optional[Dict[str, Any]] = None,
              **kwargs) -> None:
        """
        Write dataset report to RST file.
        
        Parameters
        ----------
        file_name : str
            Output RST file path
        title : str, optional
            Report title. If None, uses source file name or generic title.
        include_plot : bool, default=True
            Whether to generate and include a plot in the report
        plot_output_dir : str, optional
            Directory for plot files. If None, uses docs/source/_static/reports/.
        processing_metadata : dict, optional
            Processing metadata containing variable mappings and pipeline info.
            If None, attempts to extract from dataset attributes.
        **kwargs
            Additional formatting options
        """
        try:
            # Store processing metadata for use in report generation
            self._processing_metadata = processing_metadata
            
            # Generate the RST content
            rst_content = self._generate_rst_report(
                title=title, 
                include_plot=include_plot,
                plot_output_dir=plot_output_dir,
                **kwargs
            )
            
            # Ensure output directory exists
            output_path = Path(file_name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the report
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rst_content)
            
            logger.info(f"Report written to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to write report: {e}")
            raise

    def _generate_rst_report(self, title: Optional[str] = None,
                            include_plot: bool = False,
                            plot_output_dir: Optional[str] = None,
                            **kwargs) -> str:
        """Generate the RST report content."""
        
        # Determine report title
        if title is None:
            source_file = self.data.attrs.get('source_file', 'Dataset')
            if source_file != 'Dataset':
                title = Path(source_file).stem + ' Report'
            else:
                title = 'SeaSenseLib Dataset Report'
        
        # Compute statistics
        statistics = self._compute_statistics()
        
        # Extract pipeline metadata
        pipeline_info = self._extract_pipeline_info()
        
        # Build RST content
        lines = []
        
        # Title and header
        title_line = title
        lines.extend([
            title_line,
            '=' * len(title_line),
            '',
            f'*Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC*',
            '',
        ])
        
        # Dataset overview
        lines.extend(self._generate_overview_section(statistics, pipeline_info))
        
        # Optional plot
        if include_plot:
            logger.info(f"Generating plot section with plot_output_dir={plot_output_dir}")
            plot_section = self._generate_plot_section(plot_output_dir, pipeline_info)
            logger.info(f"Plot section result: {True if plot_section else False}, length: {len(plot_section) if plot_section else 0}")
            if plot_section:
                lines.extend(plot_section)
            else:
                logger.warning("Plot section generation returned None or empty")

        # Coordinate information  
        lines.extend(self._generate_coordinate_section(statistics))

        # Variable information
        lines.extend(self._generate_variable_section(statistics, pipeline_info))

        # Sensor variables information
        lines.extend(self._generate_sensor_variables_section())
                
        # Processing protocol
        lines.extend(self._generate_processing_section(pipeline_info))
        
        # Metadata section
        lines.extend(self._generate_metadata_section(pipeline_info))
        

        
        return '\n'.join(lines)

    def _compute_statistics(self) -> Dict[str, Any]:
        """Compute comprehensive dataset statistics."""
        stats = {
            'total_variables': len(self.data.data_vars),
            'total_coordinates': len(self.data.coords),
            'total_attributes': len(self.data.attrs),
            'file_size_mb': self.data.nbytes / (1024 * 1024),
            'variables': {},
            'coordinates': {}
        }
        
        # Variable statistics
        for var_name, var in self.data.data_vars.items():
            var_stats = {
                'dtype': str(var.dtype),
                'shape': var.shape,
                'dimensions': list(var.dims),
                'units': var.attrs.get('units', 'unknown'),
                'long_name': var.attrs.get('long_name', var_name),
                'missing_data_pct': 0.0
            }
            
            # Numeric statistics
            if np.issubdtype(var.dtype, np.number):
                valid_data = var.where(np.isfinite(var), drop=True)
                if valid_data.size > 0:
                    var_stats.update({
                        'min': float(valid_data.min().values),
                        'max': float(valid_data.max().values),
                        'mean': float(valid_data.mean().values),
                        'std': float(valid_data.std().values)
                    })
                    # Missing data percentage
                    var_stats['missing_data_pct'] = ((var.size - valid_data.size) / var.size) * 100
            
            stats['variables'][var_name] = var_stats
        
        # Coordinate statistics
        for coord_name, coord in self.data.coords.items():
            coord_stats = {
                'dtype': str(coord.dtype),
                'shape': coord.shape,
                'dimensions': list(coord.dims),
                'units': coord.attrs.get('units', 'unknown'),
                'long_name': coord.attrs.get('long_name', coord_name)
            }
            
            if np.issubdtype(coord.dtype, np.number):
                valid_data = coord.where(np.isfinite(coord), drop=True)
                if valid_data.size > 0:
                    coord_stats.update({
                        'min': float(valid_data.min().values),
                        'max': float(valid_data.max().values)
                    })
            elif coord.dtype.kind == 'M':  # Datetime
                coord_stats.update({
                    'min': str(coord.min().values)[:19],
                    'max': str(coord.max().values)[:19]
                })
            
            stats['coordinates'][coord_name] = coord_stats
        
        return stats

    def _extract_pipeline_info(self) -> Dict[str, Any]:
        """Extract pipeline processing information from dataset metadata."""
        # First try processing metadata passed to write(), then fall back to dataset attrs
        if hasattr(self, '_processing_metadata') and self._processing_metadata:
            metadata = self._processing_metadata
            return {
                'variable_mappings': metadata.get('variable_mappings', {}),
                'stages_applied': metadata.get('stages_applied', []),
                'handlers_applied': metadata.get('handlers_applied', []),
                'derived_parameters': metadata.get('derived_parameters', []),
                'unit_conversions': metadata.get('unit_conversions', {}),
                'source_file': metadata.get('source_file'),
                'reader_class': metadata.get('reader_class'),
                'format_name': metadata.get('format_name')
            }
        else:
            # Fallback to dataset attributes
            return {
                'variable_mappings': self.data.attrs.get('applied_variable_mapping', {}),
                'stages_applied': self.data.attrs.get('stages_applied', []),
                'handlers_applied': self.data.attrs.get('handlers_applied', []),
                'derived_parameters': self.data.attrs.get('derived_parameters', []),
                'unit_conversions': self.data.attrs.get('unit_conversions', {}),
                'source_file': self.data.attrs.get('source_file'),
                'reader_class': self.data.attrs.get('reader_class'),
                'format_name': self.data.attrs.get('format_name')
            }

    def _generate_overview_section(self, statistics: Dict[str, Any], 
                                  pipeline_info: Dict[str, Any]) -> List[str]:
        """Generate dataset overview section."""
        lines = [
            'Dataset Overview',
            '^' * 16,
            ''
        ]
        
        # Basic information
        if pipeline_info['source_file']:
            lines.append(f"- **Source File**: {pipeline_info['source_file']}")
        if pipeline_info['format_name']:
            lines.append(f"- **Original Format**: {pipeline_info['format_name']}")
        if pipeline_info['reader_class']:
            lines.append(f"- **Reader**: {pipeline_info['reader_class'].split('.')[-1]}")
        
        lines.extend([
            f"- **Total Variables**: {statistics['total_variables']}",
            f"- **Total Coordinates**: {statistics['total_coordinates']}",
            f"- **Dataset Size**: {statistics['file_size_mb']:.2f} MB",
            ''
        ])
        
        # Temporal information
        temporal_info = self._analyze_temporal_coverage()
        if temporal_info.get('has_time'):
            lines.append(f"- **Time Coverage**: {temporal_info.get('start_date', 'Unknown')} to {temporal_info.get('end_date', 'Unknown')}")
            if 'total_records' in temporal_info:
                lines.append(f"- **Record Length**: {temporal_info['total_records']:,} observations")
            if 'estimated_frequency' in temporal_info:
                lines.append(f"- **Sampling Frequency**: {temporal_info['estimated_frequency']}")
        
        lines.append('')
        return lines

    def _generate_variable_section(self, statistics: Dict[str, Any],
                                  pipeline_info: Dict[str, Any]) -> List[str]:
        """Generate variable information section with mapping table."""
        lines = [
            'Variable Information',
            '^' * 20,
            '',
            'The following table shows variable mappings from original to standardized names,',
            'along with key statistics for each variable.',
            ''
        ]
        
        # Create variable mapping table
        var_data = []
        variable_mappings = pipeline_info['variable_mappings']
        
        # Create reverse mapping for display
        reverse_mapping = {}
        for orig, std in variable_mappings.items():
            if orig != std:  # Only show actual renames
                reverse_mapping[std] = orig
        
        for var_name in self.data.data_vars: # Do we want to sort this?
            # Skip sensor variables - they go in their own section
            if var_name.startswith('SENSOR_'):
                continue
                
            var_stats = statistics['variables'][var_name]
            
            # Format display name
            if var_name in reverse_mapping:
                display_name = f"*{reverse_mapping[var_name]}* → **{var_name}**"
            else:
                display_name = f"**{var_name}**"
            
            # Format description
            long_name = var_stats['long_name']
            description = self.data[var_name].attrs.get('description', '')
            
            # Check if this variable has a linked sensor (for measured variables only)
            sensor_link = self.data[var_name].attrs.get('sensor', '')
            sensor_suffix = ""
            if sensor_link:
                # Only add sensor info for original measured variables (not derived ones)
                measurement_type = self.data[var_name].attrs.get('measurement_type', '')
                if measurement_type == 'Measured':
                    sensor_suffix = f" ({sensor_link})"
            
            if description and description != long_name:
                display_description = f"**{long_name}**: {description}{sensor_suffix}"
            else:
                display_description = f"{long_name}{sensor_suffix}"
            
            # Min/max values
            min_val = var_stats.get('min', 'N/A')
            max_val = var_stats.get('max', 'N/A')
            if isinstance(min_val, float):
                min_val = f"{min_val:.3f}"
            if isinstance(max_val, float):
                max_val = f"{max_val:.3f}"
            
            var_data.append({
                'Variable': display_name,
                'Description': display_description,
                'Units': var_stats['units'],
                'Shape': str(var_stats['shape']),
                'Min Value': min_val,
                'Max Value': max_val,
                'Missing %': f"{var_stats['missing_data_pct']:.1f}%"
            })
        
        # Convert to RST table
        if var_data:
            df = pd.DataFrame(var_data)
            lines.extend(self._dataframe_to_rst_table(df))
        else:
            lines.append('No variables available.')
        
        lines.append('')
        return lines

    def _generate_sensor_variables_section(self) -> List[str]:
        """Generate sensor variables section with metadata table."""
        lines = [
            'Sensor Variables',
            '^' * 16,
            '',
            'The following table shows sensor metadata variables that contain',
            'instrument information and calibration details.',
            ''
        ]
        
        # Find all sensor variables
        sensor_vars = [var_name for var_name in sorted(self.data.data_vars) 
                      if var_name.startswith('SENSOR_')]
        
        if not sensor_vars:
            lines.extend(['No sensor variables found.', ''])
            return lines
        
        # Create sensor variable table data
        sensor_data = []
        for var_name in sensor_vars:
            var = self.data[var_name]
            attrs = var.attrs
            
            # Extract information with fallbacks
            serial_number = attrs.get('sensor_serial_number', 'N/A')
            calib_date = attrs.get('sensor_calibration_date', 'N/A')
            if calib_date != 'N/A' and calib_date.endswith('T00:00:00Z'):
                # Format date more cleanly
                calib_date = calib_date[:10]  # Just the date part
            
            # Combine details into bulleted list
            details_entries = []
            
            # Add long_name if present
            long_name = attrs.get('long_name', '')
            if long_name:
                details_entries.append(f"long_name = {long_name}")
            
            # Add sensor_model if present
            sensor_model = attrs.get('sensor_model', '')
            if sensor_model:
                details_entries.append(f"sensor_model = {sensor_model}")
            
            # Add sensor_maker if present
            sensor_maker = attrs.get('sensor_maker', '')
            if sensor_maker:
                details_entries.append(f"sensor_maker = {sensor_maker}")
            
            # Add serial number and calibration date  
            if serial_number != 'N/A':
                details_entries.append(f"serial_number = {serial_number}")
            if calib_date != 'N/A':
                details_entries.append(f"calibration_date = {calib_date}")
            
            # Add channel information if available
            sensor_channel = attrs.get('sensor_channel', '')
            if sensor_channel:
                details_entries.append(f"channel = {sensor_channel}")
            
            # Format as RST bulleted list for table cell
            if details_entries:
                formatted_details = []
                for i, entry in enumerate(details_entries):
                    if i == 0:
                        formatted_details.append(f"- {entry}")
                    else:
                        # Subsequent lines need 7 spaces for proper RST table cell alignment
                        formatted_details.append(f"       - {entry}")
                details_display = "\n".join(formatted_details)
            else:
                details_display = 'N/A'
            
            # Extract all three vocabulary URIs
            vocab_entries = []
            
            # Sensor type vocabulary
            sensor_type_vocab = attrs.get('sensor_type_vocabulary', '')
            if sensor_type_vocab:
                vocab_entries.append(f"• **Type**: {sensor_type_vocab}")
            
            # Sensor model vocabulary
            sensor_model_vocab = attrs.get('sensor_model_vocabulary', '')
            if sensor_model_vocab:
                vocab_entries.append(f"• **Model**: {sensor_model_vocab}")
                
            # Sensor maker vocabulary
            sensor_maker_vocab = attrs.get('sensor_maker_vocabulary', '')
            if sensor_maker_vocab:
                vocab_entries.append(f"• **Maker**: {sensor_maker_vocab}")
            
            # Format as RST nested list for table cell - proper table cell indentation
            if vocab_entries:
                formatted_vocabs = []
                for i, vocab in enumerate(vocab_entries):
                    clean_vocab = vocab.replace('• ', '')
                    if i == 0:
                        # First item starts with "- "
                        formatted_vocabs.append(f"- {clean_vocab}")
                    else:
                        # Subsequent lines need 7 spaces for proper RST table cell alignment
                        formatted_vocabs.append(f"       - {clean_vocab}")
                vocab_display = "\n".join(formatted_vocabs)
            else:
                vocab_display = 'N/A'
            
            # Extract calibration coefficients
            calib_coeffs = []
            for attr_name, attr_value in attrs.items():
                if attr_name.endswith('_calibration_coefficients'):
                    # Extract sensor type from attribute name
                    sensor_type = attr_name.replace('_calibration_coefficients', '')
                    
                    # Keep full coefficient strings for display
                    calib_coeffs.append(f"• **{sensor_type}**: {attr_value}")
            
            # Format calibration coefficients as bulleted list or N/A
            if calib_coeffs:
                # Format as RST nested list for table cell - proper table cell indentation
                formatted_coeffs = []
                for i, coeff in enumerate(calib_coeffs):
                    clean_coeff = coeff.replace('• ', '')
                    if i == 0:
                        # First item: "- **Sensor**: coeffs"
                        formatted_coeffs.append(f"- {clean_coeff}")
                    else:
                        # Subsequent lines need 7 spaces for proper RST table cell alignment
                        formatted_coeffs.append(f"       - {clean_coeff}")
                calib_display = "\n".join(formatted_coeffs)
            else:
                calib_display = 'N/A'
            
            sensor_data.append({
                'Variable': f"**{var_name}**",
                'Details': details_display,
                'Vocabulary': vocab_display,
                'Calibration Coefficients': calib_display
            })
        
        # Convert to RST table
        if sensor_data:
            df = pd.DataFrame(sensor_data)
            lines.extend(self._dataframe_to_rst_table(df))
        
        lines.append('')
        return lines

    def _generate_coordinate_section(self, statistics: Dict[str, Any]) -> List[str]:
        """Generate coordinate information section."""
        lines = [
            'Coordinate Information',
            '^' * 22,
            '',
            'The following table shows information about dataset coordinates:',
            ''
        ]
        
        coord_data = []
        for coord_name in sorted(self.data.coords):
            coord_stats = statistics['coordinates'][coord_name]
            coord_var = self.data[coord_name]
            
            # Format min/max values
            min_val = coord_stats.get('min', 'N/A')
            max_val = coord_stats.get('max', 'N/A')
            
            coord_data.append({
                'Coordinate': f"**{coord_name}**",
                'Description': coord_stats['long_name'],
                'Units': coord_stats['units'],
                'Shape': str(coord_stats['shape']),
                'Min Value': str(min_val),
                'Max Value': str(max_val)
            })
        
        if coord_data:
            df = pd.DataFrame(coord_data)
            lines.extend(self._dataframe_to_rst_table(df))
        else:
            lines.append('No coordinates available.')
        
        lines.append('')
        return lines

    def _generate_processing_section(self, pipeline_info: Dict[str, Any]) -> List[str]:
        """Generate processing protocol section."""
        lines = [
            'Processing Protocol',
            '^' * 18,
            '',
            'This section documents the processing pipeline applied to transform the raw data.',
            ''
        ]
        
        # Stages applied
        stages = pipeline_info.get('stages_applied', [])
        if stages:
            lines.extend([
                '**Pipeline Stages Applied:**',
                ''
            ])
            for i, stage in enumerate(stages, 1):
                lines.append(f'{i}. {stage}')
            lines.append('')
        
        # Handlers applied
        handlers = pipeline_info.get('handlers_applied', [])
        if handlers:
            lines.extend([
                '**Handlers Applied:**',
                ''
            ])
            for handler in handlers:
                lines.append(f'- {handler}')
            lines.append('')
        
        # Variable mappings
        mappings = pipeline_info.get('variable_mappings', {})
        actual_mappings = {orig: std for orig, std in mappings.items() if orig != std}
        if actual_mappings:
            lines.extend([
                '**Variable Name Mappings:**',
                ''
            ])
            for orig, std in sorted(actual_mappings.items()):
                lines.append(f'- ``{orig}`` → ``{std}``')
            lines.append('')
        
        # Derived parameters
        derived = pipeline_info.get('derived_parameters', [])
        if derived:
            lines.extend([
                '**Derived Parameters:**',
                ''
            ])
            for param in derived:
                lines.append(f'- {param}')
            lines.append('')
        
        # Unit conversions (handle both dict and list formats)
        unit_conversions = pipeline_info.get('unit_conversions', [])
        if unit_conversions:
            lines.extend([
                '**Unit Conversions:**',
                ''
            ])
            if isinstance(unit_conversions, list):
                for conversion in unit_conversions:
                    lines.append(f'- {conversion}')
            elif isinstance(unit_conversions, dict):
                for var, conversion in unit_conversions.items():
                    lines.append(f'- ``{var}``: {conversion}')
            lines.append('')
        
        return lines

    def _generate_metadata_section(self, pipeline_info: Dict[str, Any]) -> List[str]:
        """Generate metadata section."""
        lines = [
            'Global Metadata',
            '^' * 15,
            '',
            'Complete dataset metadata with processing annotations:',
            ''
        ]
        
        # Sort metadata for consistent output
        metadata = dict(self.data.attrs)
        excluded_keys = {
            'applied_variable_mapping', 'stages_applied', 'handlers_applied',
            'derived_parameters', 'unit_conversions'  # Already shown in processing section
        }
        excluded_keys = {}
        
        # Preserve the order from the dataset (which has been sorted canonically)
        for key in metadata.keys():
            if key not in excluded_keys:
                value = metadata[key]
                formatted_key = key.replace('_', ' ').title()
                
                # Handle different value types
                if isinstance(value, (list, tuple)):
                    value_str = ', '.join(map(str, value))
                    if len(value_str) > 500:
                        value_str = f'[List with {len(value)} items, truncated]'
                elif isinstance(value, dict):
                    # For dictionaries, provide a summary if too long
                    if key.lower() == 'raw_metadata' or len(str(value)) > 500:
                        # Try to provide useful summary for raw_metadata
                        if isinstance(value, dict):
                            num_keys = len(value.keys())
                            # Try to extract useful info from raw metadata
                            schema = value.get('schema', 'unknown')
                            blocks = value.get('blocks', {})
                            if blocks:
                                block_names = list(blocks.keys())
                                value_str = f'[Raw metadata: schema={schema}, blocks={block_names}]'
                            else:
                                value_str = f'[Complex metadata structure with {num_keys} top-level keys]'
                        else:
                            value_str = f'[Complex structure - {len(value)} items]'
                    else:
                        value_str = str(value)
                else:
                    value_str = str(value)
                    # Truncate very long strings (like embedded raw metadata)
                    if len(value_str) > 500:
                        # Try to extract meaningful preview
                        if 'Sea-Bird' in value_str[:100] or 'CTD' in value_str[:100]:
                            value_str = f'[CTD instrument metadata, {len(value_str):,} characters]'
                        elif '{' in value_str[:10] and '}' in value_str[-10:]:
                            # Likely JSON
                            try:
                                import json
                                data = json.loads(value_str)
                                if isinstance(data, dict):
                                    keys = list(data.keys())[:5]
                                    value_str = f'[JSON structure with keys: {keys}...]'
                                    value_str = str(value)
                                else:
                                    value_str = f'[JSON data, {len(value_str):,} characters]'
                            except:
                                value_str = f'[Complex data structure, {len(value_str):,} characters]'
                        else:
                            # Generic long string
                            preview = value_str[:100].replace('\n', ' ')
                            value_str = f'{preview}... [{len(value_str):,} total characters]'
                
                lines.append(f'- **{formatted_key}**: {value_str}')
        
        lines.append('')
        return lines

    def _generate_plot_section(self, plot_output_dir: Optional[str], pipeline_info: Optional[Dict[str, Any]] = None) -> Optional[List[str]]:
        """Generate optional plot section using SeaSenseLib plotters."""
        try:
            logger.info(f"_generate_plot_section called with plot_output_dir={plot_output_dir}")
            # Determine plot output directory
            if plot_output_dir is None:
                logger.warning("No plot_output_dir specified, skipping plot generation")
                return None
            else:
                plot_dir = Path(plot_output_dir)
                logger.info(f"Using plot_dir={plot_dir}")
            
            plot_dir.mkdir(parents=True, exist_ok=True)
            
            # Import SeaSenseLib plotters
            from seasenselib.plotters.time_series_plotter import TimeSeriesPlotter
            from seasenselib.plotters.depth_profile_plotter import DepthProfilePlotter
            import seasenselib.parameters as params
            logger.info("Successfully imported plotters")
            
            # Find suitable variables for plotting
            time_coords = [c for c in self.data.coords if 'time' in c.lower()]
            logger.info(f"Found time coordinates: {time_coords}")
            if not time_coords:
                logger.warning("No time coordinates found for plotting")
                return None
            
            # Find numeric variables with time dimension
            plottable_vars = []
            for var_name, var in self.data.data_vars.items():
                if (time_coords[0] in var.dims and 
                    np.issubdtype(var.dtype, np.number) and
                    'flag' not in var_name.lower()):
                    plottable_vars.append(var_name)
            
            if not plottable_vars:
                return None
            
            # Analyze temporal coverage to determine plot type
            temporal_info = self._analyze_temporal_coverage()
            estimated_freq = temporal_info.get('estimated_frequency', '60min')
            
            # Extract minutes from frequency string (e.g., "5min" -> 5, "1H" -> 60)
            sampling_freq_minutes = self._parse_frequency_to_minutes(estimated_freq)
            
            # Check if this is SbeCnvReader data
            if pipeline_info:
                reader_class = pipeline_info.get('reader_class', '')
            else:
                reader_class = self.data.attrs.get('reader_class', '')
            is_sbe_cnv = 'SbeCnvReader' in reader_class
            logger.info(f"reader_class={reader_class}, is_sbe_cnv={is_sbe_cnv}")
            
            # PLOT TYPE SELECTION LOGIC
            # Check if this is a MicroCat sensor (SBE 37 series)
            is_microcat = False
            
            # Check sensor variables for SBE 37 model indicators
            sensor_vars = [var_name for var_name in self.data.data_vars if var_name.startswith('SENSOR_')]
            for sensor_var in sensor_vars:
                sensor_attrs = self.data[sensor_var].attrs
                sensor_model = sensor_attrs.get('sensor_model', '')
                long_name = sensor_attrs.get('long_name', '')
                if 'SBE 37' in sensor_model or 'SBE37' in sensor_model or 'SBE37' in long_name:
                    is_microcat = True
                    logger.info(f"Detected MicroCat sensor from {sensor_var}: {sensor_model}")
                    break
            
            # Also check global attributes for SBE model
            if not is_microcat:
                sbe_model = self.data.attrs.get('cnv_sbe_model', '')
                if 'SBE 37' in sbe_model or 'SBE37' in sbe_model:
                    is_microcat = True
                    logger.info(f"Detected MicroCat from cnv_sbe_model: {sbe_model}")
            
            # Also check raw metadata structure for SBE model
            if not is_microcat:
                raw_metadata = self.data.attrs.get('raw_metadata')
                if isinstance(raw_metadata, dict):
                    # Check if raw_metadata is a dictionary (JSON structure)
                    other_attrs = raw_metadata.get('other', {}).get('global_attributes', {})
                    sbe_model = other_attrs.get('cnv_sbe_model', '')
                    if 'SBE 37' in sbe_model or 'SBE37' in sbe_model:
                        is_microcat = True
                        logger.info(f"Detected MicroCat from raw_metadata cnv_sbe_model: {sbe_model}")
                elif isinstance(raw_metadata, str):
                    # Check if raw_metadata is a string and contains SBE37 references
                    if 'SBE37' in raw_metadata:
                        is_microcat = True
                        logger.info(f"Detected MicroCat from raw_metadata string content")
            
            # Use depth profile if: fast sampling (<1min) AND SbeCnvReader AND has required variable types AND NOT MicroCat
            # Check for temperature_1, salinity, and depth (allowing for numbered variants)
            has_temp = any(v.startswith('temperature_') or v == 'temperature' for v in self.data.data_vars)
            has_sal = 'salinity' in self.data.data_vars
            has_depth = 'depth' in self.data.data_vars
            has_depth_vars = has_temp and has_sal and has_depth
            
            use_depth_profile = (
                sampling_freq_minutes < 1 and 
                is_sbe_cnv and 
                has_depth_vars and
                not is_microcat  # Force time series for MicroCat sensors
            )
            logger.info(f"Plot type selection: sampling_freq_minutes={sampling_freq_minutes}, has_depth_vars={has_depth_vars}, is_microcat={is_microcat}, use_depth_profile={use_depth_profile}")
            
            # Extract source filename for plot naming
            if hasattr(self, '_processing_metadata') and self._processing_metadata:
                source_file = self._processing_metadata.get('source_file')
            else:
                source_file = self.data.attrs.get('source_file')
            
            if not source_file:
                source_file = self.data.attrs.get('raw_filename', 'dataset')
            
            source_name = Path(source_file).stem

            if use_depth_profile:
                # Use depth profile plotter with auto-detected variable names
                logger.info(f"Generating depth profile plot: {source_name}_profile.png")
                plotter = DepthProfilePlotter(self.data)
                plot_filename = f"{source_name}_profile.png"
                plot_path = plot_dir / plot_filename
                
                # The DepthProfilePlotter should auto-detect the variables
                # based on what's available in the dataset
                logger.info(f"Calling DepthProfilePlotter.plot with output_file={plot_path}")
                plotter.plot(
                    output_file=str(plot_path),
                    title=f"CTD Profile - {source_name}",
                    figsize=(8, 10)
                )
                logger.info(f"Plot saved, file exists: {plot_path.exists()}")
                
                logger.info(f"Depth profile plot saved to: {plot_path}")
                plot_type = "CTD depth profile"
                var_description = "temperature and salinity vs depth"
                
            else:
                # Use time series plotter with temperature + salinity if available
                # VARIABLE SELECTION LOGIC - Prioritize temp/sal for multi-parameter plot
                # Prefer temperature_1 over conservative_temperature_1
                temp_vars = [v for v in plottable_vars if 'temperature' in v.lower()]
                if 'temperature_1' in temp_vars:
                    temp_vars = ['temperature_1']  # Prefer temperature_1
                elif any('temperature_' in v for v in temp_vars):
                    # Prefer temperature_X over conservative/potential temperature
                    primary_temp = [v for v in temp_vars if v.startswith('temperature_')]
                    if primary_temp:
                        temp_vars = [primary_temp[0]]
                
                sal_vars = [v for v in plottable_vars if 'salinity' in v.lower()]
                
                vars_to_plot = []
                if temp_vars and sal_vars:
                    # Multi-parameter plot with temp + salinity (dual axis)
                    vars_to_plot = [temp_vars[0], sal_vars[0]]
                    plot_filename = f"{source_name}_timeseries.png"
                    dual_axis = True
                else:
                    # Single parameter or mixed parameters
                    priority_vars = ['temperature', 'salinity', 'conductivity', 'pressure', 'density']
                    for priority in priority_vars:
                        matching = [v for v in plottable_vars if priority in v.lower()]
                        if matching:
                            vars_to_plot.append(matching[0])
                        if len(vars_to_plot) >= 2:
                            break
                    
                    if not vars_to_plot:
                        vars_to_plot = plottable_vars[:2]
                    
                    plot_filename = f"{source_name}_timeseries.png"
                    dual_axis = len(set(self.data[v].attrs.get('units', '') for v in vars_to_plot)) > 1
                
                # Generate plot using TimeSeriesPlotter
                plotter = TimeSeriesPlotter(self.data)
                plot_path = plot_dir / plot_filename
                
                plotter.plot(
                    *vars_to_plot,
                    output_file=str(plot_path),
                    dual_axis=dual_axis,
                    figsize=(10, 6)
                )
                
                plot_type = "time series"
                var_description = ', '.join(vars_to_plot)
            
            # Generate RST plot section (use relative path from RST file location)
            # If plot is in a 'plots' subdirectory relative to the RST file
            relative_path = f"plots/{plot_filename}"
            
            plot_section = [
                'Dataset Visualization',
                '^' * 20,
                '',
                f'.. figure:: {relative_path}',
                f'   :alt: Dataset {plot_type} plot',
                '   :align: center',
                '   :scale: 80%',
                '',
                f'   {plot_type.title()} plot showing {var_description}.',
                f'   Sampling frequency: {sampling_freq_minutes:.1f} minutes.',
                ''
            ]
            logger.info(f"Returning plot section with {len(plot_section)} lines")
            return plot_section
            
        except ImportError:
            logger.warning("SeaSenseLib plotters not available for plot generation")
            return None
        except Exception as e:
            logger.warning(f"Failed to generate plot using SeaSenseLib plotters: {e}", exc_info=True)
            # Fallback to simple matplotlib plot
            logger.info("Attempting fallback to simple matplotlib plot")
            return self._generate_simple_plot(plot_output_dir)

    def _generate_simple_plot(self, plot_output_dir: Optional[str]) -> Optional[List[str]]:
        """Fallback simple matplotlib plot generation."""
        try:
            import matplotlib.pyplot as plt
            
            plot_dir = Path(plot_output_dir) if plot_output_dir else Path.cwd() / 'plots'
            plot_dir.mkdir(parents=True, exist_ok=True)
            
            # Find first plottable variable
            time_coords = [c for c in self.data.coords if 'time' in c.lower()]
            if not time_coords:
                return None
            
            plottable_vars = [v for v, var in self.data.data_vars.items() 
                             if time_coords[0] in var.dims and np.issubdtype(var.dtype, np.number)]
            if not plottable_vars:
                return None
            
            var_to_plot = plottable_vars[0]
            var_data = self.data[var_to_plot]
            
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(self.data[time_coords[0]], var_data, linewidth=1)
            ax.set_ylabel(f"{var_data.attrs.get('long_name', var_to_plot)} ({var_data.attrs.get('units', '')})")
            ax.set_xlabel(f"{time_coords[0]} ({self.data[time_coords[0]].attrs.get('units', '')})")
            ax.set_title(f"{var_data.attrs.get('long_name', var_to_plot)}")
            ax.grid(True, alpha=0.3)
            
            # Save plot
            source_name = Path(self.data.attrs.get('source_file', 'dataset')).stem
            plot_filename = f"{source_name}_simple_plot.png"
            plot_path = plot_dir / plot_filename
            fig.savefig(plot_path, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close(fig)
            
            relative_path = f"plots/{plot_filename}"
            return [
                'Dataset Visualization',
                '^' * 20,
                '',
                f'.. figure:: {relative_path}',
                '   :alt: Dataset plot',
                '   :align: center',
                '   :scale: 80%',
                '',
                f'   Simple time series plot for {var_to_plot}.',
                ''
            ]
            
        except Exception as e:
            logger.warning(f"Failed to generate simple plot: {e}")
            return None

    def _analyze_temporal_coverage(self) -> Dict[str, Any]:
        """Analyze temporal coverage of the dataset."""
        time_coords = [c for c in self.data.coords if 'time' in c.lower()]
        
        if not time_coords:
            return {'has_time': False}
        
        time_coord = time_coords[0]
        time_data = self.data[time_coord]
        
        try:
            # Convert to pandas for analysis
            if time_data.dtype.kind == 'M':  # datetime64
                time_series = pd.to_datetime(time_data.values)
            else:
                # Try to convert numeric time
                time_series = pd.to_datetime(time_data.values)
            
            # Remove invalid times
            valid_times = time_series.dropna()
            if len(valid_times) == 0:
                return {'has_time': True, 'valid_times': False}
            
            start_date = valid_times.min()
            end_date = valid_times.max()
            
            time_info = {
                'has_time': True,
                'valid_times': True,
                'coordinate_name': time_coord,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'total_records': len(valid_times),
                'time_span_days': (end_date - start_date).days
            }
            
            # Estimate frequency
            if len(valid_times) > 1:
                median_diff = pd.Series(valid_times).diff().median()
                time_info['estimated_frequency'] = self._estimate_frequency(median_diff)
            
            return time_info
            
        except Exception:
            return {'has_time': True, 'valid_times': False}

    def _estimate_frequency(self, median_diff: pd.Timedelta) -> str:
        """Estimate sampling frequency from median time difference."""
        hours = median_diff.total_seconds() / 3600
        
        if hours < 1:
            return f"{int(median_diff.total_seconds()//60)}min"
        elif hours < 12:
            return f"{hours:.1f}H"
        elif 10 <= hours <= 14:
            return "12H"
        elif 20 <= hours <= 28:
            return "daily"
        elif 720 <= hours <= 760:
            return "monthly"
        else:
            return f"{hours:.1f}H"

    def _parse_frequency_to_minutes(self, freq_str: str) -> float:
        """Parse frequency string to minutes (e.g., '5min' -> 5, '1.5H' -> 90)."""
        if not freq_str:
            return 60.0  # Default 1 hour
        
        freq_lower = freq_str.lower()
        
        if freq_lower.endswith('min'):
            return float(freq_lower.replace('min', ''))
        elif freq_lower.endswith('h'):
            hours = float(freq_lower.replace('h', ''))
            return hours * 60
        elif freq_lower == 'daily':
            return 24 * 60
        elif freq_lower == 'monthly':
            return 30 * 24 * 60
        else:
            return 60.0  # Default fallback

    def _dataframe_to_rst_table(self, df: pd.DataFrame) -> List[str]:
        """Convert DataFrame to RST list-table format."""
        if df.empty:
            return ['(No data available)']
        
        lines = []
        num_cols = len(df.columns)
        col_width = max(15, 100 // num_cols)
        
        # Start list-table directive
        lines.extend([
            '.. list-table::',
            f'   :widths: {" ".join([str(col_width)] * num_cols)}',
            '   :header-rows: 1',
            ''
        ])
        
        # Header row
        header_row = '   * - ' + '\n     - '.join(df.columns)
        lines.append(header_row)
        
        # Data rows
        for _, row in df.iterrows():
            cell_values = []
            for col in df.columns:
                cell_value = str(row[col])
                # Keep RST formatting, escape backticks only
                cell_value = cell_value.replace('`', '\\`')
                # Preserve newlines for columns with RST list formatting
                if col not in ['Calibration Coefficients', 'Vocabulary', 'Details']:
                    cell_value = cell_value.replace('\n', ' ')
                cell_values.append(cell_value)
            
            data_row = '   * - ' + '\n     - '.join(cell_values)
            lines.append(data_row)
        
        lines.append('')
        return lines