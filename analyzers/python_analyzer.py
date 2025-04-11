"""
Python dependency analyzer module.

This module provides functionality to analyze dependencies in Python projects.
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


class PythonAnalyzer(IDependencyAnalyzer):
    """Analyzer for Python dependencies."""
    
    @property
    def environment_name(self) -> str:
        """Get the environment name."""
        return "Python"
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to requirements.txt in the specified directory.
        
        Args:
            directory: The directory to search for requirements.txt
            
        Returns:
            The Path object for requirements.txt
            
        Raises:
            FileNotFoundError: If requirements.txt doesn't exist
        """
        requirements_path = Path(directory) / "requirements.txt"
        if not requirements_path.exists():
            raise FileNotFoundError(f"requirements.txt not found in {directory}")
        return requirements_path
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse requirements.txt and extract the dependencies.
        
        Args:
            file_path: The path to requirements.txt
            
        Returns:
            A dictionary mapping package names to their current versions
            
        Raises:
            ParsingError: If there's an error parsing requirements.txt
        """
        try:
            dependencies = {}
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Skip comments and empty lines
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Skip Git/URL dependencies
                    if line.startswith(('git+', 'http://', 'https://')):
                        continue
                    
                    # Skip options and editable installs
                    if line.startswith(('-', '--')):
                        continue
                    if line.startswith('-e '):
                        continue
                    
                    # Handle package with version specifier
                    # Various formats: package==1.0.0, package>=1.0.0, package~=1.0.0
                    match = re.match(r'^([a-zA-Z0-9_\-\.]+)(?:[<>=~!]+)([a-zA-Z0-9_\-\.]+)', line)
                    if match:
                        package, version = match.groups()
                        dependencies[package.lower()] = version
                    else:
                        # Package with no version specified
                        dependencies[line.lower()] = "Not specified"
            
            return dependencies
            
        except IOError as e:
            raise ParsingError(f"Error parsing requirements.txt: {str(e)}")
    
    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a PyPI package.
        
        Args:
            package_name: The name of the PyPI package
            
        Returns:
            The latest version as a string
            
        Raises:
            NetworkError: If there's an issue fetching the latest version
            ValueError: If the package doesn't exist or another error occurs
        """
        # Normalize package name (PyPI is case-insensitive)
        package_name = package_name.lower()
        
        # Check cache first
        cache_key = f"pypi:{package_name}"
        cached_version = self.cache.get(cache_key)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version
        
        # Not in cache, fetch from PyPI
        url = API_URLS['PyPI'].format(package=package_name)
        self.logger.debug(f"Fetching latest version for {package_name} from {url}")
        
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            if 'info' in data and 'version' in data['info']:
                latest_version = data['info']['version']
                
                # Update cache
                self.cache.set(cache_key, latest_version)
                
                return latest_version
            else:
                raise ValueError(f"Unable to determine latest version for {package_name}")
                
        except requests.RequestException as e:
            raise NetworkError(f"Error fetching latest version for {package_name}: {str(e)}")
        except (ValueError, KeyError) as e:
            raise ValueError(f"Error processing PyPI response for {package_name}: {str(e)}")
    
    def _get_installed_dependencies_with_latest(self, dependencies: Dict[str, str]) -> List[Tuple[str, str, str]]:
        """
        Get the latest versions for all dependencies.
        
        Args:
            dependencies: A dictionary mapping package names to their current versions
            
        Returns:
            A list of tuples (package_name, current_version, latest_version)
        """
        result = []
        
        # Use ThreadPoolExecutor to fetch latest versions concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Create a future for each dependency
            future_to_package = {
                executor.submit(self.get_latest_version, package): (package, current_version)
                for package, current_version in dependencies.items()
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_package):
                package, current_version = future_to_package[future]
                try:
                    latest_version = future.result()
                    result.append((package, current_version, latest_version))
                except Exception as e:
                    self.logger.error(f"Error getting latest version for {package}: {str(e)}")
                    # Include in the result with an error indicator
                    result.append((package, current_version, "Error fetching"))
        
        return result
    
    def analyze_dependencies(self, directory: str, output_file: str) -> None:
        """
        Analyze Python dependencies in the specified directory.
        
        Args:
            directory: The directory containing requirements.txt
            output_file: The path to the output file where results will be written
            
        Raises:
            FileNotFoundError: If requirements.txt doesn't exist
            ParsingError: If there's an error parsing requirements.txt
        """
        try:
            self.logger.info(f"Analyzing Python dependencies in {directory}")
            
            # Get dependency file path
            requirements_path = self._get_dependency_file_path(directory)
            
            # Parse dependencies
            dependencies = self._parse_dependencies(requirements_path)
            
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
            
            self.logger.info(f"Python dependency analysis for {directory} completed")
            
        except Exception as e:
            self.logger.error(f"Error analyzing Python dependencies in {directory}: {str(e)}")
            # Write error to report
            error_content = f"## Python Dependencies in {directory}\n\n"
            error_content += f"Error analyzing dependencies: {str(e)}\n\n"
            self.write_to_report(output_file, error_content)
            raise
