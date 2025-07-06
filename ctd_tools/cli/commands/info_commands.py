"""
Information commands (formats).
"""

import argparse
import csv
import json
from io import StringIO
from .base import BaseCommand, CommandResult


class FormatsCommand(BaseCommand):
    """Handle formats listing with minimal dependencies."""

    def execute(self, args: argparse.Namespace) -> CommandResult:
        """Execute formats command."""
        try:
            # Use the lightweight format registry instead of loading heavy reader classes
            # pylint: disable=C0415
            from ...core.format_registry import get_all_formats

            # Get format information without loading reader classes
            formats_data = []
            for format_info in get_all_formats():
                format_data = {
                    'name': format_info.name,
                    'key': format_info.key,
                    'extension': format_info.extension,
                    'class': format_info.class_name
                }
                formats_data.append(format_data)

            # Apply filtering if specified
            if args.filter:
                filter_term = args.filter.lower()
                formats_data = [
                    fmt for fmt in formats_data
                    if filter_term in fmt['name'].lower() or 
                       filter_term in fmt['extension'].lower() or
                       filter_term in fmt['key'].lower()
                ]

            # Sort data
            sort_key = args.sort
            if sort_key == 'name':
                formats_data.sort(key=lambda x: x['name'].lower(), reverse=args.reverse)
            elif sort_key == 'key':
                formats_data.sort(key=lambda x: x['key'].lower(), reverse=args.reverse)
            elif sort_key == 'extension':
                formats_data.sort(key=lambda x: x['extension'].lower(), reverse=args.reverse)

            # Output based on selected format
            self._output_formats(formats_data, args)

            return CommandResult(success=True, message="Formats displayed successfully")

        except Exception as e:
            return CommandResult(success=False, message=str(e))

    def _output_formats(self, formats_data, args):
        """Output formats in the requested format."""
        output_format = args.output

        if output_format == 'json':
            print(json.dumps(formats_data, indent=2))
        elif output_format == 'yaml':
            try:
                # pylint: disable=C0415
                import yaml
                print(yaml.dump(formats_data, default_flow_style=False))
            except ImportError:
                print("Error: PyYAML not installed. Install with: pip install PyYAML")
                print("Falling back to JSON format:")
                print(json.dumps(formats_data, indent=2))
        elif output_format == 'csv':
            self._output_csv(formats_data, args)
        else:  # table format (default)
            self._output_table(formats_data, args)

    def _output_csv(self, formats_data, args):
        """Output formats as CSV."""
        output = StringIO()
        fieldnames = ['name', 'key', 'extension']
        if args.verbose:
            fieldnames.append('class')

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        if not args.no_header:
            writer.writeheader()

        for fmt in formats_data:
            row = {k: fmt[k] for k in fieldnames}
            writer.writerow(row)

        print(output.getvalue().rstrip())

    def _output_table(self, formats_data, args):
        """Output formats as a formatted table."""
        if not formats_data:
            print("No formats found matching the criteria.")
            return

        # Determine columns to show
        columns = [
            ('Format', 'name'),
            ('Key', 'key'),
            ('Extension', 'extension')
        ]

        if args.verbose:
            columns.append(('Class', 'class'))

        # Calculate column widths
        col_widths = []
        for header, field in columns:
            max_width = len(header)
            for fmt in formats_data:
                max_width = max(max_width, len(str(fmt[field])))
            col_widths.append(max_width + 2)  # Add padding

        # Create table border
        border = "+" + "+".join("-" * width for width in col_widths) + "+"

        # Print table
        if not args.no_header:
            print(border)
            header_row = "|"
            for i, (header, _) in enumerate(columns):
                header_row += f" {header:<{col_widths[i]-2}} |"
            print(header_row)
            print(border)

        for fmt in formats_data:
            row = "|"
            for i, (_, field) in enumerate(columns):
                value = str(fmt[field])
                row += f" {value:<{col_widths[i]-2}} |"
            print(row)

        if not args.no_header:
            print(border)

        # Show summary
        if not args.no_header:
            print(f"\nTotal: {len(formats_data)} format(s)")
            if args.filter:
                print(f"Filtered by: '{args.filter}'")
