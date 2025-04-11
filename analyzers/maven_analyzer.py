"""
Maven dependency analyzer module.

This module provides functionality to analyze dependencies in Java projects using Maven.
"""

import os
import re
import xml.etree.ElementTree as ET
import requests
import logging
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from .interface import IDependencyAnalyzer
from ..core.constants import API_URLS, DEFAULT_TIMEOUT
from ..core.exceptions import run_command, CommandExecutionError, NetworkError, ParsingError
from ..core.cache import VersionCache


class MavenAnalyzer(IDependencyAnalyzer):
    """Analyzer for Maven dependencies."""
    
    # XML namespace map for parsing POM files
    NAMESPACES = {"maven": "http://maven.apache.org/POM/4.0.0"}
    
    @property
    def environment_name(self) -> str:
        """Get the environment name."""
        return "Maven"
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to pom.xml in the specified directory.
        
        Args:
            directory: The directory to search for pom.xml
            
        Returns:
            The Path object for pom.xml
            
        Raises:
            FileNotFoundError: If pom.xml doesn't exist
        """
        pom_path = Path(directory) / "pom.xml"
        if not pom_path.exists():
            raise FileNotFoundError(f"pom.xml not found in {directory}")
        return pom_path
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse pom.xml and extract the dependencies.
        
        Args:
            file_path: The path to pom.xml
            
        Returns:
            A dictionary mapping dependency coordinates to their current versions
            
        Raises:
            ParsingError: If there's an error parsing pom.xml
        """
        try:
            # Register namespaces
            for prefix, uri in self.NAMESPACES.items():
                ET.register_namespace(prefix, uri)
            
            # Parse the XML file
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Adjust element paths for namespaces
            ns_prefix = "{" + self.NAMESPACES["maven"] + "}"
            
            # Find all dependency elements
            dependencies = {}
            
            # Look for dependencies in the dependencies section
            dependency_elements = root.findall(f".//{ns_prefix}dependencies/{ns_prefix}dependency")
            
            for elem in dependency_elements:
                # Extract dependency information
                group_id = elem.find(f"./{ns_prefix}groupId")
                artifact_id = elem.find(f"./{ns_prefix}artifactId")
                version = elem.find(f"./{ns_prefix}version")
                scope = elem.find(f"./{ns_prefix}scope")
                
                # Skip test dependencies
                if scope is not None and scope.text == "test":
                    continue
                
                # Skip if missing required elements
                if group_id is None or artifact_id is None:
                    continue
                
                # Get the dependency coordinate (groupId:artifactId)
                coordinate = f"{group_id.text}:{artifact_id.text}"
                
                # Get the version or mark as "Not specified" if using property or parent version
                version_text = "Not specified"
                if version is not None:
                    version_text = version.text
                    # If version uses property reference, mark as property
                    if version_text.startswith("${") and version_text.endswith("}"):
                        version_text = "Property reference"
                
                dependencies[coordinate] = version_text
            
            return dependencies
            
        except ET.ParseError as e:
            raise ParsingError(f"Error parsing pom.xml: XML parsing error: {str(e)}")
        except Exception as e:
            raise ParsingError(f"Error parsing pom.xml: {str(e)}")
    
    def get_latest_version(self, coordinate: str) -> str:
        """
        Get the latest version of a Maven artifact.
        
        Args:
            coordinate: The Maven coordinate in the format "groupId:artifactId"
            
        Returns:
            The latest version as a string
            
        Raises:
            NetworkError: If there's an issue fetching the latest version
            ValueError: If the artifact doesn't exist or another error occurs
        """
        # Split coordinate into groupId and artifactId
        parts = coordinate.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid Maven coordinate: {coordinate}")
        
        group_id, artifact_id = parts
        
        # Check cache first
        cache_key = f"maven:{coordinate}"
        cached_version = self.cache.get(cache_key)
        if cached_version:
            self.logger.debug(f"Cache hit for {coordinate}: {cached_version}")
            return cached_version
        
        # Not in cache, fetch from Maven Central
        url = API_URLS['Maven'].format(group_id=group_id, artifact_id=artifact_id)
        self.logger.debug(f"Fetching latest version for {coordinate} from {url}")
        
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            if 'response' in data and 'docs' in data['response'] and len(data['response']['docs']) > 0:
                docs = data['response']['docs']
                # Sort by timestamp to get the latest version
                latest_doc = sorted(docs, key=lambda x: x.get('timestamp', 0), reverse=True)[0]
                latest_version = latest_doc.get('latestVersion') or latest_doc.get('v', 'Unknown')
                
                # Update cache
                self.cache.set(cache_key, latest_version)
                
                return latest_version
            else:
                raise ValueError(f"Unable to determine latest version for {coordinate}")
                
        except requests.RequestException as e:
            raise NetworkError(f"Error fetching latest version for {coordinate}: {str(e)}")
        except (ValueError, KeyError) as e:
            raise ValueError(f"Error processing Maven Central response for {coordinate}: {str(e)}")
    
    def _get_installed_dependencies_with_latest(self, dependencies: Dict[str, str]) -> List[Tuple[str, str, str]]:
        """
        Get the latest versions for all dependencies.
        
        Args:
            dependencies: A dictionary mapping Maven coordinates to their current versions
            
        Returns:
            A list of tuples (coordinate, current_version, latest_version)
        """
        result = []
        
        # Use ThreadPoolExecutor to fetch latest versions concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Create a future for each dependency
            future_to_coordinate = {
                executor.submit(self.get_latest_version, coordinate): (coordinate, current_version)
                for coordinate, current_version in dependencies.items()
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_coordinate):
                coordinate, current_version = future_to_coordinate[future]
                try:
                    latest_version = future.result()
                    result.append((coordinate, current_version, latest_version))
                except Exception as e:
                    self.logger.error(f"Error getting latest version for {coordinate}: {str(e)}")
                    # Include in the result with an error indicator
                    result.append((coordinate, current_version, "Error fetching"))
        
        return result
    
    def analyze_dependencies(self, directory: str, output_file: str) -> None:
        """
        Analyze Maven dependencies in the specified directory.
        
        Args:
            directory: The directory containing pom.xml
            output_file: The path to the output file where results will be written
            
        Raises:
            FileNotFoundError: If pom.xml doesn't exist
            ParsingError: If there's an error parsing pom.xml
        """
        try:
            self.logger.info(f"Analyzing Maven dependencies in {directory}")
            
            # Get dependency file path
            pom_path = self._get_dependency_file_path(directory)
            
            # Parse dependencies
            dependencies = self._parse_dependencies(pom_path)
            
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
            
            self.logger.info(f"Maven dependency analysis for {directory} completed")
            
        except Exception as e:
            self.logger.error(f"Error analyzing Maven dependencies in {directory}: {str(e)}")
            # Write error to report
            error_content = f"## Maven Dependencies in {directory}\n\n"
            error_content += f"Error analyzing dependencies: {str(e)}\n\n"
            self.write_to_report(output_file, error_content)
            raise
