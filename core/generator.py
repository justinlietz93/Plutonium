"""
Dependency report generator module.

This module provides functionality to generate a comprehensive dependency report
based on the configuration and supported environments.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv

# Use absolute imports for PyInstaller compatibility
from plutonium.core.factory import DependencyAnalyzerFactory
from plutonium.core.config_validator import ConfigValidator
from plutonium.core.report_formatter import ReportFormatter
# Assuming constants are now in plutonium.core
from plutonium.core.constants import DEFAULT_OUTPUT_FILE, VULNCHECK_API_TOKEN_ENV_VAR
from plutonium.core.exceptions import DependencyAnalyzerError, ConfigurationError, ParsingError
from plutonium.core.cache import VersionCache


class DependencyReportGenerator:
    """Facade for generating dependency reports."""

    def __init__(self, default_output_file: str = DEFAULT_OUTPUT_FILE):
        """
        Initialize the generator with a default output file.

        Args:
            default_output_file: The default path for the output report file
        """
        self.default_output_file = default_output_file
        self.logger = logging.getLogger("generator")
        self.formatter = ReportFormatter()  # Initialize the report formatter

    def generate_report(self, config_path: str) -> None:
        """
        Generate a dependency report based on the provided configuration.

        Args:
            config_path: The path to the configuration file

        Raises:
            ConfigurationError: If there's an error with the configuration
            DependencyAnalyzerError: If there's an error during report generation
        """
        try:
            self.logger.info(f"Starting dependency report generation using config: {config_path}")

            # Load environment variables from .env file
            # This will load VULNCHECK_API_TOKEN if it's in the .env file
            loaded_env = load_dotenv()
            self.logger.debug(f"Loaded environment variables from .env file: {loaded_env}")

            # Check for VulnCheck API Token (primarily from environment, fallback from .env)
            vulncheck_api_token = os.getenv(VULNCHECK_API_TOKEN_ENV_VAR)
            if vulncheck_api_token:
                self.logger.info(f"VulnCheck API token found via environment variable {VULNCHECK_API_TOKEN_ENV_VAR}.")
            elif loaded_env:
                 # Check again if dotenv loaded it but it wasn't previously set in env
                 vulncheck_api_token = os.getenv(VULNCHECK_API_TOKEN_ENV_VAR)
                 if vulncheck_api_token:
                     self.logger.info(f"VulnCheck API token found via .env file ({VULNCHECK_API_TOKEN_ENV_VAR}).")

            if not vulncheck_api_token:
                self.logger.warning(
                    f"{VULNCHECK_API_TOKEN_ENV_VAR} not found in environment or .env file. "
                    "Vulnerability information will not be available."
                )
                # Proceed without token, analyzers should handle this gracefully

            # Read and parse configuration file
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                raise ConfigurationError(f"Error reading configuration file: {str(e)}")

            # Validate configuration
            ConfigValidator.validate(config)

            # Get output file path from config or use default, resolve relative to executable
            output_file_rel = config.get("OutputFile", self.default_output_file)
            if getattr(sys, 'frozen', False):  # Running as executable
                base_path = os.path.dirname(sys.executable)
                self.output_file = str(Path(base_path) / output_file_rel)
            else: # Running as script
                 # Resolve relative to the current working directory or config file location
                 # Let's use CWD for simplicity, adjust if needed
                 self.output_file = str(Path.cwd() / output_file_rel)
            self.logger.debug(f"Resolved output file path: {self.output_file}")

            # Create a shared cache for all analyzers with the configured cache file
            cache_file_rel = config.get("CacheFile", "version_cache.json")
            # Resolve cache file path similar to output file
            if getattr(sys, 'frozen', False):
                cache_file = str(Path(base_path) / cache_file_rel)
            else:
                 cache_file = str(Path.cwd() / cache_file_rel)
            cache = VersionCache(cache_file)

            # Initialize report file with header
            self._initialize_report(self.output_file)

            # Process each directory
            processed_directories = set()
            for directory_config in config["Directories"]:
                directory = directory_config["Path"]
                environments = directory_config["Environments"]

                # Resolve directory path relative to config file or CWD? Let's assume relative to CWD.
                # If config paths are absolute, this won't hurt.
                directory_path = Path(directory).resolve()
                directory = str(directory_path)


                # Skip if already processed
                if directory in processed_directories:
                    self.logger.warning(f"Directory {directory} already processed, skipping duplicate entry")
                    continue

                self.logger.info(f"Processing directory: {directory}")
                processed_directories.add(directory)

                # Verify directory exists
                if not directory_path.exists():
                    self.logger.warning(f"Directory not found: {directory}, skipping")
                    self._append_error_to_report(self.output_file, f"Directory not found: {directory}")
                    continue

                # Create analyzers for this directory (pass cache, token is read by factory)
                analyzers = DependencyAnalyzerFactory.create_analyzers(
                    directory, environments, cache
                )

                if not analyzers:
                    self.logger.warning(f"No applicable analyzers found or dependency files missing for {directory}, skipping")
                    continue

                # Run each analyzer
                for analyzer in analyzers:
                    try:
                        self.logger.info(f"Running {analyzer.environment_name} analyzer on {directory}")
                        # Get the raw dependency data from the analyzer
                        # No need to pass output_file here based on current structure
                        dependency_info = analyzer.analyze_dependencies(directory)

                        # Format the data as Markdown
                        markdown_content = self.formatter.format_markdown_section(
                            analyzer.environment_name, directory, dependency_info
                        )
                        # Write the formatted content to the report file
                        self.formatter.write_to_report(self.output_file, markdown_content)
                        self.logger.info(f"{analyzer.environment_name} dependency analysis for {directory} completed")
                    except Exception as e:
                        # Catch specific exceptions if needed (ParsingError, NetworkError, etc.)
                        self.logger.error(
                            f"Error analyzing {analyzer.environment_name} dependencies in {directory}: {str(e)}",
                            exc_info=True # Log traceback for unexpected errors
                        )
                        self._append_error_to_report(
                            self.output_file,
                            f"Error analyzing {analyzer.environment_name} dependencies in {directory}: {str(e)}"
                        )

            # Write report footer
            self._finalize_report(self.output_file)

            self.logger.info(f"Dependency report generation completed: {self.output_file}")

        except DependencyAnalyzerError as e:
            self.logger.exception(f"Error generating dependency report: {str(e)}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error generating dependency report: {str(e)}")
            raise DependencyAnalyzerError(f"Unexpected error: {str(e)}")

    def _initialize_report(self, output_file: str) -> None:
        """Initialize the report file with a header."""
        try:
            # Ensure output directory exists
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)

            header = (
                "# Dependency Analysis Report\n\n"
                f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "This report shows the current and latest versions of dependencies across projects, "
                "along with known vulnerabilities from VulnCheck.\n\n"
                "---\n\n"
            )
            self.formatter.write_to_report(output_file, header, mode='w')
        except IOError as e:
            raise DependencyAnalyzerError(f"Error initializing report file '{output_file}': {str(e)}")
        except Exception as e:
             raise DependencyAnalyzerError(f"Unexpected error initializing report file '{output_file}': {str(e)}")

    def _append_error_to_report(self, output_file: str, error_message: str) -> None:
        """Append an error message to the report."""
        try:
            error_content = f"\n## Error\n\n```\n{error_message}\n```\n\n---\n\n"
            self.formatter.write_to_report(output_file, error_content)
        except IOError as e:
            self.logger.error(f"Error appending to report file '{output_file}': {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error appending to report file '{output_file}': {str(e)}")

    def _finalize_report(self, output_file: str) -> None:
        """Finalize the report with a footer, adding skip reason if applicable."""
        try:
            # Use the exact legend provided by the user in the last message
            footer = (
                "\n## Report Summary\n\n"
                "- ✅ = Up to date\n"
                "- ⚠️= Update available\n"
                "- 🛑 = Vulnerabilities found (or Error checking)\n"
                "- ⚙️ = Variable version\n"                           # Added Gear
                "- Error / N/A = Error or Skipped Check\n\n"         # Combined Error/NA
            )

            # Check if vulnerability checks were skipped and add reason
            if hasattr(self, 'vulnerability_checker') and self.vulnerability_checker and self.vulnerability_checker.skip_reason:
                 # Add the skip reason if it exists (e.g., "Token Missing", "402 Payment Required")
                 footer += f"**Note:** Vulnerability checks skipped: ({self.vulnerability_checker.skip_reason})\n\n"

            footer += (
                "---\n\n"
                "Report complete.\n"
            )
            # Assuming self.formatter exists and works
            self.formatter.write_to_report(output_file, footer)
        except IOError as e:
            self.logger.error(f"Error finalizing report file '{output_file}': {str(e)}")
        except Exception as e:
             self.logger.error(f"Unexpected error finalizing report file '{output_file}': {str(e)}", exc_info=True)