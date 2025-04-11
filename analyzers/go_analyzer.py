"""
Go dependency analyzer module.

This module provides functionality to analyze dependencies in Go projects.
"""

import re
import os
import requests
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .interface import IDependencyAnalyzer
from ..core.constants import API_URLS, DEFAULT_TIMEOUT
from ..core.exceptions import run_command, CommandExecutionError, NetworkError, ParsingError
from ..core.cache import VersionCache


class GoAnalyzer(IDependencyAnalyzer):
    """Analyzer for Go dependencies."""
    
    @property
    def environment_name(self) -> str:
        """Get the environment name."""
        return "Go"
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to go.mod in the specified directory.
        
        Args:
            directory: The directory to search for go.mod
            
        Returns:
            The Path object for go.mod
            
        Raises:
            FileNotFoundError: If go.mod doesn't exist
        """
        go_mod_path = Path(directory) / "go.mod"
        if not go_mod_path.exists():
            raise FileNotFoundError(f"go.mod not found in {directory}")
        return go_mod_path
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse go.mod and extract the dependencies.
        
        Args:
            file_path: The path to go.mod
            
        Returns:
            A dictionary mapping package names to their current versions
            
        Raises:
            ParsingError: If there's an error parsing go.mod
        """
        try:
            dependencies = {}
            require_section = False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Start of require section
                    if line.startswith("require ("):
                        require_section = True
                        continue
                    
                    # End of require section
                    if require_section and line == ")":
                        require_section = False
                        continue
                    
                    # Single-line require statement
                    if line.startswith("require ") and not require_section:
                        # Extract the require info after the keyword
                        parts = line[len("require "):].strip().split()
                        if len(parts) >= 2:
                            package, version = parts[0], parts[1]
                            dependencies[package] = version
                        continue
                    
                    # Dependency line in require section
                    if require_section and line and not line.startswith("//"):
                        # Remove inline comments
                        line = line.split("//")[0].strip()
                        parts = line.split()
                        if len(parts) >= 2:
                            package, version = parts[0], parts[1]
                            dependencies[package] = version
            
            return dependencies
        
        except IOError as e:
            raise ParsingError(f"Error parsing go.mod: {str(e)}")
    
    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a Go package.
        
        Args:
            package_name: The name of the Go package
            
        Returns:
            The latest version as a string
            
        Raises:
            NetworkError: If there's an issue fetching the latest version
            ValueError: If the package doesn't exist or another error occurs
        """
        # Check cache first
        cache_key = f"go:{package_name}"
        cached_version = self.cache.get(cache_key)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version
        
        # Not in cache, fetch from Go proxy
        url = API_URLS['Go'].format(package=package_name)
        self.logger.debug(f"Fetching latest version for {package_name} from {url}")
        
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            # Response is a text list of versions
            versions = response.text.strip().split('\n')
            if not versions:
                raise ValueError(f"No versions found for {package_name}")
            
            # The latest version is typically the last one in the list
            latest_version = versions[-1]
            
            # Update cache
            self.cache.set(cache_key, latest_version)
            
            return latest_version
        
        except requests.RequestException as e:
            raise NetworkError(f"Error fetching latest version for {package_name}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error processing Go proxy response for {package_name}: {str(e)}")
    
    def analyze_dependencies(self, directory: str, output_file: str) -> None:
        """
        Analyze Go dependencies in the specified directory.
        
        Args:
            directory: The directory containing go.mod
            output_file: The path to the output file where results will be written
            
        Raises:
            FileNotFoundError: If go.mod doesn't exist
            ParsingError: If there's an error parsing go.mod
        """
        try:
            self.logger.info(f"Analyzing Go dependencies in {directory}")
            
            # Get dependency file path
            go_mod_path = self._get_dependency_file_path(directory)
            
            # Parse dependencies
            dependencies = self._parse_dependencies(go_mod_path)
            
            if not dependencies:
                self.logger.info(f"No dependencies found in {directory}")
                # Write empty section to report
                content = self.format_markdown_section(directory, [])
                self.write_to_report(output_file, content)
                return
            
            self.logger.info(f"Found {len(dependencies)} dependencies")
            
            # Get latest versions and vulnerabilities
            dependencies_with_latest_and_vulns = self._get_installed_dependencies_with_latest(dependencies)
            
            # Format and write to report
            content = self.format_markdown_section(directory, dependencies_with_latest_and_vulns)
            self.write_to_report(output_file, content)
            
            self.logger.info(f"Go dependency analysis for {directory} completed")
            
        except Exception as e:
            self.logger.error(f"Error analyzing Go dependencies in {directory}: {str(e)}")
            # Write error to report
            error_content = f"## Go Dependencies in {directory}\n\n"
            error_content += f"Error analyzing dependencies: {str(e)}\n\n"
            self.write_to_report(output_file, error_content)
            raise