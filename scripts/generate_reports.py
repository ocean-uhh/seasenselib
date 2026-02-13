#!/usr/bin/env python3
"""
Generate comprehensive dataset reports for SeaSenseLib processed data.

This script processes oceanographic data files through the SeaSenseLib pipeline
and generates detailed RST reports documenting variable mappings, metadata changes,
and processing protocols for documentation purposes.

Example:
    python scripts/generate_reports.py examples/MSM121_054_1db.cnv -o docs/source/reports
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import seasenselib as ssl


def generate_single_report(
    input_file: str,
    output_dir: Path,
    pipeline_profile: str = 'default',
    include_plot: bool = True,
    title: Optional[str] = None
) -> Path:
    """
    Generate a report for a single data file.
    
    Parameters
    ----------
    input_file : str
        Path to the input data file
    output_dir : Path
        Directory to write the report
    pipeline_profile : str, default='default'
        Pipeline profile to use for processing
    include_plot : bool, default=True
        Whether to include plots in the report
    title : str, optional
        Custom report title
        
    Returns
    -------
    Path
        Path to the generated report file
    """
    input_path = Path(input_file)
    print(f"Processing {input_path.name}...")
    
    # Process the file with SeaSenseLib pipeline (capture metadata for variable mappings)
    try:
        # Auto-detect header file and format for Aquadopp/Nortek ASCII files
        header_file = None
        file_format = None
        if input_path.suffix.lower() == '.dat':
            # Look for corresponding .hdr file with same name
            potential_header = input_path.with_suffix('.hdr')
            if potential_header.exists():
                header_file = str(potential_header)
                file_format = 'nortek-ascii'  # Explicitly set format for Nortek ASCII
                print(f"  Found header file: {potential_header.name}")
                print(f"  Using format: {file_format}")
        
        dataset, metadata = ssl.read(
            str(input_path),
            header_file=header_file,
            file_format=file_format,
            pipeline_profile=pipeline_profile,
            return_metadata=True
        )
    except Exception as e:
        print(f"  Error reading {input_path.name}: {e}")
        raise
    
    # Generate output filename
    report_filename = f"{input_path.stem}_report.rst"
    output_file = output_dir / report_filename
    
    # Set report title if not provided
    if title is None:
        title = f"{input_path.stem} Dataset Report"
    
    # Write the report using direct ReportWriter instantiation
    try:
        from seasenselib.writers.report_writer import ReportWriter
        writer = ReportWriter(dataset)
        writer.write(
            str(output_file),
            title=title,
            include_plot=include_plot,
            plot_output_dir=str(output_dir / 'plots') if include_plot else None,
            processing_metadata=metadata
        )
        
        print(f"  Report written to: {output_file}")
        return output_file
        
    except Exception as e:
        print(f"  Error generating report for {input_path.name}: {e}")
        raise


def generate_batch_reports(
    input_files: List[str],
    output_dir: Path,
    pipeline_profile: str = 'default',
    include_plots: bool = True
) -> List[Path]:
    """
    Generate reports for multiple data files.
    
    Parameters
    ----------
    input_files : List[str]
        Paths to input data files
    output_dir : Path
        Directory to write reports
    pipeline_profile : str, default='default'
        Pipeline profile to use for processing
    include_plots : bool, default=True
        Whether to include plots in reports
        
    Returns
    -------
    List[Path]
        Paths to generated report files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_reports = []
    
    print(f"Generating reports for {len(input_files)} files...")
    print(f"Pipeline profile: {pipeline_profile}")
    print(f"Output directory: {output_dir}")
    
    for input_file in input_files:
        try:
            report_path = generate_single_report(
                input_file,
                output_dir,
                pipeline_profile=pipeline_profile,
                include_plot=include_plots
            )
            generated_reports.append(report_path)
            
        except Exception as e:
            print(f"Failed to process {input_file}: {e}")
            continue
    
    return generated_reports


