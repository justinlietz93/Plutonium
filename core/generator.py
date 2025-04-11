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

from .factory import DependencyAnalyzerFactory
from .config_validator import ConfigValidator
from .constants import DEFAULT_OUTPUT_FILE
from .exceptions import DependencyAnalyzerError, ConfigurationError, ParsingError
from .cache import VersionCache


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
                    directory, environments, cache
                )
                
                if not analyzers:
                    self.logger.warning(f"No applicable analyzers for {directory}, skipping")
                    continue
                
                # Run each analyzer
                for analyzer in analyzers:
                    try:
                        self.logger.info(f"Running {analyzer.environment_name} analyzer on {directory}")
                        analyzer.analyze_dependencies(directory, output_file)
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
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# Dependency Analysis Report\n\n")
                f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("This report shows the current and latest versions of dependencies across projects.\n\n")
                f.write("---\n\n")
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
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"\n## Error\n\n{error_message}\n\n---\n\n")
        except IOError as e:
            self.logger.error(f"Error appending to report file: {str(e)}")
    
    def _finalize_report(self, output_file: str) -> None:
        """
        Finalize the report with a footer.
        
        Args:
            output_file: The path to the output file
        """
        try:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("\n## Report Summary\n\n")
                f.write("- ✅ = Up to date\n")
                f.write("- ⚠️ = Update available\n\n")
                f.write("---\n\n")
                f.write("Report complete.\n")
        except IOError as e:
            self.logger.error(f"Error finalizing report file: {str(e)}")