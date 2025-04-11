"""
Node.js dependency analyzer module.

This module provides functionality to analyze dependencies in Node.js projects.
"""

import json
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


class NodeJsAnalyzer(IDependencyAnalyzer):
    """Analyzer for Node.js dependencies."""
    
    @property
    def environment_name(self) -> str:
        """Get the environment name."""
        return "Node.js"
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to package.json in the specified directory.
        
        Args:
            directory: The directory to search for package.json
            
        Returns:
            The Path object for package.json
            
        Raises:
            FileNotFoundError: If package.json doesn't exist
        """
        package_json_path = Path(directory) / "package.json"
        if not package_json_path.exists():
            raise FileNotFoundError(f"package.json not found in {directory}")
        return package_json_path
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse package.json and extract the dependencies.
        
        Args:
            file_path: The path to package.json
            
        Returns:
            A dictionary mapping package names to their current versions
            
        Raises:
            ParsingError: If there's an error parsing package.json
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
            
            # Extract dependencies and devDependencies
            dependencies = {}
            dependencies.update(package_data.get('dependencies', {}))
            dependencies.update(package_data.get('devDependencies', {}))
            
            # Clean up version strings (remove ^, ~, etc.)
            for pkg, version in dependencies.items():
                if version.startswith('^') or version.startswith('~'):
                    dependencies[pkg] = version[1:]
            
            return dependencies
            
        except (json.JSONDecodeError, IOError) as e:
            raise ParsingError(f"Error parsing package.json: {str(e)}")
    
    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of an npm package.
        
        Args:
            package_name: The name of the npm package
            
        Returns:
            The latest version as a string
            
        Raises:
            NetworkError: If there's an issue fetching the latest version
            ValueError: If the package doesn't exist or another error occurs
        """
        # Check cache first
        cache_key = f"npm:{package_name}"
        cached_version = self.cache.get(cache_key)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version
        
        # Not in cache, fetch from npm registry
        url = API_URLS['npm'].format(package=package_name)
        self.logger.debug(f"Fetching latest version for {package_name} from {url}")
        
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            if 'dist-tags' in data and 'latest' in data['dist-tags']:
                latest_version = data['dist-tags']['latest']
                
                # Update cache
                self.cache.set(cache_key, latest_version)
                
                return latest_version
            else:
                raise ValueError(f"Unable to determine latest version for {package_name}")
                
        except requests.RequestException as e:
            raise NetworkError(f"Error fetching latest version for {package_name}: {str(e)}")
        except (ValueError, KeyError) as e:
            raise ValueError(f"Error processing npm response for {package_name}: {str(e)}")
    
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
        Analyze Node.js dependencies in the specified directory.
        
        Args:
            directory: The directory containing package.json
            output_file: The path to the output file where results will be written
            
        Raises:
            FileNotFoundError: If package.json doesn't exist
            ParsingError: If there's an error parsing package.json
        """
        try:
            self.logger.info(f"Analyzing Node.js dependencies in {directory}")
            
            # Get dependency file path
            package_json_path = self._get_dependency_file_path(directory)
            
            # Parse dependencies
            dependencies = self._parse_dependencies(package_json_path)
            
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
            
            self.logger.info(f"Node.js dependency analysis for {directory} completed")
            
        except Exception as e:
            self.logger.error(f"Error analyzing Node.js dependencies in {directory}: {str(e)}")
            # Write error to report
            error_content = f"## Node.js Dependencies in {directory}\n\n"
            error_content += f"Error analyzing dependencies: {str(e)}\n\n"
            self.write_to_report(output_file, error_content)
            raise
