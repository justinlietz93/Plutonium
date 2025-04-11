"""
Analyzer interface module.

This module defines the abstract base class that all dependency analyzers must implement.
It establishes the common interface and implements the Template Method pattern.
"""

from abc import ABC, abstractmethod
import os
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from ..core.cache import VersionCache


class IDependencyAnalyzer(ABC):
    """
    Abstract Base Class for dependency analyzers.
    
    This class defines the interface that all dependency analyzers must implement
    and provides some common functionality through the Template Method pattern.
    """
    
    def __init__(self, cache: VersionCache = None):
        """
        Initialize the analyzer with an optional version cache.
        
        Args:
            cache: A VersionCache instance for caching version lookups
        """
        self.cache = cache or VersionCache()
        self.logger = logging.getLogger(f"analyzer.{self.environment_name}")
    
    @property
    @abstractmethod
    def environment_name(self) -> str:
        """
        Get the name of the environment (e.g., "Node.js", "Python").
        
        Returns:
            The environment name as a string
        """
        pass
    
    @abstractmethod
    def get_latest_version(self, package_name: str) -> str:
        """
        Get the latest version of a package.
        
        Args:
            package_name: The name of the package
            
        Returns:
            The latest version as a string
            
        Raises:
            NetworkError: If there's an issue fetching the latest version
            ValueError: If the package doesn't exist or another error occurs
        """
        pass
    
    @abstractmethod
    def analyze_dependencies(self, directory: str, output_file: str) -> None:
        """
        Analyze dependencies in the specified directory and write results to the output file.
        
        This is the main method that implements the Template Method pattern. It should:
        1. Parse the dependency file to extract dependencies
        2. For each dependency, get the current and latest versions
        3. Write the results to the output file
        
        Args:
            directory: The directory containing the dependency file to analyze
            output_file: The path to the output file where results will be written
            
        Raises:
            FileNotFoundError: If the dependency file doesn't exist
            ParsingError: If there's an error parsing the dependency file
            NetworkError: If there's an issue fetching latest versions
        """
        pass
    
    # Suggested internal methods for concrete implementations
    
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to the dependency file in the specified directory.
        
        Args:
            directory: The directory to search for the dependency file
            
        Returns:
            The Path object for the dependency file
            
        Raises:
            FileNotFoundError: If the dependency file doesn't exist
        """
        # Concrete implementation should return the path to the 
        # specific dependency file (e.g., package.json, requirements.txt)
        raise NotImplementedError()
    
    def _parse_dependencies(self, file_path: Path) -> Dict[str, str]:
        """
        Parse the dependency file and extract the dependencies.
        
        Args:
            file_path: The path to the dependency file
            
        Returns:
            A dictionary mapping package names to their current versions
            
        Raises:
            ParsingError: If there's an error parsing the dependency file
        """
        # Concrete implementation should parse the specific dependency file format
        raise NotImplementedError()
    
    def _get_installed_dependencies_with_latest(self, dependencies: Dict[str, str]) -> List[Tuple[str, str, str]]:
        """
        Get the latest versions for all dependencies.
        
        Args:
            dependencies: A dictionary mapping package names to their current versions
            
        Returns:
            A list of tuples (package_name, current_version, latest_version)
        """
        # Concrete implementation should fetch the latest versions
        raise NotImplementedError()
    
    # Helper methods
    
    def write_to_report(self, output_file: str, content: str, mode: str = 'a') -> None:
        """
        Write content to the report file.
        
        Args:
            output_file: The path to the output file
            content: The content to write
            mode: The file mode ('a' for append, 'w' for write/overwrite)
        """
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, mode, encoding='utf-8') as f:
            f.write(content)
        
    def format_markdown_section(self, directory: str, dependencies: List[Tuple[str, str, str]]) -> str:
        """
        Format the dependencies as a Markdown section.
        
        Args:
            directory: The directory being analyzed
            dependencies: A list of tuples (package_name, current_version, latest_version)
            
        Returns:
            A formatted Markdown string
        """
        if not dependencies:
            return f"## {self.environment_name} Dependencies in {directory}\n\nNo dependencies found.\n\n"
        
        lines = [f"## {self.environment_name} Dependencies in {directory}\n\n"]
        lines.append("| Package | Current Version | Latest Version |\n")
        lines.append("|---------|----------------|----------------|\n")
        
        for package, current, latest in sorted(dependencies):
            status = "⚠️" if current != latest else "✅"
            lines.append(f"| {package} | {current} | {latest} {status} |\n")
        
        lines.append("\n")
        return "".join(lines)
