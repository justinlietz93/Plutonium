"""
Factory module for creating dependency analyzers.

This module provides a factory for creating dependency analyzers
based on the environment and checking for the existence of dependency files.
"""

import logging
from pathlib import Path
from typing import List, Optional

# Use relative imports within the package
from ..analyzers.interface import IDependencyAnalyzer
from .cache import VersionCache  # Corrected relative import
# Assuming constants are now in plutonium.core
from .constants import SUPPORTED_ENVIRONMENTS, DEPENDENCY_FILES, VULNCHECK_API_TOKEN_ENV_VAR
import os # Import os to get env var

# Import all concrete analyzer classes
from ..analyzers.nodejs_analyzer import NodeJsAnalyzer
from ..analyzers.python_analyzer import PythonAnalyzer
from ..analyzers.ruby_analyzer import RubyAnalyzer # Uncomment if used
from ..analyzers.maven_analyzer import MavenAnalyzer # Uncomment if used
from ..analyzers.go_analyzer import GoAnalyzer # Uncomment if used


class DependencyAnalyzerFactory:
    """Factory for creating dependency analyzers."""

    @staticmethod
    def create_analyzers(directory: str, environments: List[str],
                         cache: Optional[VersionCache] = None) -> List[IDependencyAnalyzer]:
        """
        Create analyzers for the specified environments.

        Args:
            directory: The directory to analyze
            environments: List of environments to analyze
            cache: Optional VersionCache instance to share across analyzers

        Returns:
            A list of dependency analyzers
        """
        analyzers = []
        logger = logging.getLogger("factory")

        # Get VulnCheck token (needed by analyzers for vuln checking)
        vulncheck_api_token = os.getenv(VULNCHECK_API_TOKEN_ENV_VAR)
        if not vulncheck_api_token:
             # Log warning, but let analyzers handle missing token if they attempt vuln check
             logger.warning(f"{VULNCHECK_API_TOKEN_ENV_VAR} not set. Vulnerability checks may fail.")

        # Create a shared cache if none is provided
        if cache is None:
            cache = VersionCache()

        for env in environments:
            # Verify environment is supported
            if env not in SUPPORTED_ENVIRONMENTS:
                logger.warning(f"Skipping unsupported environment: {env}")
                continue

            # Check if dependency file exists
            dependency_file = DEPENDENCY_FILES.get(env)
            if not dependency_file:
                 logger.warning(f"No dependency file defined for environment: {env}")
                 continue # Skip if no file is defined for this env type

            dependency_path = Path(directory) / dependency_file

            # Special case: Node.js uses package.json but relies on package-lock.json for analysis
            if env == "Node.js" and not (Path(directory) / "package-lock.json").exists():
                 if not dependency_path.exists(): # If package.json also doesn't exist
                     logger.info(f"Skipping {env} analysis: {dependency_file} not found in {directory}")
                     continue
                 # If only package.json exists, NodeJsAnalyzer might handle it or warn
                 logger.info(f"Found package.json but no package-lock.json for {env} in {directory}. Analysis might be limited.")
            elif env != "Node.js" and not dependency_path.exists():
                 logger.info(f"Skipping {env} analysis: {dependency_file} not found in {directory}")
                 continue


            # Create the appropriate analyzer, passing the token
            analyzer = None

            # Use a dictionary mapping for cleaner creation
            analyzer_map = {
                "Node.js": NodeJsAnalyzer,
                "Python": PythonAnalyzer,
                "Ruby": RubyAnalyzer, # Uncomment if used
                "Maven": MavenAnalyzer, # Uncomment if used
                "Go": GoAnalyzer, # Uncomment if used
            }

            if env in analyzer_map:
                try:
                    # Pass cache and token to the constructor
                    analyzer = analyzer_map[env](cache=cache, vulncheck_api_token=vulncheck_api_token)
                    logger.info(f"Created analyzer for {env}")
                    analyzers.append(analyzer)
                except Exception as e:
                    logger.error(f"Failed to instantiate analyzer for {env}: {e}")

        return analyzers