def discover_data_files(search_dir: Path, extensions: Optional[List[str]] = None) -> List[Path]:
    """
    Discover oceanographic data files in a directory.
    
    Parameters
    ----------
    search_dir : Path
        Directory to search for data files
    extensions : List[str], optional
        File extensions to look for. If None, uses common oceanographic formats.
        
    Returns
    -------
    List[Path]
        List of discovered data files
    """
    if extensions is None:
        # Common oceanographic file extensions
        extensions = ['.cnv', '.rsk', '.nc', '.mat', '.txt', '.asc', '.csv']
    
    discovered = []
    for ext in extensions:
        discovered.extend(search_dir.glob(f"**/*{ext}"))
    
    return sorted(discovered)


def main():
    """Main script entry point."""
    parser = argparse.ArgumentParser(
        description='Generate SeaSenseLib dataset reports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate report for single file
  python generate_reports.py examples/profile.cnv
  
  # Generate reports for multiple files
  python generate_reports.py examples/*.cnv examples/*.rsk
  
  # Use full pipeline processing
  python generate_reports.py examples/profile.cnv --pipeline-profile full
  
  # Disable plots in reports (plots are included by default)
  python generate_reports.py examples/*.cnv --no-plots
  
  # Auto-discover files in examples directory
  python generate_reports.py --discover examples/
        """
    )
    
    parser.add_argument(
        'files',
        nargs='*',
        help='Input data files to process'
    )
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('docs/source/reports'),
        help='Output directory for reports (default: docs/source/reports)'
    )
    parser.add_argument(
        '--pipeline-profile', '-p',
        default='default',
        choices=['minimal', 'default', 'full'],
        help='Pipeline profile to use for processing (default: default)'
    )
    parser.add_argument(
        '--no-plots',
        action='store_true',
        help='Disable plot generation in reports'
    )
    parser.add_argument(
        '--discover', '-d',
        type=Path,
        help='Auto-discover data files in specified directory'
    )
    parser.add_argument(
        '--extensions',
        nargs='+',
        default=['.cnv', '.rsk', '.nc', '.mat', '.txt'],
        help='File extensions to discover (default: .cnv .rsk .nc .mat .txt)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Suppress SeaSenseLib logging during processing
    logging.getLogger('seasenselib').setLevel(logging.INFO)
    logging.getLogger('pycnv').setLevel(logging.INFO)
    
    # Determine input files
    input_files = []
    
    if args.discover:
        # Auto-discover files in directory
        if not args.discover.exists():
            print(f"Error: Discovery directory does not exist: {args.discover}")
            sys.exit(1)
        
        discovered = discover_data_files(args.discover, args.extensions)
        input_files.extend(str(f) for f in discovered)
        print(f"Discovered {len(discovered)} files in {args.discover}")
        
    if args.files:
        # Add explicitly specified files
        for file_pattern in args.files:
            file_path = Path(file_pattern)
            if file_path.exists():
                input_files.append(str(file_path))
            else:
                # Try glob expansion
                from glob import glob
                matches = glob(file_pattern)
                if matches:
                    input_files.extend(matches)
                else:
                    print(f"Warning: No files found matching {file_pattern}")
    
    if not input_files:
        print("Error: No input files specified or discovered.")
        print("Use --discover <directory> to auto-discover files, or specify files directly.")
        sys.exit(1)
    
    # Generate reports
    try:
        generated_reports = generate_batch_reports(
            input_files,
            args.output_dir,
            pipeline_profile=args.pipeline_profile,
            include_plots=not args.no_plots  # Invert the flag
        )
        
        print(f"\nSuccessfully generated {len(generated_reports)} reports:")
        for report_path in generated_reports:
            print(f"  {report_path}")
            
        print(f"\nReports saved to: {args.output_dir}")
        
        # Note: plots are now generated by default  
        print(f"Plots saved to: {args.output_dir / 'plots'}")
            
    except KeyboardInterrupt:
        print("\nReport generation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error during report generation: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()