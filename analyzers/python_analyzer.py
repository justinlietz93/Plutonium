"""
Python dependency analyzer module.

This module provides functionality to analyze Python dependencies
by parsing requirements.txt files and fetching the latest versions.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .interface import IDependencyAnalyzer
from ..core.constants import API_URLS, DEFAULT_TIMEOUT
from ..core.exceptions import run_command, CommandExecutionError, NetworkError, ParsingError
from ..core.cache import VersionCache
import requests


class PythonAnalyzer(IDependencyAnalyzer):
    """Analyzer for Python dependencies."""
    
    @property
    def environment_name(self) -> str:
        return "Python"
    
    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a Python package from PyPI.
        
        Args:
            package_name: The name of the package
            
        Returns:
            The latest version as a string
            
        Raises:
            NetworkError: If there's an issue fetching the latest version
            ValueError: If the package doesn't exist or another error occurs
        """
        # Check cache first
        cached_version = self.cache.get(package_name)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version
        
        # Fetch from PyPI
        url = API_URLS["PyPI"].format(package=package_name)
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            latest_version = data["info"]["version"]
            self.cache.set(package_name, latest_version)
            return latest_version
        except requests.RequestException as e:
            self.logger.error(f"Network error fetching latest version for {package_name}: {str(e)}")
            raise NetworkError(f"Failed to fetch latest version for {package_name}: {str(e)}")
        except (KeyError, ValueError) as e:
            self.logger.error(f"Error parsing PyPI response for {package_name}: {str(e)}")
            raise ValueError(f"Failed to parse latest version for {package_name}: {str(e)}")
    
    def analyze_dependencies(self, directory: str) -> List[Tuple[str, str, str, List[str]]]:
        """
        Analyze Python dependencies in the specified directory and return the results.

        Args:
            directory: The directory containing the requirements.txt file to analyze
            
        Returns:
            A list of tuples (package_name, current_version, latest_version, vulnerabilities)
            
        Raises:
            FileNotFoundError: If the requirements.txt file doesn't exist
            ParsingError: If there's an error parsing the requirements.txt file
            NetworkError: If there's an issue fetching latest versions
        """
        self.logger.info(f"Analyzing Python dependencies in {directory}")
        
        # Find the requirements.txt file
        dependency_file = self._get_dependency_file_path(directory)
        
        # Parse the dependencies
        dependencies = self._parse_dependencies(dependency_file)
        
        # Get the latest versions and vulnerabilities
        dependency_info = self._get_installed_dependencies_with_latest(dependencies)
        
        self.logger.info(f"Found {len(dependency_info)} dependencies")
        return dependency_info
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to the requirements.txt file in the specified directory.
        
        Args:
            directory: The directory to search for the requirements.txt file
            
        Returns:
            The Path object for the requirements.txt file
            
        Raises:
            FileNotFoundError: If the requirements.txt file doesn't exist
        """
        file_path = Path(directory) / "requirements.txt"
        if not file_path.exists():
            self.logger.error(f"requirements.txt not found in {directory}")
            raise FileNotFoundError(f"requirements.txt not found in {directory}")
        return file_path
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse the requirements.txt file and extract the dependencies.
        
        Args:
            file_path: The path to the requirements.txt file
            
        Returns:
            A dictionary mapping package names to their current versions
            
        Raises:
            ParsingError: If there's an error parsing the requirements.txt file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            dependencies = {}
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Handle simple version specifiers (e.g., "package==1.2.3")
                if '==' in line:
                    package, version = line.split('==', 1)
                    package = package.strip()
                    version = version.strip()
                    dependencies[package] = version
                else:
                    # Skip lines without version specifiers
                    continue
            
            return dependencies
        except IOError as e:
            self.logger.error(f"Error reading requirements.txt: {str(e)}")
            raise ParsingError(f"Failed to read requirements.txt: {str(e)}")