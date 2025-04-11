"""
Maven dependency analyzer module.

This module provides functionality to analyze Maven dependencies
by parsing pom.xml files and fetching the latest versions.
"""

import logging
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .interface import IDependencyAnalyzer
from ..core.constants import API_URLS, DEFAULT_TIMEOUT
from ..core.exceptions import run_command, CommandExecutionError, NetworkError, ParsingError
from ..core.cache import VersionCache


class MavenAnalyzer(IDependencyAnalyzer):
    """Analyzer for Maven dependencies."""
    
    @property
    def environment_name(self) -> str:
        return "Maven"
    
    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a Maven artifact from Maven Central.
        
        Args:
            package_name: The package name in the format "groupId:artifactId"
            
        Returns:
            The latest version as a string
            
        Raises:
            NetworkError: If there's an issue fetching the latest version
            ValueError: If the artifact doesn't exist or another error occurs
        """
        # Check cache first
        cached_version = self.cache.get(package_name)
        if cached_version:
            self.logger.debug(f"Cache hit for {package_name}: {cached_version}")
            return cached_version
        
        # Split package_name into groupId and artifactId
        try:
            group_id, artifact_id = package_name.split(':')
        except ValueError:
            self.logger.error(f"Invalid Maven package name format: {package_name}")
            raise ValueError(f"Invalid Maven package name format: {package_name}")
        
        # Fetch from Maven Central
        url = API_URLS["Maven"].format(group_id=group_id, artifact_id=artifact_id)
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            latest_version = data["response"]["docs"][0]["v"]
            self.cache.set(package_name, latest_version)
            return latest_version
        except (requests.RequestException, IndexError) as e:
            self.logger.error(f"Network error fetching latest version for {package_name}: {str(e)}")
            raise NetworkError(f"Failed to fetch latest version for {package_name}: {str(e)}")
        except (KeyError, ValueError) as e:
            self.logger.error(f"Error parsing Maven response for {package_name}: {str(e)}")
            raise ValueError(f"Failed to parse latest version for {package_name}: {str(e)}")
    
    def analyze_dependencies(self, directory: str) -> List[Tuple[str, str, str, List[str]]]:
        """
        Analyze Maven dependencies in the specified directory and return the results.

        Args:
            directory: The directory containing the pom.xml file to analyze
            
        Returns:
            A list of tuples (package_name, current_version, latest_version, vulnerabilities)
            
        Raises:
            FileNotFoundError: If the pom.xml file doesn't exist
            ParsingError: If there's an error parsing the pom.xml file
            NetworkError: If there's an issue fetching latest versions
        """
        self.logger.info(f"Analyzing Maven dependencies in {directory}")
        
        # Find the pom.xml file
        dependency_file = self._get_dependency_file_path(directory)
        
        # Parse the dependencies
        dependencies = self._parse_dependencies(dependency_file)
        
        # Get the latest versions and vulnerabilities
        dependency_info = self._get_installed_dependencies_with_latest(dependencies)
        
        self.logger.info(f"Found {len(dependency_info)} dependencies")
        return dependency_info
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to the pom.xml file in the specified directory.
        
        Args:
            directory: The directory to search for the pom.xml file
            
        Returns:
            The Path object for the pom.xml file
            
        Raises:
            FileNotFoundError: If the pom.xml file doesn't exist
        """
        file_path = Path(directory) / "pom.xml"
        if not file_path.exists():
            self.logger.error(f"pom.xml not found in {directory}")
            raise FileNotFoundError(f"pom.xml not found in {directory}")
        return file_path
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse the pom.xml file and extract the dependencies.
        
        Args:
            file_path: The path to the pom.xml file
            
        Returns:
            A dictionary mapping package names (groupId:artifactId) to their current versions
            
        Raises:
            ParsingError: If there's an error parsing the pom.xml file
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Define the namespace for Maven XML
            ns = {"m": "http://maven.apache.org/POM/4.0.0"}
            
            dependencies = {}
            # Find all dependencies in the pom.xml
            for dep in root.findall(".//m:dependency", ns):
                group_id = dep.find("m:groupId", ns).text
                artifact_id = dep.find("m:artifactId", ns).text
                version_elem = dep.find("m:version", ns)
                version = version_elem.text if version_elem is not None else "unknown"
                package_name = f"{group_id}:{artifact_id}"
                dependencies[package_name] = version
            
            return dependencies
        except (IOError, ET.ParseError) as e:
            self.logger.error(f"Error parsing pom.xml: {str(e)}")
            raise ParsingError(f"Failed to parse pom.xml: {str(e)}")