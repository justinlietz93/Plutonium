"""
Dependency Report Generator module.

This module provides the main facade for generating dependency reports
by coordinating the various components of the dependency analyzer.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv

# Use absolute imports
from plutonium.core.factory import DependencyAnalyzerFactory
from plutonium.core.config_validator import ConfigValidator
from plutonium.core.constants import DEFAULT_OUTPUT_FILE
from plutonium.core.exceptions import DependencyAnalyzerError, ConfigurationError, ParsingError
from plutonium.core.cache import VersionCache
from plutonium.core.report_formatter import ReportFormatter  # New import


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
            
            # Load environment variables from .env file (kept for potential future use)
            load_dotenv()
            self.logger.debug("Loaded environment variables from .env file")
            
            # Read and parse configuration file
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                raise ConfigurationError(f"Error reading configuration file: {str(e)}")
            
            # Validate configuration
            ConfigValidator.validate(config)
            
            # Get output file path from config or use default, resolve relative to executable
            output_file = config.get("OutputFile", self.default_output_file)
            if getattr(sys, 'frozen', False):  # Running as executable
                base_path = os.path.dirname(sys.executable)
                output_file = str(Path(base_path) / output_file)
            self.logger.debug(f"Resolved output file path: {output_file}")
            
            # Get NVD API key from environment variable (not used with VulnCheck, kept for compatibility)
            nvd_api_key = os.getenv("NVD_API_KEY")
            self.logger.debug(f"NVD_API_KEY environment variable value: {nvd_api_key}")
            if nvd_api_key:
                self.logger.info("NVD API key found in environment variable NVD_API_KEY (not used with VulnCheck NVD++)")
            
            # Create a shared cache for all analyzers with the configured cache file
            cache_file = config.get("CacheFile", "version_cache.json")
            cache = VersionCache(cache_file)
            
            # Initialize report file with header
            self._initialize_report(output_file)
            
            # Process each directory
            processed_directories = set()
            for directory_config in config["Directories"]:
                directory = directory_config["Path"]
                environments = directory_config["Environments"]
                
                # Skip if already processed
                if directory in processed_directories:
                    self.logger.warning(f"Directory {directory} already processed, skipping duplicate entry")
                    continue
                
                self.logger.info(f"Processing directory: {directory}")
                processed_directories.add(directory)
                
                # Verify directory exists
                if not Path(directory).exists():
                    self.logger.warning(f"Directory not found: {directory}, skipping")
                    self._append_error_to_report(output_file, f"Directory not found: {directory}")
                    continue
                
                # Create analyzers for this directory
                analyzers = DependencyAnalyzerFactory.create_analyzers(
                    directory, environments, cache, nvd_api_key=nvd_api_key
                )
                
                if not analyzers:
                    self.logger.warning(f"No applicable analyzers for {directory}, skipping")
                    continue
                
                # Run each analyzer
                for analyzer in analyzers:
                    try:
                        self.logger.info(f"Running {analyzer.environment_name} analyzer on {directory}")
                        # Get the raw dependency data from the analyzer
                        dependency_info = analyzer.analyze_dependencies(directory)
                        # Format the data as Markdown
                        markdown_content = self.formatter.format_markdown_section(
                            analyzer.environment_name, directory, dependency_info
                        )
                        # Write the formatted content to the report file
                        self.formatter.write_to_report(output_file, markdown_content)
                        self.logger.info(f"{analyzer.environment_name} dependency analysis for {directory} completed")
                    except Exception as e:
                        self.logger.error(
                            f"Error analyzing {analyzer.environment_name} dependencies in {directory}: {str(e)}"
                        )
                        self._append_error_to_report(
                            output_file,
                            f"Error analyzing {analyzer.environment_name} dependencies in {directory}: {str(e)}"
                        )
            
            # Write report footer
            self._finalize_report(output_file)
            
            self.logger.info(f"Dependency report generation completed: {output_file}")
            
        except DependencyAnalyzerError as e:
            self.logger.exception(f"Error generating dependency report: {str(e)}")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error generating dependency report: {str(e)}")
            raise DependencyAnalyzerError(f"Unexpected error: {str(e)}")
    
    def _initialize_report(self, output_file: str) -> None:
        """
        Initialize the report file with a header.
        
        Args:
            output_file: The path to the output file
        """
        try:
            # Use the formatter to write the header
            header = (
                "# Dependency Analysis Report\n\n"
                f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "This report shows the current and latest versions of dependencies across projects.\n\n"
                "---\n\n"
            )
            self.formatter.write_to_report(output_file, header, mode='w')
        except IOError as e:
            raise DependencyAnalyzerError(f"Error initializing report file: {str(e)}")
    
    def _append_error_to_report(self, output_file: str, error_message: str) -> None:
        """
        Append an error message to the report.
        
        Args:
            output_file: The path to the output file
            error_message: The error message to append
        """
        try:
            error_content = f"\n## Error\n\n{error_message}\n\n---\n\n"
            self.formatter.write_to_report(output_file, error_content)
        except IOError as e:
            self.logger.error(f"Error appending to report file: {str(e)}")
    
    def _finalize_report(self, output_file: str) -> None:
        """
        Finalize the report with a footer.
        
        Args:
            output_file: The path to the output file
        """
        try:
            footer = (
                "\n## Report Summary\n\n"
                "- ✅ = Up to date\n"
                "- ⬆️ = Update available\n\n"
                "---\n\n"
                "Report complete.\n"
            )
            self.formatter.write_to_report(output_file, footer)
        except IOError as e:
            self.logger.error(f"Error finalizing report file: {str(e)}")