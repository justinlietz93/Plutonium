"""
Analyzer interface module.

This module defines the abstract base class that all dependency analyzers must implement.
It establishes the common interface and implements the Template Method pattern.
"""

from abc import ABC, abstractmethod
import logging
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Use absolute imports
from abc import ABC, abstractmethod
import logging
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from ..core.cache import VersionCache
from ..core.constants import DEFAULT_TIMEOUT
from ..core.vulnerability_checker import VulnerabilityChecker


class IDependencyAnalyzer(ABC):
    """
    Abstract Base Class for dependency analyzers.
    
    This class defines the interface that all dependency analyzers must implement
    and provides some common functionality through the Template Method pattern.
    """
    
    def __init__(self, cache: VersionCache = None, nvd_api_key: str = None):
        """
        Initialize the analyzer with an optional version cache and NVD API key.
        
        Args:
            cache: A VersionCache instance for caching version lookups
            nvd_api_key: Optional NVD API key (not used with VulnCheck NVD++)
        """
        self.cache = cache or VersionCache()
        self.vulnerability_checker = VulnerabilityChecker(api_key=nvd_api_key)
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
    def analyze_dependencies(self, directory: str) -> List[Tuple[str, str, str, List[str]]]:
        """
        Analyze dependencies in the specified directory and return the results.

        Args:
            directory: The directory containing the dependency file to analyze
            
        Returns:
            A list of tuples (package_name, current_version, latest_version, vulnerabilities)
            
        Raises:
            FileNotFoundError: If the dependency file doesn't exist
            ParsingError: If there's an error parsing the dependency file
            NetworkError: If there's an issue fetching latest versions
        """
        # Find the dependency file
        dependency_file = self._get_dependency_file_path(directory)
        
        # Parse the dependencies
        dependencies = self._parse_dependencies(dependency_file)
        
        # Get the latest versions and vulnerabilities
        dependency_info = self._get_installed_dependencies_with_latest(dependencies)
        
        return dependency_info
    
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
        raise NotImplementedError()
    
    def _get_installed_dependencies_with_latest(self, dependencies: Dict[str, str]) -> List[Tuple[str, str, str, List[str]]]:
        """
        Get the latest versions and vulnerabilities for all dependencies.
        
        Args:
            dependencies: A dictionary mapping package names to their current versions
            
        Returns:
            A list of tuples (package_name, current_version, latest_version, vulnerabilities)
        """
        result = []
        
        # Use ThreadPoolExecutor to fetch latest versions and vulnerabilities concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Create a future for each dependency
            future_to_package = {
                executor.submit(lambda pkg, ver: (pkg, ver, self.get_latest_version(pkg), self.vulnerability_checker.fetch_vulnerabilities(pkg, ver, self.environment_name)), package, current_version): (package, current_version)
                for package, current_version in dependencies.items()
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_package):
                package, current_version = future_to_package[future]
                try:
                    pkg, ver, latest_version, vulnerabilities = future.result()
                    result.append((pkg, ver, latest_version, vulnerabilities))
                except Exception as e:
                    self.logger.error(f"Error getting latest version or vulnerabilities for {package}: {str(e)}")
                    result.append((package, current_version, "Error fetching", ["Error fetching"]))
        
        return result
