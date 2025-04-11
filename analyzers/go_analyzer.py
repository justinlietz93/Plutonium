"""
Go dependency analyzer module.

This module provides functionality to analyze Go dependencies
by parsing go.mod files and fetching the latest versions.
"""

import logging
import requests
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Change from relative imports to absolute imports
from plutonium.analyzers.interface import IDependencyAnalyzer
from plutonium.core.constants import API_URLS, DEFAULT_TIMEOUT
from plutonium.core.exceptions import run_command, CommandExecutionError, NetworkError, ParsingError
from plutonium.core.cache import VersionCache


class GoAnalyzer(IDependencyAnalyzer):
    """Analyzer for Go dependencies."""
    
    @property
    def environment_name(self) -> str:
        return "Go"
    
    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a Go module from the Go proxy.
        
        Args:
            package_name: The name of the module (e.g., "github.com/gorilla/mux")
            
        Returns:
            The latest version as a string
            
        Raises:
            NetworkError: If there's an issue fetching the latest version
            ValueError: If the module doesn't exist or another error occurs
        """
        # Check cache first
        cached_version = self.cache.get(package_name)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version
        
        # Fetch from Go proxy
        url = API_URLS["Go"].format(package=package_name)
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            versions = response.text.strip().split('\n')
            # The last version in the list is typically the latest
            latest_version = versions[-1]
            self.cache.set(package_name, latest_version)
            return latest_version
        except requests.RequestException as e:
            self.logger.error(f"Network error fetching latest version for {package_name}: {str(e)}")
            raise NetworkError(f"Failed to fetch latest version for {package_name}: {str(e)}")
        except (IndexError, ValueError) as e:
            self.logger.error(f"Error parsing Go proxy response for {package_name}: {str(e)}")
            raise ValueError(f"Failed to parse latest version for {package_name}: {str(e)}")
    
    def analyze_dependencies(self, directory: str) -> List[Tuple[str, str, str, List[str]]]:
        """
        Analyze Go dependencies in the specified directory and return the results.

        Args:
            directory: The directory containing the go.mod file to analyze
            
        Returns:
            A list of tuples (package_name, current_version, latest_version, vulnerabilities)
            
        Raises:
            FileNotFoundError: If the go.mod file doesn't exist
            ParsingError: If there's an error parsing the go.mod file
            NetworkError: If there's an issue fetching latest versions
        """
        self.logger.info(f"Analyzing Go dependencies in {directory}")
        
        # Find the go.mod file
        dependency_file = self._get_dependency_file_path(directory)
        
        # Parse the dependencies
        dependencies = self._parse_dependencies(dependency_file)
        
        # Get the latest versions and vulnerabilities
        dependency_info = self._get_installed_dependencies_with_latest(dependencies)
        
        self.logger.info(f"Found {len(dependency_info)} dependencies")
        return dependency_info
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to the go.mod file in the specified directory.
        
        Args:
            directory: The directory to search for the go.mod file
            
        Returns:
            The Path object for the go.mod file
            
        Raises:
            FileNotFoundError: If the go.mod file doesn't exist
        """
        file_path = Path(directory) / "go.mod"
        if not file_path.exists():
            self.logger.error(f"go.mod not found in {directory}")
            raise FileNotFoundError(f"go.mod not found in {directory}")
        return file_path
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse the go.mod file and extract the dependencies.
        
        Args:
            file_path: The path to the go.mod file
            
        Returns:
            A dictionary mapping module names to their current versions
            
        Raises:
            ParsingError: If there's an error parsing the go.mod file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            dependencies = {}
            require_pattern = re.compile(r"^\s*(\S+)\s+v([\d\.]+.*)$")
            in_require_block = False
            for line in lines:
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                if line == "require (":  # Start of a multi-line require block
                    in_require_block = True
                    continue
                if line == ")":  # End of a multi-line require block
                    in_require_block = False
                    continue
                if line.startswith("require "):  # Single-line require
                    match = require_pattern.match(line.replace("require ", ""))
                elif in_require_block:  # Inside a multi-line require block
                    match = require_pattern.match(line)
                else:
                    continue
                if match:
                    package = match.group(1)
                    version = match.group(2)
                    dependencies[package] = version
            
            return dependencies
        except IOError as e:
            self.logger.error(f"Error reading go.mod: {str(e)}")
            raise ParsingError(f"Failed to read go.mod: {str(e)}")