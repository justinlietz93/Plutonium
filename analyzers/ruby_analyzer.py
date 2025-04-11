"""
Ruby dependency analyzer module.

This module provides functionality to analyze dependencies in Ruby projects.
"""

import re
import os
import requests
import logging
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .interface import IDependencyAnalyzer
from ..core.constants import API_URLS, DEFAULT_TIMEOUT
from ..core.exceptions import run_command, CommandExecutionError, NetworkError, ParsingError
from ..core.cache import VersionCache


class RubyAnalyzer(IDependencyAnalyzer):
    """Analyzer for Ruby dependencies."""
    
    @property
    def environment_name(self) -> str:
        """Get the environment name."""
        return "Ruby"
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to Gemfile in the specified directory.
        
        Args:
            directory: The directory to search for Gemfile
            
        Returns:
            The Path object for Gemfile
            
        Raises:
            FileNotFoundError: If Gemfile doesn't exist
        """
        gemfile_path = Path(directory) / "Gemfile"
        if not gemfile_path.exists():
            raise FileNotFoundError(f"Gemfile not found in {directory}")
        return gemfile_path
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse Gemfile and extract the dependencies.
        
        Args:
            file_path: The path to Gemfile
            
        Returns:
            A dictionary mapping gem names to their current versions
            
        Raises:
            ParsingError: If there's an error parsing Gemfile
        """
        try:
            dependencies = {}
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all gem declarations
            # This is a simple regex that might not handle all Gemfile formats
            # but should cover the most common cases
            gem_pattern = r"gem\s+['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?"
            matches = re.findall(gem_pattern, content)
            
            for match in matches:
                gem_name = match[0]
                gem_version = match[1] if len(match) > 1 and match[1] else "Not specified"
                
                # Clean up version specifier
                if gem_version.startswith(('~>', '>=', '<=', '>', '<', '=')):
                    # Extract version from specifier
                    version_match = re.search(r'[\d\.]+', gem_version)
                    if version_match:
                        gem_version = version_match.group(0)
                
                dependencies[gem_name] = gem_version
            
            return dependencies
            
        except IOError as e:
            raise ParsingError(f"Error parsing Gemfile: {str(e)}")
    
    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a RubyGems package.
        
        Args:
            package_name: The name of the RubyGems package
            
        Returns:
            The latest version as a string
            
        Raises:
            NetworkError: If there's an issue fetching the latest version
            ValueError: If the package doesn't exist or another error occurs
        """
        # Check cache first
        cache_key = f"rubygems:{package_name}"
        cached_version = self.cache.get(cache_key)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version
        
        # Not in cache, fetch from RubyGems
        url = API_URLS['RubyGems'].format(package=package_name)
        self.logger.debug(f"Fetching latest version for {package_name} from {url}")
        
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            if 'version' in data:
                latest_version = data['version']
                
                # Update cache
                self.cache.set(cache_key, latest_version)
                
                return latest_version
            else:
                raise ValueError(f"Unable to determine latest version for {package_name}")
                
        except requests.RequestException as e:
            raise NetworkError(f"Error fetching latest version for {package_name}: {str(e)}")
        except (ValueError, KeyError) as e:
            raise ValueError(f"Error processing RubyGems response for {package_name}: {str(e)}")
    
    def analyze_dependencies(self, directory: str, output_file: str) -> None:
        """
        Analyze Ruby dependencies in the specified directory.
        
        Args:
            directory: The directory containing Gemfile
            output_file: The path to the output file where results will be written
            
        Raises:
            FileNotFoundError: If Gemfile doesn't exist
            ParsingError: If there's an error parsing Gemfile
        """
        try:
            self.logger.info(f"Analyzing Ruby dependencies in {directory}")
            
            # Get dependency file path
            gemfile_path = self._get_dependency_file_path(directory)
            
            # Parse dependencies
            dependencies = self._parse_dependencies(gemfile_path)
            
            if not dependencies:
                self.logger.info(f"No dependencies found in {directory}")
                # Write empty section to report
                content = self.format_markdown_section(directory, [])
                self.write_to_report(output_file, content)
                return
            
            self.logger.info(f"Found {len(dependencies)} dependencies")
            
            # Get latest versions
            dependencies_with_latest = self._get_installed_dependencies_with_latest(dependencies)
            
            # Format and write to report
            content = self.format_markdown_section(directory, dependencies_with_latest)
            self.write_to_report(output_file, content)
            
            self.logger.info(f"Ruby dependency analysis for {directory} completed")
            
        except Exception as e:
            self.logger.error(f"Error analyzing Ruby dependencies in {directory}: {str(e)}")
            # Write error to report
            error_content = f"## Ruby Dependencies in {directory}\n\n"
            error_content += f"Error analyzing dependencies: {str(e)}\n\n"
            self.write_to_report(output_file, error_content)
            raise
