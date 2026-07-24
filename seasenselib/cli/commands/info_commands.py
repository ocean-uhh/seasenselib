"""
Information commands (list, formats).
"""

import argparse
import csv
import json
import shutil
import textwrap
from io import StringIO
from .base import BaseCommand, CommandResult


class ListCommand(BaseCommand):
    """Handle listing of readers, writers, and plotters with minimal dependencies."""

    def execute(self, args: argparse.Namespace) -> CommandResult:
        """Execute list command."""
        try:
            resource_type = args.resource_type
            all_data = []

            if resource_type == 'parameters':
                all_data = self._list_parameters()
                self._apply_filters_and_sort(all_data, args, resource_type)
                self._output_parameters(all_data, args)
                return CommandResult(success=True, message="Parameter list displayed successfully")

            if resource_type == 'reader-args':
                all_data = self._list_reader_args()
                self._apply_filters_and_sort(all_data, args, resource_type)
                self._output_reader_args(all_data, args)
                return CommandResult(success=True, message="Reader argument list displayed successfully")

            if resource_type == 'pipeline-stages':
                all_data = self._list_stages()
                self._apply_filters_and_sort(all_data, args, resource_type)
                self._output_stages(all_data, args)
                return CommandResult(success=True, message="Stage list displayed successfully")

            if resource_type == 'pipeline-handlers':
                all_data = self._list_handlers()
                self._apply_filters_and_sort(all_data, args, resource_type)
                self._output_handlers(all_data, args)
                return CommandResult(success=True, message="Handler list displayed successfully")

            if resource_type == 'pipeline-profiles':
                all_data = self._list_pipeline_profiles()
                self._apply_filters_and_sort(all_data, args, resource_type)
                self._output_pipeline_profiles(all_data, args)
                return CommandResult(success=True, message="Pipeline profile list displayed successfully")

            # Use autodiscovery to get format information
            # pylint: disable=C0415
            from ...core.autodiscovery import ReaderDiscovery, WriterDiscovery, PlotterDiscovery

            # Collect data based on resource type
            if resource_type in ['all', 'readers']:
                discovery = ReaderDiscovery()
                readers = self._convert_format_info(discovery.get_format_info(), 'reader')
                all_data.extend(readers)

            if resource_type in ['all', 'writers']:
                discovery = WriterDiscovery()
                writers = self._convert_format_info(discovery.get_format_info(), 'writer')
                all_data.extend(writers)

            if resource_type in ['all', 'plotters']:
                discovery = PlotterDiscovery()
                plotters = self._convert_format_info(discovery.get_format_info(), 'plotter')
                all_data.extend(plotters)

            # Apply filtering and sorting
            self._apply_filters_and_sort(all_data, args, resource_type)

            # Output based on selected format
            self._output_list(all_data, args)

            return CommandResult(success=True, message="List displayed successfully")

        except Exception as e:
            return CommandResult(success=False, message=str(e))

    def _convert_format_info(self, format_info_list, resource_type):
        """Convert format info to unified structure with type."""
        result = []
        for format_info in format_info_list:
            extensions = format_info.get('extensions') or []
            extension_text = ', '.join(extensions)
            item = {
                'name': format_info.get('name', 'Unknown'),
                'key': format_info['key'],
                'extension': extension_text or format_info.get('extension') or '',
                'extensions': extensions,
                'class': format_info['class_name'],
                'type': resource_type,
                'is_plugin': format_info.get('is_plugin', False)
            }
            result.append(item)
        return result

    @staticmethod
    def _format_value(value):
        """Format reader argument defaults for compact table and CSV output."""
        if value is None:
            return ''
        if isinstance(value, bool):
            return 'true' if value else 'false'
        return str(value)

    def _list_reader_args(self):
        """List reader-specific arguments accepted by --reader-arg."""
        from ...core.autodiscovery import ReaderDiscovery
        discovery = ReaderDiscovery()
        classes = discovery.discover_classes()
        plugin_classes = discovery.get_plugin_classes()

        rows = []
        for class_name, class_obj in classes.items():
            try:
                reader_key = class_obj.format_key()
                reader_name = class_obj.format_name()
                specs = class_obj.reader_args()
            except Exception:
                continue

            for spec in specs or []:
                name = spec.get('name')
                if not name:
                    continue
                cli_name = spec.get('cli_name') or str(name).replace('_', '-')
                choices = spec.get('choices') or []
                default = spec.get('default')
                rows.append({
                    'reader': reader_key,
                    'reader_name': reader_name,
                    'argument': name,
                    'cli_name': cli_name,
                    'type': spec.get('type', ''),
                    'default': default,
                    'default_text': self._format_value(default),
                    'choices': choices,
                    'choices_text': ', '.join(str(choice) for choice in choices),
                    'required': bool(spec.get('required', False)),
                    'description': spec.get('description', ''),
                    'source': spec.get('source', 'declared'),
                    'class': class_name,
                    'is_plugin': class_name in plugin_classes,
                })

        return rows

    def _list_parameters(self):
        """List canonical parameter names."""
        try:
            # pylint: disable=C0415
            import seasenselib.parameters as params
            metadata = getattr(params, 'metadata', {}) or {}
            default_mappings = getattr(params, 'default_mappings', {}) or {}
            allowed = params.allowed_parameters()
        except Exception:
            metadata = {}
            default_mappings = {}
            allowed = {}

        data = []
        names = set()
        if isinstance(default_mappings, dict):
            names.update(default_mappings.keys())
        if isinstance(metadata, dict):
            names.update(metadata.keys())

        if names:
            for name in sorted(names):
                if isinstance(metadata, dict) and name in metadata:
                    description = self._describe_parameter(name, metadata[name])
                else:
                    description = allowed.get(name) if isinstance(allowed, dict) else None
                    if not description:
                        description = name.replace('_', ' ').title()
                data.append({'name': name, 'description': description})
        else:
            for name, description in allowed.items():
                data.append({
                    'name': name,
                    'description': description or ''
                })
        return data

    @staticmethod
    def _describe_parameter(name, info):
        """Build a short description from metadata."""
        if not isinstance(info, dict):
            return name.replace('_', ' ').title()
        long_name = info.get('long_name') or name.replace('_', ' ').title()
        units = info.get('units')
        if units:
            return f"{long_name} ({units})"
        return long_name

    def _apply_filters_and_sort(self, data, args, resource_type):
        """Apply filtering and sorting to list data."""
        if args.filter:
            filter_term = args.filter.lower()
            if resource_type == 'parameters':
                data[:] = [
                    item for item in data
                    if filter_term in item['name'].lower() or
                       filter_term in item.get('description', '').lower()
                ]
            elif resource_type == 'pipeline-stages':
                data[:] = [
                    item for item in data
                    if filter_term in item.get('name', '').lower() or
                       filter_term in item.get('class', '').lower()
                ]
            elif resource_type == 'pipeline-handlers':
                data[:] = [
                    item for item in data
                    if filter_term in item.get('name', '').lower() or
                       filter_term in item.get('stage', '').lower() or
                       filter_term in item.get('class', '').lower()
                ]
            elif resource_type == 'pipeline-profiles':
                data[:] = [
                    item for item in data
                    if filter_term in item.get('name', '').lower() or
                       filter_term in item.get('description', '').lower() or
                       filter_term in item.get('file', '').lower()
                ]
            elif resource_type == 'reader-args':
                data[:] = [
                    item for item in data
                    if filter_term in item.get('reader', '').lower() or
                       filter_term in item.get('reader_name', '').lower() or
                       filter_term in item.get('argument', '').lower() or
                       filter_term in item.get('cli_name', '').lower() or
                       filter_term in item.get('description', '').lower() or
                       filter_term in item.get('class', '').lower()
                ]
            else:
                data[:] = [
                    item for item in data
                    if filter_term in item['name'].lower() or
                       filter_term in item.get('extension', '').lower() or
                       filter_term in item['key'].lower() or
                       filter_term in item['type'].lower()
                ]

        sort_key = args.sort
        if resource_type == 'parameters':
            if sort_key in ['name', 'key']:
                data.sort(key=lambda x: x['name'].lower(), reverse=args.reverse)
        elif resource_type == 'pipeline-stages':
            if sort_key == 'name':
                data.sort(key=lambda x: x.get('name', '').lower(), reverse=args.reverse)
            elif sort_key == 'class':
                data.sort(key=lambda x: x.get('class', '').lower(), reverse=args.reverse)
        elif resource_type == 'pipeline-handlers':
            if sort_key == 'stage':
                data.sort(key=lambda x: x.get('stage', '').lower(), reverse=args.reverse)
            elif sort_key == 'name':
                data.sort(key=lambda x: x.get('name', '').lower(), reverse=args.reverse)
            elif sort_key == 'class':
                data.sort(key=lambda x: x.get('class', '').lower(), reverse=args.reverse)
        elif resource_type == 'pipeline-profiles':
            if sort_key == 'name':
                data.sort(key=lambda x: x.get('name', '').lower(), reverse=args.reverse)
        elif resource_type == 'reader-args':
            if sort_key in ['name', 'reader', 'key']:
                data.sort(
                    key=lambda x: (x.get('reader', '').lower(), x.get('argument', '').lower()),
                    reverse=args.reverse,
                )
            elif sort_key == 'argument':
                data.sort(
                    key=lambda x: (x.get('argument', '').lower(), x.get('reader', '').lower()),
                    reverse=args.reverse,
                )
            elif sort_key == 'class':
                data.sort(
                    key=lambda x: (x.get('class', '').lower(), x.get('argument', '').lower()),
                    reverse=args.reverse,
                )
        else:
            if sort_key == 'name':
                data.sort(key=lambda x: x['name'].lower(), reverse=args.reverse)
            elif sort_key == 'key':
                data.sort(key=lambda x: x['key'].lower(), reverse=args.reverse)
            elif sort_key == 'extension':
                data.sort(key=lambda x: x.get('extension', '').lower(), reverse=args.reverse)
            elif sort_key == 'type':
                data.sort(key=lambda x: x['type'].lower(), reverse=args.reverse)

    def _list_stages(self):
        """List available pipeline stages."""
        try:
            from ...pipeline.registry import StageRegistry
            registry = StageRegistry.get_instance()
            builtin = set(registry.list_builtin_stages())
            data = []
            for name in registry.list_stages():
                cls = registry.get_stage_class(name)
                data.append({
                    'name': name,
                    'class': cls.__name__,
                    'class_path': f"{cls.__module__}.{cls.__name__}",
                    'is_plugin': name not in builtin,
                })
            return data
        except Exception:
            return []

    def _list_handlers(self):
        """List available pipeline handlers."""
        try:
            from ...pipeline.handler_catalog import list_handlers
            return list_handlers(include_plugins=True)
        except Exception:
            return []

    def _list_pipeline_profiles(self):
        """List available pipeline profiles."""
        try:
            from importlib import resources
            profiles = []
            root = resources.files('seasenselib.config.pipeline')
            for item in root.iterdir():
                if not item.is_file():
                    continue
                suffix = item.suffix.lower()
                if suffix not in {'.json', '.yaml', '.yml', '.toml'}:
                    continue
                description = ""
                if suffix == '.json':
                    try:
                        with item.open('r', encoding='utf-8') as handle:
                            data = json.load(handle)
                        if isinstance(data, dict):
                            global_cfg = data.get('global', {})
                            if isinstance(global_cfg, dict):
                                description = str(global_cfg.get('description', '') or '')
                            if not description:
                                description = str(data.get('description', '') or '')
                    except Exception:
                        description = ""
                profiles.append({'name': item.stem, 'description': description, 'file': item.name})
            return profiles
        except Exception:
            return []

    def _output_list(self, data, args):
        """Output list in the requested format."""
        output_format = args.output

        if output_format == 'json':
            print(json.dumps(data, indent=2))
        elif output_format == 'yaml':
            try:
                # pylint: disable=C0415
                import yaml
                print(yaml.dump(data, default_flow_style=False))
            except ImportError:
                print("Error: PyYAML not installed. Install with: pip install PyYAML")
                print("Falling back to JSON format:")
                print(json.dumps(data, indent=2))
        elif output_format == 'csv':
            self._output_csv(data, args)
        else:  # table format (default)
            self._output_table(data, args)

    def _output_parameters(self, data, args):
        """Output parameter list in the requested format."""
        output_format = args.output

        if output_format == 'json':
            print(json.dumps(data, indent=2))
        elif output_format == 'yaml':
            try:
                # pylint: disable=C0415
                import yaml
                print(yaml.dump(data, default_flow_style=False))
            except ImportError:
                print("Error: PyYAML not installed. Install with: pip install PyYAML")
                print("Falling back to JSON format:")
                print(json.dumps(data, indent=2))
        elif output_format == 'csv':
            self._output_parameters_csv(data, args)
        else:
            self._output_parameters_table(data, args)

    def _output_reader_args(self, data, args):
        """Output reader argument list in the requested format."""
        output_format = args.output

        if output_format == 'json':
            print(json.dumps(data, indent=2, default=str))
        elif output_format == 'yaml':
            try:
                # pylint: disable=C0415
                import yaml
                print(yaml.dump(data, default_flow_style=False))
            except ImportError:
                print("Error: PyYAML not installed. Install with: pip install PyYAML")
                print("Falling back to JSON format:")
                print(json.dumps(data, indent=2, default=str))
        elif output_format == 'csv':
            self._output_reader_args_csv(data, args)
        else:
            self._output_reader_args_table(data, args)

    def _output_stages(self, data, args):
        """Output stage list in the requested format."""
        output_format = args.output

        if output_format == 'json':
            print(json.dumps(data, indent=2))
        elif output_format == 'yaml':
            try:
                # pylint: disable=C0415
                import yaml
                print(yaml.dump(data, default_flow_style=False))
            except ImportError:
                print("Error: PyYAML not installed. Install with: pip install PyYAML")
                print("Falling back to JSON format:")
                print(json.dumps(data, indent=2))
        elif output_format == 'csv':
            self._output_stages_csv(data, args)
        else:
            self._output_stages_table(data, args)

    def _output_handlers(self, data, args):
        """Output handler list in the requested format."""
        output_format = args.output

        if output_format == 'json':
            print(json.dumps(data, indent=2))
        elif output_format == 'yaml':
            try:
                # pylint: disable=C0415
                import yaml
                print(yaml.dump(data, default_flow_style=False))
            except ImportError:
                print("Error: PyYAML not installed. Install with: pip install PyYAML")
                print("Falling back to JSON format:")
                print(json.dumps(data, indent=2))
        elif output_format == 'csv':
            self._output_handlers_csv(data, args)
        else:
            self._output_handlers_table(data, args)

    def _output_pipeline_profiles(self, data, args):
        """Output pipeline profile list in the requested format."""
        output_format = args.output

        if output_format == 'json':
            print(json.dumps(data, indent=2))
        elif output_format == 'yaml':
            try:
                # pylint: disable=C0415
                import yaml
                print(yaml.dump(data, default_flow_style=False))
            except ImportError:
                print("Error: PyYAML not installed. Install with: pip install PyYAML")
                print("Falling back to JSON format:")
                print(json.dumps(data, indent=2))
        elif output_format == 'csv':
            self._output_pipeline_profiles_csv(data, args)
        else:
            self._output_pipeline_profiles_table(data, args)

    def _output_parameters_csv(self, data, args):
        """Output parameter data as CSV."""
        output = StringIO()
        fieldnames = ['name', 'description']
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        if not args.no_header:
            writer.writeheader()
        for item in data:
            row = {k: item.get(k, '') for k in fieldnames}
            writer.writerow(row)
        print(output.getvalue().rstrip())

    def _output_reader_args_csv(self, data, args):
        """Output reader argument data as CSV."""
        output = StringIO()
        fieldnames = [
            'reader',
            'reader_name',
            'cli_name',
            'argument',
            'type',
            'default_text',
            'choices_text',
            'required',
            'description',
        ]
        if getattr(args, 'list_details', False):
            fieldnames.extend(['class', 'source', 'is_plugin'])

        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        if not args.no_header:
            writer.writeheader()
        for item in data:
            row = {k: item.get(k, '') for k in fieldnames}
            writer.writerow(row)
        print(output.getvalue().rstrip())

    def _output_stages_csv(self, data, args):
        """Output stage data as CSV."""
        output = StringIO()
        fieldnames = ['name', 'class', 'is_plugin']
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        if not args.no_header:
            writer.writeheader()
        for item in data:
            row = {k: item.get(k, '') for k in fieldnames}
            writer.writerow(row)
        print(output.getvalue().rstrip())

    def _output_handlers_csv(self, data, args):
        """Output handler data as CSV."""
        output = StringIO()
        fieldnames = ['stage', 'name', 'class', 'is_plugin']
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        if not args.no_header:
            writer.writeheader()
        for item in data:
            row = {k: item.get(k, '') for k in fieldnames}
            writer.writerow(row)
        print(output.getvalue().rstrip())

    def _output_pipeline_profiles_csv(self, data, args):
        """Output pipeline profile data as CSV."""
        output = StringIO()
        fieldnames = ['name', 'description', 'file']
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        if not args.no_header:
            writer.writeheader()
        for item in data:
            row = {k: item.get(k, '') for k in fieldnames}
            writer.writerow(row)
        print(output.getvalue().rstrip())

    def _output_parameters_table(self, data, args):
        """Output parameter data as a formatted table."""
        if not data:
            print("No parameters found matching the criteria.")
            return

        columns = [
            ('Name', 'name'),
            ('Description', 'description'),
        ]

        col_widths = []
        for header, field in columns:
            max_width = len(header)
            for item in data:
                value = str(item.get(field, ''))
                max_width = max(max_width, len(value))
            col_widths.append(max_width + 2)

        border = "+" + "+".join("-" * width for width in col_widths) + "+"

        if not args.no_header:
            print(border)
            header_row = "|"
            for i, (header, _) in enumerate(columns):
                header_row += f" {header:<{col_widths[i]-2}} |"
            print(header_row)
            print(border)

        for item in data:
            row = "|"
            for i, (_, field) in enumerate(columns):
                value = str(item.get(field, ''))
                row += f" {value:<{col_widths[i]-2}} |"
            print(row)

        if not args.no_header:
            print(border)
            print(f"\nTotal: {len(data)} parameter(s)")

    def _output_reader_args_table(self, data, args):
        """Output reader argument data as a wrapped help-style listing."""
        if not data:
            print("No reader arguments found matching the criteria.")
            return

        if not args.no_header:
            print("Reader-specific arguments")
            print("Use with: --reader-arg NAME=VALUE")
            print()

        width = max(40, shutil.get_terminal_size(fallback=(88, 24)).columns)
        current_reader = None
        for item in data:
            reader = item.get('reader', '')
            if reader != current_reader:
                if current_reader is not None:
                    print()
                reader_name = item.get('reader_name') or reader
                print(f"{reader_name} ({reader}):")
                current_reader = reader

            invocation = self._reader_arg_invocation(item)
            description = self._reader_arg_description(
                item,
                include_details=getattr(args, 'list_details', False),
            )
            self._print_reader_arg_option(invocation, description, width)

        if not args.no_header:
            print(f"\nTotal: {len(data)} reader argument(s)")

    @staticmethod
    def _reader_arg_invocation(item):
        """Return a compact NAME=VALUE form for --reader-arg help output."""
        choices = item.get('choices') or []
        if choices:
            value_hint = "{" + ",".join(str(choice) for choice in choices) + "}"
        else:
            type_name = str(item.get('type') or '').lower()
            if 'bool' in type_name and 'path' in type_name:
                value_hint = 'BOOL|PATH'
            elif 'bool' in type_name and 'str' in type_name:
                value_hint = 'BOOL|TEXT'
            elif type_name == 'bool':
                value_hint = 'BOOL'
            elif type_name == 'int':
                value_hint = 'INT'
            elif type_name == 'float':
                value_hint = 'FLOAT'
            elif type_name == 'path':
                value_hint = 'PATH'
            elif type_name == 'str':
                value_hint = 'TEXT'
            else:
                value_hint = 'VALUE'
        return f"{item.get('cli_name', item.get('argument', 'NAME'))}={value_hint}"

    @staticmethod
    def _reader_arg_description(item, include_details=False):
        """Return a wrapped help description for a reader argument."""
        description = item.get('description', '')
        details = []
        type_name = item.get('type')
        if type_name:
            details.append(f"type: {type_name}")
        choices_text = item.get('choices_text')
        if choices_text:
            details.append(f"choices: {choices_text}")
        default_text = item.get('default_text')
        if default_text:
            details.append(f"default: {default_text}")
        if item.get('required'):
            details.append("required")
        if include_details:
            details.extend([
                f"python: {item.get('argument', '')}",
                f"source: {item.get('source', '')}",
                f"class: {item.get('class', '')}",
            ])
        if details:
            suffix = "; ".join(detail for detail in details if detail)
            if description:
                return f"{description} ({suffix})"
            return suffix
        return description

    @staticmethod
    def _print_reader_arg_option(invocation, description, width):
        """Print one reader argument in an argparse-like wrapped layout."""
        option_indent = "  "
        help_indent = "      "
        print(f"{option_indent}{invocation}")
        if description:
            print(textwrap.fill(
                description,
                width=width,
                initial_indent=help_indent,
                subsequent_indent=help_indent,
            ))

    def _output_stages_table(self, data, args):
        """Output stage data as a formatted table."""
        if not data:
            print("No stages found matching the criteria.")
            return

        columns = [('Name', 'name'), ('Plugin', 'is_plugin')]
        if getattr(args, 'list_details', False):
            columns.insert(1, ('Class', 'class'))

        col_widths = []
        for header, field in columns:
            max_width = len(header)
            for item in data:
                value = str(item.get(field, ''))
                if field == 'is_plugin':
                    value = 'Yes' if item.get('is_plugin', False) else 'No'
                max_width = max(max_width, len(value))
            col_widths.append(max_width + 2)

        border = "+" + "+".join("-" * width for width in col_widths) + "+"

        if not args.no_header:
            print(border)
            header_row = "|"
            for i, (header, _) in enumerate(columns):
                header_row += f" {header:<{col_widths[i]-2}} |"
            print(header_row)
            print(border)

        for item in data:
            row = "|"
            for i, (_, field) in enumerate(columns):
                value = str(item.get(field, ''))
                if field == 'is_plugin':
                    value = 'Yes' if item.get('is_plugin', False) else 'No'
                row += f" {value:<{col_widths[i]-2}} |"
            print(row)

        if not args.no_header:
            print(border)
            print(f"\nTotal: {len(data)} stage(s)")

    def _output_handlers_table(self, data, args):
        """Output handler data as a formatted table."""
        if not data:
            print("No handlers found matching the criteria.")
            return

        columns = [('Stage', 'stage'), ('Handler', 'name'), ('Plugin', 'is_plugin')]
        if getattr(args, 'list_details', False):
            columns.insert(2, ('Class', 'class'))

        col_widths = []
        for header, field in columns:
            max_width = len(header)
            for item in data:
                value = str(item.get(field, ''))
                if field == 'is_plugin':
                    value = 'Yes' if item.get('is_plugin', False) else 'No'
                max_width = max(max_width, len(value))
            col_widths.append(max_width + 2)

        border = "+" + "+".join("-" * width for width in col_widths) + "+"

        if not args.no_header:
            print(border)
            header_row = "|"
            for i, (header, _) in enumerate(columns):
                header_row += f" {header:<{col_widths[i]-2}} |"
            print(header_row)
            print(border)

        for item in data:
            row = "|"
            for i, (_, field) in enumerate(columns):
                value = str(item.get(field, ''))
                if field == 'is_plugin':
                    value = 'Yes' if item.get('is_plugin', False) else 'No'
                row += f" {value:<{col_widths[i]-2}} |"
            print(row)

        if not args.no_header:
            print(border)
            print(f"\nTotal: {len(data)} handler(s)")

    def _output_pipeline_profiles_table(self, data, args):
        """Output pipeline profile data as a formatted table."""
        if not data:
            print("No pipeline profiles found matching the criteria.")
            return

        columns = [('Name', 'name'), ('Description', 'description'), ('File', 'file')]

        col_widths = []
        for header, field in columns:
            max_width = len(header)
            for item in data:
                value = str(item.get(field, ''))
                max_width = max(max_width, len(value))
            col_widths.append(max_width + 2)

        border = "+" + "+".join("-" * width for width in col_widths) + "+"

        if not args.no_header:
            print(border)
            header_row = "|"
            for i, (header, _) in enumerate(columns):
                header_row += f" {header:<{col_widths[i]-2}} |"
            print(header_row)
            print(border)

        for item in data:
            row = "|"
            for i, (_, field) in enumerate(columns):
                value = str(item.get(field, ''))
                row += f" {value:<{col_widths[i]-2}} |"
            print(row)

        if not args.no_header:
            print(border)
            print(f"\nTotal: {len(data)} profile(s)")
    def _output_csv(self, data, args):
        """Output data as CSV."""
        output = StringIO()
        fieldnames = ['name', 'key', 'type', 'extension']
        if getattr(args, 'list_details', False):
            fieldnames.extend(['class', 'is_plugin'])

        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        if not args.no_header:
            writer.writeheader()

        for item in data:
            row = {k: item.get(k, '') for k in fieldnames}
            writer.writerow(row)

        print(output.getvalue().rstrip())

    def _output_table(self, data, args):
        """Output data as a formatted table."""
        if not data:
            print("No resources found matching the criteria.")
            return

        # Determine if we're showing a single resource type
        resource_type = args.resource_type
        single_type = resource_type in ['readers', 'writers', 'plotters']
        
        # Determine columns to show
        columns = [
            ('Name', 'name'),
            ('Key', 'key'),
        ]
        
        # Only show Type column if showing multiple types (all)
        if not single_type:
            columns.append(('Type', 'type'))
        
        # Only show Extension column for readers/writers (not for plotters)
        if resource_type != 'plotters':
            # Check if any item has an extension
            has_extensions = any(item.get('extension') for item in data)
            if has_extensions:
                columns.append(('Extension', 'extension'))
        
        # Add Plugin column
        columns.append(('Plugin', 'is_plugin'))
        
        if getattr(args, 'list_details', False):
            columns.append(('Class', 'class'))

        # Calculate column widths
        col_widths = []
        for header, field in columns:
            max_width = len(header)
            for item in data:
                value = str(item.get(field, ''))
                # Format plugin column as Yes/No
                if field == 'is_plugin':
                    value = 'Yes' if item.get('is_plugin', False) else 'No'
                max_width = max(max_width, len(value))
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

        for item in data:
            row = "|"
            for i, (_, field) in enumerate(columns):
                value = str(item.get(field, ''))
                # Format plugin column as Yes/No
                if field == 'is_plugin':
                    value = 'Yes' if item.get('is_plugin', False) else 'No'
                row += f" {value:<{col_widths[i]-2}} |"
            print(row)

        if not args.no_header:
            print(border)

        # Show summary
        if not args.no_header:
            total = len(data)
            plugins = sum(1 for item in data if item.get('is_plugin', False))
            print(f"\nTotal: {total} resource(s)", end='')
            if plugins > 0:
                print(f" ({plugins} plugin(s))")
            else:
                print()
            if args.filter:
                print(f"Filtered by: '{args.filter}'")
            
            # Show usage hint if showing all resources (no specific type selected)
            if args.resource_type == 'all' and not args.filter:
                print("\nTip: Use 'seasenselib list readers', 'list writers', or 'list plotters'")
                print("     to show only specific resource types.")
                print("     Use 'seasenselib list parameters' to list canonical variable names.")
                print("     Use 'seasenselib list reader-args' to list reader-specific options.")
                print("     Use 'seasenselib list pipeline-stages' or 'list pipeline-handlers' for pipeline components.")
                print("     Use 'seasenselib list pipeline-profiles' to list built-in pipeline profiles.")
                print("     Use --help for more options (filtering, sorting, output formats).")


class FormatsCommand(BaseCommand):
    """
    Legacy formats command - redirects to ListCommand with 'readers' resource type.
    Maintained for backward compatibility.
    """

    def execute(self, args: argparse.Namespace) -> CommandResult:
        """
        Execute formats command by delegating to ListCommand.
        
        This maintains backward compatibility by treating 'formats' as 
        an alias for 'list readers'.
        """
        # Create a modified args namespace that forces resource_type to 'readers'
        # This ensures 'formats' only shows readers (original behavior)
        list_args = argparse.Namespace(**vars(args))
        list_args.resource_type = 'readers'
        
        # Delegate to ListCommand
        list_command = ListCommand(self.io)
        return list_command.execute(list_args)
