"""
Main entry point for the Dependency Analyzer.

This script initializes logging, parses command-line arguments,
and starts the dependency report generation process.
"""

import argparse
import logging
import sys
from pathlib import Path

# Use absolute imports for PyInstaller compatibility
from plutonium.core.generator import DependencyReportGenerator
from plutonium.core.constants import DEFAULT_CONFIG_FILE, DEFAULT_LOG_FILE


def setup_logging(log_file: str) -> None:
    """
    Set up logging to both a file and the console.
    
    Args:
        log_file: The path to the log file
    """
    # Ensure the log directory exists
    log_path = Path(log_file)
    log_dir = log_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all logs
    
    # Create file handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Console can remain at INFO
    
    # Create formatter
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logging.info("Logging initialized")


def main() -> None:
    """
    Main function to run the Dependency Analyzer.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Dependency Analyzer")
    parser.add_argument(
        "-c", "--config",
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to the configuration file (default: {DEFAULT_CONFIG_FILE})"
    )
    parser.add_argument(
        "-l", "--log",
        default=DEFAULT_LOG_FILE,
        help=f"Path to the log file (default: {DEFAULT_LOG_FILE})"
    )
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log)
    
    # Create the report generator and generate the report
    generator = DependencyReportGenerator()
    try:
        generator.generate_report(args.config)
        logging.info("Dependency analysis completed successfully.")
        logging.info(f"Report saved to: {generator.default_output_file}")
    except Exception as e:
        logging.error(f"Failed to generate dependency report: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()