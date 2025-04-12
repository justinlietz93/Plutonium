"""
Analyzer interface module.

This module defines the abstract base class that all dependency analyzers must implement.
It establishes the common interface.
"""

from abc import ABC, abstractmethod
import logging
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any # Added Any
import time # Added for potential delays

# Use relative imports within the package
from ..core.cache import VersionCache
# Assuming constants are now in plutonium.core
from ..core.constants import DEFAULT_TIMEOUT, VULNCHECK_API_TOKEN_ENV_VAR # Import constant name if needed
from ..core.vulnerability_checker import VulnerabilityChecker # Assuming this exists and will be updated


class IDependencyAnalyzer(ABC):
    """
    Abstract Base Class for dependency analyzers.

    This class defines the interface that all dependency analyzers must implement
    and provides common functionality.
    """

    def __init__(self, cache: Optional[VersionCache] = None, vulncheck_api_token: Optional[str] = None):
        """
        Initialize the analyzer with an optional version cache and VulnCheck API token.

        Args:
            cache: A VersionCache instance for caching version lookups.
            vulncheck_api_token: Optional VulnCheck API token for vulnerability checking.
                                 This token should be passed from the factory,
                                 which reads it from the environment (e.g., VULLNCHECK_API_KEY).
        """
        self.cache = cache or VersionCache()
        # Logger name depends on the concrete class's implementation of environment_name
        # It's accessed after the subclass is fully initialized.
        # We set up the logger reference here, but its name is dynamic.
        self.logger = logging.getLogger(f"analyzer.{self.environment_name}")

        # Store the token for potential direct use or for the VulnerabilityChecker
        self.vulncheck_api_token = vulncheck_api_token

        # Initialize the VulnerabilityChecker, passing the VulnCheck token.
        # IMPORTANT: The VulnerabilityChecker class itself needs to be updated
        #            to accept 'vulncheck_token' and use the VulnCheck API.
        self.vulnerability_checker = VulnerabilityChecker(vulncheck_token=self.vulncheck_api_token)

        if not self.vulncheck_api_token:
             # Logging the warning here might be too early if logger name isn't set,
             # but let's keep it for visibility. Alternatively, check in methods that use it.
             logging.warning( # Use root logger if self.logger isn't ready
                 f"VulnCheck API token not provided during initialization of {self.__class__.__name__}. "
                 "Vulnerability checks via VulnerabilityChecker might fail or be skipped."
             )

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
    def get_latest_version(self, package_identifier: Any) -> str:
        """
        Get the latest version of a package.

        Args:
            package_identifier: The name or identifier specific to the environment
                                (e.g., "requests", "groupId:artifactId", "module/path").

        Returns:
            The latest version string or an 'N/A' status string on failure.

        Raises:
            NetworkError: If there's an issue fetching the latest version.
            ParsingError: If the registry response cannot be parsed.
            ValueError: If the identifier is invalid or lookup fails logically.
        """
        pass

    @abstractmethod
    def analyze_dependencies(self, directory: str) -> List[Tuple[str, str, str, List[str]]]:
        """
        Analyze dependencies, fetch latest versions, and check vulnerabilities.
        This is the main method subclasses must implement fully.

        Args:
            directory: The directory containing the dependency file(s).

        Returns:
            A list of tuples (package_name_or_id, current_version, latest_version, vulnerabilities).
            The format of vulnerabilities list elements depends on the checker implementation
            (e.g., ["CVE-XXXX-YYYY", "Error (Timeout)", "N/A (No Token)"]).

        Raises:
            FileNotFoundError: If the primary dependency file doesn't exist.
            ParsingError: If dependency files cannot be parsed.
            NetworkError: If network issues prevent analysis.
        """
        # Subclasses implement the full workflow:
        # 1. Find dependency file(s) (using _get_dependency_file_path or similar)
        # 2. Parse dependencies (using _parse_dependencies or similar)
        # 3. Loop through dependencies:
        #    a. Get latest version (using self.get_latest_version)
        #    b. Check vulnerabilities (e.g., using self.vulnerability_checker.fetch_vulnerabilities
        #       or a dedicated _fetch_vulnerabilities method calling the API directly)
        #    c. Aggregate results
        # 4. Return results
        raise NotImplementedError

    @abstractmethod
    def _get_dependency_file_path(self, directory: str) -> Path:
        """
        Get the path to the primary dependency file for this environment.

        Args:
            directory: The directory to search within.

        Returns:
            The Path object for the dependency file.

        Raises:
            FileNotFoundError: If the required file doesn't exist.
        """
        # Subclasses must implement this to find their specific file (e.g., pom.xml, go.mod)
        raise NotImplementedError

    @abstractmethod
    def _parse_dependencies(self, file_path: Path) -> Dict[Any, str]:
        """
        Parse the primary dependency file.

        Args:
            file_path: The path to the dependency file.

        Returns:
             Dict mapping package identifier (str, tuple, etc.) to its version string
             as found in the file.

        Raises:
            ParsingError: If the file cannot be parsed.
        """
        # Subclasses must implement parsing logic for their specific file format
        raise NotImplementedError

    # Note: The concurrent fetching logic (_get_installed_dependencies_with_latest)
    # has been removed from the base class. It's generally better for each specific
    # analyzer's `analyze_dependencies` method to handle its own fetching loop
    # (either sequentially or concurrently using concurrent.futures within that method)
    # because the identifiers and necessary parameters differ between environments.
    # The lambda function previously here also relied on self.vulnerability_checker,
    # which now needs to be updated to use the VulnCheck token/API.