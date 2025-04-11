#!/usr/bin/env python3
"""
Dependency Analyzer Tool

This is the main entry point for the dependency analyzer tool, which analyzes
dependencies across multiple programming environments and generates a report
comparing current versions with the latest available versions.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from core.generator import DependencyReportGenerator
from core.logging import setup_logging
from core.constants import DEFAULT_OUTPUT_FILE
from core.exceptions import DependencyAnalyzerError, ConfigurationError


def main():
    """Main entry point for the dependency analyzer tool."""
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Analyze dependencies across multiple programming environments")
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Path to the configuration file (default: config.json)"
    )
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Path to the output report file (default: {DEFAULT_OUTPUT_FILE})"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)
    
    logger = logging.getLogger("main")
    logger.info("Dependency Analyzer starting...")
    
    try:
        # Check if config file exists
        config_path = Path(args.config)
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        # Create and run the report generator
        generator = DependencyReportGenerator(default_output_file=args.output)
        generator.generate_report(str(config_path))
        
        # Print success message
        print(f"\nDependency analysis completed successfully.")
        print(f"Report saved to: {args.output}")
        return 0
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        print(f"\nConfiguration error: {str(e)}")
        print("Please check your configuration file and try again.")
        return 1
        
    except DependencyAnalyzerError as e:
        logger.error(f"Error during dependency analysis: {str(e)}")
        print(f"\nError during dependency analysis: {str(e)}")
        print("Check the log file for more details.")
        return 1
        
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        print(f"\nAn unexpected error occurred: {str(e)}")
        print("Check the log file for more details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
