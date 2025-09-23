"""
Plotting commands (plot-ts, plot-profile, plot-series).
"""

import argparse
from ...core.exceptions import ValidationError
from .base import BaseCommand, CommandResult


class PlotTSCommand(BaseCommand):
    """Handle T-S diagram plotting with lazy loading."""

    def execute(self, args: argparse.Namespace) -> CommandResult:
        """Execute plot-ts command."""
        try:
            # Validate dot size
            if args.dot_size and (args.dot_size < 1 or args.dot_size > 200):
                raise ValidationError("--dot-size must be between 1 and 200")

            # Load required dependencies
            data_deps = self.deps.get_data_dependencies()
            plot_deps = self.deps.get_plot_dependencies()

            # Read data
            data = self.io.read_data(args.input, args.input_format, args.header_input)

            if not data:
                raise ValidationError('No data found in file.')

            # Create plotter
            ts_diagram_plotter = plot_deps['plotters'].TsDiagramPlotter
            plotter = ts_diagram_plotter(data)

            # Plot with options
            plotter.plot(
                output_file=args.output,
                title=args.title,
                dot_size=args.dot_size,
                use_colormap=(not args.no_colormap),
                show_density_isolines=(not args.no_isolines),
                colormap=args.colormap,
                show_lines_between_dots=(not args.no_lines_between_dots),
                show_grid=(not args.no_grid)
            )

            message = "T-S diagram plotted successfully"
            if args.output:
                message += f" and saved to {args.output}"

            return CommandResult(success=True, message=message)

        except Exception as e:
            return CommandResult(success=False, message=str(e))


class PlotProfileCommand(BaseCommand):
    """Handle profile plotting with lazy loading."""

    def execute(self, args: argparse.Namespace) -> CommandResult:
        """Execute plot-profile command."""
        try:
            # Load required dependencies
            data_deps = self.deps.get_data_dependencies()
            plot_deps = self.deps.get_plot_dependencies()

            # Read data
            data = self.io.read_data(args.input, args.input_format, args.header_input)

            if not data:
                raise ValidationError('No data found in file.')

            # Create plotter
            profile_plotter = plot_deps['plotters'].ProfilePlotter
            plotter = profile_plotter(data)

            # Plot with options
            plotter.plot(
                output_file=args.output,
                title=args.title,
                dot_size=args.dot_size,
                show_lines_between_dots=(not args.no_lines_between_dots),
                show_grid=(not args.no_grid)
            )

            message = "Profile plotted successfully"
            if args.output:
                message += f" and saved to {args.output}"

            return CommandResult(success=True, message=message)

        except Exception as e:
            return CommandResult(success=False, message=str(e))


class PlotSeriesCommand(BaseCommand):
    """Handle time series plotting with lazy loading."""

    def execute(self, args: argparse.Namespace) -> CommandResult:
        """Execute plot-series command."""
        try:
            # Load required dependencies
            data_deps = self.deps.get_data_dependencies()
            plot_deps = self.deps.get_plot_dependencies()

            # Read data
            data = self.io.read_data(args.input, args.input_format, args.header_input)

            if not data:
                raise ValidationError('No data found in file.')

            # Parse parameters
            parameters = self._parse_parameters(args.parameter)

            # Choose appropriate plotter
            if len(parameters) == 1:
                # Single parameter - use TimeSeriesPlotter
                time_series_plotter = plot_deps['plotters'].TimeSeriesPlotter
                plotter = time_series_plotter(data)
                plotter.plot(parameter_name=parameters[0], output_file=args.output)
            else:
                # Multiple parameters - use TimeSeriesPlotterMulti
                time_series_plotter_multi = plot_deps['plotters'].TimeSeriesPlotterMulti
                plotter = time_series_plotter_multi(data)

                # Plot with options
                plotter.plot(
                    parameter_names=parameters,
                    output_file=args.output,
                    dual_axis=getattr(args, 'dual_axis', False),
                    normalize=getattr(args, 'normalize', False),
                    colors=getattr(args, 'colors', None),
                    line_styles=getattr(args, 'line_styles', None)
                )

            message = f"Time series plot for {', '.join(parameters)} created successfully"
            if args.output:
                message += f" and saved to {args.output}"

            return CommandResult(success=True, message=message)

        except Exception as e:
            return CommandResult(success=False, message=str(e))
