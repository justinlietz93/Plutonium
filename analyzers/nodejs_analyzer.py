"""
Node.js dependency analyzer module.

This module provides functionality to analyze Node.js dependencies
by parsing package.json files and fetching the latest versions.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .interface import IDependencyAnalyzer
from ..core.constants import API_URLS, DEFAULT_TIMEOUT
from ..core.exceptions import run_command, CommandExecutionError, NetworkError, ParsingError
from ..core.cache import VersionCache
import requests


class NodeJsAnalyzer(IDependencyAnalyzer):
    """Analyzer for Node.js dependencies."""
    
    @property
    def environment_name(self) -> str:
        return "Node.js"
    
    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a Node.js package from npm.
        
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
        
        # Fetch from npm registry
        url = API_URLS["npm"].format(package=package_name)
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            latest_version = data["dist-tags"]["latest"]
            self.cache.set(package_name, latest_version)
            return latest_version
        except requests.RequestException as e:
            self.logger.error(f"Network error fetching latest version for {package_name}: {str(e)}")
            raise NetworkError(f"Failed to fetch latest version for {package_name}: {str(e)}")
        except (KeyError, ValueError) as e:
            self.logger.error(f"Error parsing npm response for {package_name}: {str(e)}")
            raise ValueError(f"Failed to parse latest version for {package_name}: {str(e)}")
    
    def analyze_dependencies(self, directory: str) -> List[Tuple[str, str, str, List[str]]]:
        """
        Analyze Node.js dependencies in the specified directory and return the results.

        Args:
            directory: The directory containing the package.json file to analyze
            
        Returns:
            A list of tuples (package_name, current_version, latest_version, vulnerabilities)
            
        Raises:
            FileNotFoundError: If the package.json file doesn't exist
            ParsingError: If there's an error parsing the package.json file
            NetworkError: If there's an issue fetching latest versions
        """
        self.logger.info(f"Analyzing Node.js dependencies in {directory}")
        
        # Find the package.json file
        dependency_file = self._get_dependency_file_path(directory)
        
        # Parse the dependencies
        dependencies = self._parse_dependencies(dependency_file)
        
        # Get the latest versions and vulnerabilities
        dependency_info = self._get_installed_dependencies_with_latest(dependencies)
        
        self.logger.info(f"Found {len(dependency_info)} dependencies")
        return dependency_info
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to the package.json file in the specified directory.
        
        Args:
            directory: The directory to search for the package.json file
            
        Returns:
            The Path object for the package.json file
            
        Raises:
            FileNotFoundError: If the package.json file doesn't exist
        """
        file_path = Path(directory) / "package.json"
        if not file_path.exists():
            self.logger.error(f"package.json not found in {directory}")
            raise FileNotFoundError(f"package.json not found in {directory}")
        return file_path
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse the package.json file and extract the dependencies.
        
        Args:
            file_path: The path to the package.json file
            
        Returns:
            A dictionary mapping package names to their current versions
            
        Raises:
            ParsingError: If there's an error parsing the package.json file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            dependencies = {}
            # Include both dependencies and devDependencies
            for dep_type in ("dependencies", "devDependencies"):
                if dep_type in data:
                    for package, version in data[dep_type].items():
                        # Remove any version range specifiers (e.g., "^1.2.3" -> "1.2.3")
                        version = version.lstrip("^~").split("@")[-1]
                        dependencies[package] = version
            
            return dependencies
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Error parsing package.json: {str(e)}")
            raise ParsingError(f"Failed to parse package.json: {str(e)}")