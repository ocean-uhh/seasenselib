"""
CTD Tools - Optimized Main Entry Point

This module provides a lightweight entry point for the CTD Tools CLI with lazy loading
of dependencies to improve startup performance. Heavy imports are deferred until needed.
"""

import sys
from .cli.router import CLIRouter


def main():
    """
    Main entry point for the CTD Tools CLI.
    
    This function creates a CLI router and delegates all command handling to it.
    The router implements lazy loading to minimize startup time.
    """
    try:
        router = CLIRouter()
        exit_code = router.route_and_execute(sys.argv[1:])
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
